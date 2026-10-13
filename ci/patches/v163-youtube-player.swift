/// A YouTube video in the app: the official player with the Japanese captions under it (portrait) or over it
/// (landscape), word lookup and mining, line buttons, double tap to replay a line, swipe to seek, subtitle delay,
/// saved position and watching statistics.
@available(iOS 16.0, *)
struct YouTubePlayerScreen: View {
    let videoID: String
    @Environment(\.dismiss) private var dismiss
    @Environment(\.verticalSizeClass) private var verticalSize
    @StateObject private var player = YouTubeController()
    @State private var subDelay: Double = 0
    @State private var showLookup = false
    @State private var lookupWord = ""
    @State private var showMenu = false
    @State private var swipeStart: Double? = nil
    @State private var swipeTarget: Double? = nil
    @State private var lastSaved: Double = 0
    @State private var lastTick: CFTimeInterval = 0
    @State private var watchPending: Double = 0
    @State private var watchWords = 0
    @State private var lastCountedLine = ""
    @State private var started = false
    @State private var controlsVisible = true
    @State private var lastTouch: CFTimeInterval = 0
    @State private var forcedLandscape = false
    /// kept by the view (a timer made inside `body` would start again on every redraw)
    private let ticker = Timer.publish(every: 0.5, on: .main, in: .common).autoconnect()

    private var progressName: String {
        YouTubeHistory.progressName(videoID)
    }

    private var landscape: Bool {
        verticalSize == .compact
    }

    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()
            VStack(spacing: 10) {
                if !landscape {
                    header
                }
                video
                if !landscape {
                    controls
                    subtitles
                    Spacer(minLength: 0)
                }
            }
            if landscape && showLookup {
                landscapeLookup
            }
        }
        .preferredColorScheme(.dark)
        .navigationBarHidden(true)
        .toolbar(.hidden, for: .tabBar)
        .statusBarHidden(landscape)
        .onAppear(perform: start)
        .onDisappear(perform: stop)
        .onReceive(ticker) { _ in
            tick()
        }
        .onChange(of: player.title) { title in
            YouTubeHistory.add(videoID, title: title)
        }
        .sheet(isPresented: Binding(get: { showLookup && !landscape }, set: { showLookup = $0 })) {
            WordLookupSheet(text: lookupWord)
        }
        .onChange(of: showLookup) { shown in
            if !shown {
                player.play()
            }
        }
        .sheet(isPresented: $showMenu) {
            menu
        }
        // back from AnkiMobile: close the lookup and go on (the sheet may ignore the first dismissal)
        .onReceive(NotificationCenter.default.publisher(for: Notification.Name("yomikiri.ankiReturn"))) { _ in
            Task { @MainActor in
                for delay in [0.1, 0.4, 1.0] {
                    showLookup = false
                    try? await Task.sleep(nanoseconds: UInt64(delay * 1_000_000_000))
                }
                player.play()
            }
        }
    }

    private var header: some View {
        HStack(spacing: 8) {
            iconButton("xmark") { dismiss() }
            Text(player.title.isEmpty ? "YouTube" : player.title)
                .font(.headline)
                .lineLimit(1)
                .frame(maxWidth: .infinity)
            iconButton("rotate.right") { toggleLandscape() }
            iconButton("ellipsis.circle") { showMenu = true }
        }
        .foregroundColor(.white)
        .padding(.horizontal, 12)
    }

    private func iconButton(_ symbol: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Image(systemName: symbol)
                .font(.system(size: 20, weight: .semibold))
                .foregroundColor(.white)
                .frame(width: 40, height: 40)
        }
    }

    private var video: some View {
        ZStack {
            YouTubeWebView(webView: player.webView)
            // the app takes all touches: the YouTube controls never show up
            Color.black.opacity(0.001)
                .contentShape(Rectangle())
                .onTapGesture(count: 2) { replayLine() }
                .onTapGesture { tapVideo() }
                .gesture(DragGesture(minimumDistance: 20)
                    .onChanged { value in swipeChanged(value.translation.width) }
                    .onEnded { _ in swipeEnded() })
            if landscape {
                landscapeSubtitles
                if controlsVisible {
                    landscapeControls
                }
            }
            if let target = swipeTarget {
                Text(timeText(target) + " / " + timeText(player.duration))
                    .font(.system(size: 18, weight: .semibold).monospacedDigit())
                    .foregroundColor(.white)
                    .padding(.horizontal, 14)
                    .padding(.vertical, 8)
                    .background(.ultraThinMaterial, in: Capsule())
            }
        }
        .aspectRatio(16 / 9, contentMode: .fit)
        .frame(maxWidth: .infinity, maxHeight: landscape ? .infinity : nil)
        .ignoresSafeArea(edges: landscape ? .all : [])
    }

    private var slider: some View {
        Slider(value: Binding(get: { swipeTarget ?? player.time },
                              set: { swipeTarget = $0 }),
               in: 0 ... max(player.duration, 1),
               onEditingChanged: { editing in
                   lastTouch = CACurrentMediaTime()
                   if !editing, let target = swipeTarget {
                       swipeTarget = nil
                       player.seek(to: target)
                   }
               })
        .tint(.blue)
    }

    private var times: some View {
        HStack {
            Text(timeText(swipeTarget ?? player.time))
            Spacer()
            Text(timeText(player.duration))
        }
        .font(.caption.monospacedDigit())
        .foregroundColor(.secondary)
    }

    private var lineButtons: some View {
        HStack(spacing: 36) {
            controlButton("backward.end.fill") { jumpLine(-1) }
            controlButton(player.playing ? "pause.fill" : "play.fill", size: 30) { togglePlay() }
            controlButton("forward.end.fill") { jumpLine(1) }
        }
    }

    private var controls: some View {
        VStack(spacing: 6) {
            slider
            times
            lineButtons
        }
        .padding(.horizontal, 16)
    }

    private func controlButton(_ symbol: String, size: CGFloat = 22, action: @escaping () -> Void) -> some View {
        Button {
            lastTouch = CACurrentMediaTime()
            action()
        } label: {
            Image(systemName: symbol)
                .font(.system(size: size, weight: .semibold))
                .foregroundColor(.white)
                .frame(width: 52, height: 44)
        }
    }

    @ViewBuilder
    private var subtitles: some View {
        if !player.line.isEmpty {
            SubtitleLookupBar(line: player.line, onTap: { _ in openLookup() })
        } else if !player.status.isEmpty {
            Text(player.status)
                .font(.footnote)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 20)
        }
    }

    // MARK: - landscape

    /// The line over the bottom of the picture, above the controls when they show.
    private var landscapeSubtitles: some View {
        VStack {
            Spacer()
            if !player.line.isEmpty {
                SubtitleLookupBar(line: player.line, onTap: { _ in openLookup() })
                    .padding(.horizontal, 40)
            }
        }
        .padding(.bottom, controlsVisible ? 92 : 14)
    }

    private var landscapeControls: some View {
        VStack(spacing: 0) {
            HStack(spacing: 8) {
                iconButton("xmark") { dismiss() }
                Text(player.title.isEmpty ? "YouTube" : player.title)
                    .font(.headline)
                    .foregroundColor(.white)
                    .lineLimit(1)
                    .frame(maxWidth: .infinity)
                iconButton("rotate.right") { toggleLandscape() }
                iconButton("ellipsis.circle") { showMenu = true }
            }
            .padding(.horizontal, 20)
            .padding(.top, 8)
            .background(LinearGradient(colors: [.black.opacity(0.6), .clear], startPoint: .top, endPoint: .bottom))
            Spacer()
            VStack(spacing: 2) {
                lineButtons
                HStack(spacing: 10) {
                    Text(timeText(swipeTarget ?? player.time))
                    slider
                    Text(timeText(player.duration))
                }
                .font(.caption.monospacedDigit())
                .foregroundColor(.white)
            }
            .padding(.horizontal, 24)
            .padding(.bottom, 6)
            .background(LinearGradient(colors: [.clear, .black.opacity(0.6)], startPoint: .top, endPoint: .bottom))
        }
    }

    /// The lookup over the lower part of the screen; a tap above it or a swipe down on the handle closes it.
    private var landscapeLookup: some View {
        GeometryReader { geo in
            VStack(spacing: 0) {
                Color.clear
                    .frame(height: geo.size.height * 0.22)
                    .contentShape(Rectangle())
                    .onTapGesture { showLookup = false }
                WordLookupSheet(text: lookupWord)
                    .overlay(alignment: .top) {
                        Capsule()
                            .fill(Color.secondary.opacity(0.6))
                            .frame(width: 36, height: 5)
                            .padding(.vertical, 8)
                            .padding(.horizontal, 60)
                            .contentShape(Rectangle())
                            .gesture(DragGesture().onEnded { value in
                                if value.translation.height > 40 { showLookup = false }
                            })
                    }
            }
        }
    }

    /// Landscape (also with the rotation lock on) and back.
    private func toggleLandscape() {
        guard let scene = UIApplication.shared.connectedScenes.compactMap({ $0 as? UIWindowScene }).first else { return }
        let toLandscape = !scene.interfaceOrientation.isLandscape
        forcedLandscape = toLandscape
        lastTouch = CACurrentMediaTime()
        scene.requestGeometryUpdate(.iOS(interfaceOrientations: toLandscape ? .landscapeRight : .portrait)) { _ in }
    }

    private func restorePortrait() {
        guard let scene = UIApplication.shared.connectedScenes.compactMap({ $0 as? UIWindowScene }).first else { return }
        forcedLandscape = false
        scene.requestGeometryUpdate(.iOS(interfaceOrientations: .portrait)) { _ in }
    }

    // MARK: - menu

    private var menu: some View {
        NavigationView {
            List {
                Section {
                    HStack(spacing: 6) {
                        delayButton("−0.5") { shiftDelay(-0.5) }
                        delayButton("−0.1") { shiftDelay(-0.1) }
                        Text(String(format: "%+.2f с", subDelay))
                            .font(.callout.monospacedDigit())
                            .frame(maxWidth: .infinity)
                        delayButton("+0.1") { shiftDelay(0.1) }
                        delayButton("+0.5") { shiftDelay(0.5) }
                    }
                } header: {
                    Text("Задержка субтитров")
                }
                Section {
                    Text(player.cues.isEmpty ? player.status : "Реплик: " + String(player.cues.count))
                        .foregroundColor(.secondary)
                } header: {
                    Text("Субтитры")
                } footer: {
                    Text("Берутся японские субтитры самого YouTube: сначала сделанные людьми, иначе автоматические. Кнопка ⊕ в словаре добавляет слово в Anki или в очередь майнинга, в карточку идёт снимок плеера или обложка видео.")
                }
            }
            .navigationTitle("Настройки")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Готово") { showMenu = false }
                }
            }
        }
        .presentationDetents([.medium])
    }

    private func delayButton(_ title: String, _ action: @escaping () -> Void) -> some View {
        Button(title, action: action)
            .buttonStyle(.bordered)
            .controlSize(.small)
            .lineLimit(1)
            .fixedSize()
    }

    // MARK: - playback

    private func start() {
        guard !started else { return }
        started = true
        subDelay = UserDefaults.standard.double(forKey: "subdelay." + progressName)
        player.delay = subDelay
        let saved = VideoProgress.position(progressName)
        let length = UserDefaults.standard.double(forKey: "duration." + progressName)
        let resume = saved > 10 && (length <= 0 || saved < length - 30) ? saved : 0
        lastSaved = resume
        lastTouch = CACurrentMediaTime()
        YouTubeHistory.add(videoID, title: "")
        player.load(videoID, start: resume)
        prepareMining()
    }

    private func stop() {
        yomikiriOpenLinkHook = nil
        yomikiriQueuedWordsHook = nil
        MiningFrame.jpegBase64 = nil
        if player.duration > 0 {
            VideoProgress.save(progressName, position: player.time, duration: player.duration)
        }
        flushWatching()
        player.pause()
        player.stopTimer()
        if forcedLandscape {
            restorePortrait()
        }
    }

    private func tick() {
        if player.duration > 0, abs(player.time - lastSaved) >= 5 {
            lastSaved = player.time
            VideoProgress.save(progressName, position: player.time, duration: player.duration)
        }
        // the controls over the picture hide a few seconds after the last touch while playing
        if landscape, controlsVisible, player.playing, swipeTarget == nil, CACurrentMediaTime() - lastTouch > 4 {
            withAnimation(.easeOut(duration: 0.25)) {
                controlsVisible = false
            }
        }
        recordWatching()
    }

    /// Portrait: play / pause. Landscape: show / hide the controls. An open lookup closes first.
    private func tapVideo() {
        lastTouch = CACurrentMediaTime()
        if showLookup {
            showLookup = false
        } else if landscape {
            withAnimation(.easeOut(duration: 0.2)) {
                controlsVisible.toggle()
            }
        } else {
            togglePlay()
        }
    }

    private func togglePlay() {
        if player.playing {
            player.pause()
        } else {
            player.play()
        }
    }

    /// The cue under the current time (with the delay), or the last one before it.
    private func currentCueIndex() -> Int? {
        let t = player.currentTime - subDelay
        return player.cues.lastIndex { $0.start <= t + 0.05 }
    }

    private func jumpLine(_ step: Int) {
        guard !player.cues.isEmpty else {
            player.seek(to: min(max(player.currentTime + Double(step) * 15, 0), player.duration))
            return
        }
        let index = (currentCueIndex() ?? -1) + step
        let clamped = min(max(index, 0), player.cues.count - 1)
        player.seek(to: max(0, player.cues[clamped].start + subDelay))
        player.play()
    }

    private func replayLine() {
        guard let index = currentCueIndex() else { return }
        player.seek(to: max(0, player.cues[index].start + subDelay - 0.4))
        player.play()
    }

    private func swipeChanged(_ width: CGFloat) {
        if swipeStart == nil {
            swipeStart = player.currentTime
        }
        lastTouch = CACurrentMediaTime()
        let span = max(player.duration, 1)
        // a full swipe across the screen is two minutes, or the whole video if it is shorter
        let seconds = Double(width / UIScreen.main.bounds.width) * min(120, span)
        swipeTarget = min(max((swipeStart ?? 0) + seconds, 0), span)
    }

    private func swipeEnded() {
        if let target = swipeTarget {
            player.seek(to: target)
        }
        swipeStart = nil
        swipeTarget = nil
    }

    private func shiftDelay(_ by: Double) {
        subDelay = ((subDelay + by) * 100).rounded() / 100
        player.delay = subDelay
        UserDefaults.standard.set(subDelay, forKey: "subdelay." + progressName)
    }

    private func timeText(_ seconds: Double) -> String {
        let total = Int(max(0, seconds))
        let h = total / 3600
        let m = (total % 3600) / 60
        let s = total % 60
        return h > 0 ? String(format: "%d:%02d:%02d", h, m, s) : String(format: "%d:%02d", m, s)
    }

    // MARK: - lookup and mining

    private func openLookup() {
        lookupWord = player.line
        player.pause()
        showLookup = true
        captureFrame()
    }

    private func prepareMining() {
        MiningFrame.jpegBase64 = nil
        yomikiriQueuedWordsHook = {
            MiningQueue.shared.entries.map { MiningQueue.statsWord(of: $0.url) }
        }
        let id = videoID
        let controller = player
        yomikiriOpenLinkHook = { [weak controller] link in
            guard MiningFrame.isAddNote(link) else { return link }
            let withFrame = MiningFrame.attach(to: link)
            if UserDefaults.standard.bool(forKey: "ykMiningQueue") {
                let title = controller?.title ?? ""
                MiningQueue.shared.add(withFrame, video: "YouTube: " + (title.isEmpty ? id : title))
                UINotificationFeedbackGenerator().notificationOccurred(.success)
                return nil
            }
            return withFrame
        }
    }

    /// The note gets a picture of the player; when the video is not in the picture (a black snapshot), the cover.
    private func captureFrame() {
        MiningFrame.jpegBase64 = nil
        let id = videoID
        let controller = player
        Task { @MainActor in
            if let image = await controller.snapshot(), let cg = image.cgImage, !YouTubePlayerScreen.isDark(cg) {
                MiningFrame.capture(cg)
                return
            }
            guard let url = URL(string: "https://i.ytimg.com/vi/" + id + "/hqdefault.jpg"),
                  let loaded = try? await URLSession.shared.data(from: url),
                  let cover = UIImage(data: loaded.0)?.cgImage else { return }
            MiningFrame.capture(cover)
        }
    }

    /// Almost black: the web view did not draw the video into the snapshot.
    nonisolated static func isDark(_ image: CGImage) -> Bool {
        let side = 8
        var pixels = [UInt8](repeating: 0, count: side * side * 4)
        guard let context = CGContext(data: &pixels, width: side, height: side, bitsPerComponent: 8,
                                      bytesPerRow: side * 4, space: CGColorSpaceCreateDeviceRGB(),
                                      bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) else { return true }
        context.draw(image, in: CGRect(x: 0, y: 0, width: side, height: side))
        var sum = 0
        for index in stride(from: 0, to: pixels.count, by: 4) {
            sum += Int(pixels[index]) + Int(pixels[index + 1]) + Int(pixels[index + 2])
        }
        return sum / (side * side * 3) < 10
    }

    // MARK: - watching statistics

    private func recordWatching() {
        let now = CACurrentMediaTime()
        let step = lastTick > 0 ? min(1.0, now - lastTick) : 0
        lastTick = now
        guard player.playing else { return }
        watchPending += step
        let line = player.line
        if !line.isEmpty, line != lastCountedLine {
            lastCountedLine = line
            watchWords += NativeLookup.tokenize(line, charAt: 0).tokens.filter { token in
                token.text.unicodeScalars.contains { CharacterSet.letters.contains($0) } && !token.pos.contains("記号")
            }.count
        }
        if watchPending >= 10 {
            flushWatching()
        }
    }

    private func flushWatching() {
        let seconds = Int(watchPending.rounded())
        guard seconds > 0 || watchWords > 0 else { return }
        WatchStats.add(seconds: seconds, words: watchWords)
        watchPending = 0
        watchWords = 0
    }
}

