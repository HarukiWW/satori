
// MARK: - YouTube (v1.62)

/// A YouTube video ID from a link: youtu.be/ID, watch?v=ID, /shorts/ID, /embed/ID, /live/ID, or the ID itself.
enum YouTubeLink {
    static func videoID(from text: String) -> String? {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        if isID(trimmed) {
            return trimmed
        }
        guard let parts = URLComponents(string: trimmed.hasPrefix("http") ? trimmed : "https://" + trimmed),
              let host = parts.host?.lowercased() else { return nil }
        if host.hasSuffix("youtu.be") {
            let id = String(parts.path.dropFirst().prefix(11))
            return isID(id) ? id : nil
        }
        guard host.hasSuffix("youtube.com") || host.hasSuffix("youtube-nocookie.com") else { return nil }
        if let v = parts.queryItems?.first(where: { $0.name == "v" })?.value, isID(v) {
            return v
        }
        let path = parts.path.split(separator: "/").map(String.init)
        if path.count >= 2, ["shorts", "embed", "live", "v"].contains(path[0]) {
            let id = String(path[1].prefix(11))
            return isID(id) ? id : nil
        }
        return nil
    }

    static func isID(_ text: String) -> Bool {
        text.count == 11 && text.unicodeScalars.allSatisfy { scalar in
            CharacterSet.alphanumerics.contains(scalar) && scalar.isASCII || scalar == "-" || scalar == "_"
        }
    }
}

/// The YouTube videos opened in the app, newest first (shown in the video list).
struct YouTubeItem: Codable, Identifiable, Equatable {
    let id: String
    var title: String
}

enum YouTubeHistory {
    private static let key = "youtube.recent.v1"

    static func load() -> [YouTubeItem] {
        guard let data = UserDefaults.standard.data(forKey: key),
              let items = try? JSONDecoder().decode([YouTubeItem].self, from: data) else { return [] }
        return items
    }

    static func add(_ id: String, title: String) {
        var items = load()
        let oldTitle = items.first { $0.id == id }?.title ?? ""
        items.removeAll { $0.id == id }
        items.insert(YouTubeItem(id: id, title: title.isEmpty ? oldTitle : title), at: 0)
        save(Array(items.prefix(30)))
    }

    static func remove(_ id: String) {
        save(load().filter { $0.id != id })
        for prefix in ["resume.", "duration.", "watched.", "subdelay."] {
            UserDefaults.standard.removeObject(forKey: prefix + progressName(id))
        }
    }

    /// The name used for the progress keys (resume., duration., watched.) of a YouTube video.
    static func progressName(_ id: String) -> String {
        "yt:" + id
    }

    private static func save(_ items: [YouTubeItem]) {
        if let data = try? JSONEncoder().encode(items) {
            UserDefaults.standard.set(data, forKey: key)
        }
    }
}

/// Messages of the page go through a weak link: the content controller keeps its handlers.
private final class YouTubeMessageProxy: NSObject, WKScriptMessageHandler {
    weak var target: YouTubeController?

    func userContentController(_ controller: WKUserContentController, didReceive message: WKScriptMessage) {
        let target = self.target
        Task { @MainActor in
            target?.receive(message)
        }
    }
}

/// The official YouTube embed in a web view. A script inside the player frame reports time, length and state, takes
/// play / pause / seek, hides the player's own captions and passes the caption track the player downloads.
@MainActor
final class YouTubeController: ObservableObject {
    @Published var time: Double = 0
    @Published var duration: Double = 0
    @Published var playing = false
    @Published var ended = false
    @Published var title = ""
    @Published var cues: [EmbeddedSubtitles.Cue] = []
    @Published var status = "Загружаю видео…"

    let webView: WKWebView
    private var frame: WKFrameInfo?
    private let proxy = YouTubeMessageProxy()

    init() {
        let config = WKWebViewConfiguration()
        config.allowsInlineMediaPlayback = true
        config.mediaTypesRequiringUserActionForPlayback = []
        config.allowsPictureInPictureMediaPlayback = false
        let script = WKUserScript(source: YouTubeController.frameScript, injectionTime: .atDocumentStart,
                                  forMainFrameOnly: false)
        config.userContentController.addUserScript(script)
        config.userContentController.add(proxy, name: "ykYouTube")
        webView = WKWebView(frame: .zero, configuration: config)
        webView.isOpaque = false
        webView.backgroundColor = .black
        webView.scrollView.isScrollEnabled = false
        webView.scrollView.contentInsetAdjustmentBehavior = .never
        proxy.target = self
    }

    /// The embed is inside a page of our own: YouTube refuses embeds without a referring page (error 152/153).
    func load(_ id: String, start: Double) {
        guard YouTubeLink.isID(id) else { return }
        let origin = "https://www.yomikiri.app"
        let params = "playsinline=1&controls=0&autoplay=1&rel=0&modestbranding=1&iv_load_policy=3&disablekb=1&fs=0"
            + "&cc_load_policy=1&cc_lang_pref=ja&hl=ja&enablejsapi=1&start=" + String(Int(start))
            + "&origin=" + origin
        let html = "<!doctype html><html><head><meta name=\"viewport\" content=\"width=device-width,initial-scale=1,"
            + "maximum-scale=1,user-scalable=no\"><style>html,body{margin:0;height:100%;background:#000;overflow:hidden}"
            + "iframe{position:absolute;top:0;left:0;width:100%;height:100%;border:0}</style></head><body>"
            + "<iframe src=\"https://www.youtube.com/embed/" + id + "?" + params + "\" allow=\"autoplay; encrypted-media\""
            + " referrerpolicy=\"strict-origin-when-cross-origin\"></iframe></body></html>"
        webView.loadHTMLString(html, baseURL: URL(string: origin + "/"))
    }

    func play() {
        run("play", 0)
    }

    func pause() {
        run("pause", 0)
    }

    func seek(to seconds: Double) {
        time = seconds
        ended = false
        run("seek", max(0, seconds))
    }

    private func run(_ command: String, _ value: Double) {
        guard let frame else { return }
        let js = "window.ykCommand && window.ykCommand('" + command + "', " + String(value) + ")"
        webView.evaluateJavaScript(js, in: frame, in: .page) { _ in }
    }

    /// A picture of the player for a note (nil when the video itself is not in the picture).
    func snapshot() async -> UIImage? {
        await withCheckedContinuation { continuation in
            webView.takeSnapshot(with: nil) { image, _ in
                continuation.resume(returning: image)
            }
        }
    }

    fileprivate func receive(_ message: WKScriptMessage) {
        let host = message.frameInfo.securityOrigin.host
        guard host.hasSuffix("youtube.com") || host.hasSuffix("youtube-nocookie.com"),
              let body = message.body as? [String: Any], let type = body["type"] as? String else { return }
        frame = message.frameInfo
        switch type {
        case "tick":
            time = (body["t"] as? NSNumber)?.doubleValue ?? time
            let length = (body["d"] as? NSNumber)?.doubleValue ?? 0
            if length > 0 {
                duration = length
            }
            let state = (body["s"] as? NSNumber)?.intValue ?? -1
            playing = state == 1 || state == 3
            ended = state == 0
            if let name = body["title"] as? String, !name.isEmpty, name != title {
                title = name
            }
        case "tracks":
            let list = body["list"] as? [[String: Any]] ?? []
            let japanese = list.contains { ($0["code"] as? String ?? "").hasPrefix("ja") }
            if cues.isEmpty {
                status = japanese ? "Загружаю японские субтитры…"
                    : list.isEmpty ? "У этого видео нет субтитров." : "У этого видео нет японских субтитров."
            }
        case "cues":
            let lang = body["lang"] as? String ?? ""
            let raw = body["list"] as? [[Any]] ?? []
            guard lang.isEmpty || lang.hasPrefix("ja") else { return }
            var result: [EmbeddedSubtitles.Cue] = []
            for item in raw where item.count >= 3 {
                let start = (item[0] as? NSNumber)?.doubleValue ?? 0
                let end = (item[1] as? NSNumber)?.doubleValue ?? start
                let text = item[2] as? String ?? ""
                if !text.isEmpty {
                    result.append(EmbeddedSubtitles.Cue(start: start, end: end, text: text))
                }
            }
            if !result.isEmpty {
                cues = result
                status = (body["kind"] as? String) == "asr" ? "Автоматические субтитры YouTube" : ""
            }
        case "error":
            let code = (body["code"] as? NSNumber)?.intValue ?? 0
            status = code == 101 || code == 150 || code == 152 || code == 153
                ? "Автор запретил показ этого видео вне YouTube."
                : "YouTube: ошибка " + String(code)
        default:
            break
        }
    }

    /// Runs in the YouTube player frame (injected into every frame, does nothing elsewhere).
    static let frameScript = #"""
    (function () {
      if (!/(^|\.)youtube(-nocookie)?\.com$/.test(location.hostname) || location.pathname.indexOf('/embed/') !== 0) return;
      if (window.__ykYouTube) return;
      window.__ykYouTube = true;
      function post(m) { try { window.webkit.messageHandlers.ykYouTube.postMessage(m); } catch (e) {} }

      // the app draws the captions and the controls
      var css = '.ytp-caption-window-container,.ytp-chrome-top,.ytp-chrome-bottom,.ytp-pause-overlay,.ytp-watermark,' +
        '.ytp-gradient-top,.ytp-gradient-bottom,.ytp-ce-element,.ytp-paid-content-overlay,.ytp-impression-link,' +
        '.ytp-show-cards-title,.ytp-cards-teaser,.ytp-endscreen-content,.ytp-large-play-button,.ytp-youtube-button,' +
        '.ytp-overflow-button{display:none!important}';
      function addStyle() {
        var s = document.createElement('style');
        s.textContent = css;
        (document.head || document.documentElement).appendChild(s);
      }
      if (document.documentElement) addStyle(); else document.addEventListener('DOMContentLoaded', addStyle);

      function param(url, name) {
        try { return new URL(url, location.href).searchParams.get(name) || ''; } catch (e) { return ''; }
      }
      function parse(text) {
        var cues = [];
        try {
          var j = JSON.parse(text);
          (j.events || []).forEach(function (e) {
            if (!e.segs) return;
            var s = e.segs.map(function (g) { return g.utf8 || ''; }).join('').replace(/\n/g, ' ').trim();
            if (!s) return;
            var a = (e.tStartMs || 0) / 1000;
            cues.push([a, a + (e.dDurationMs || 0) / 1000, s]);
          });
        } catch (e) {
          var doc = new DOMParser().parseFromString(text, 'text/xml');
          Array.prototype.forEach.call(doc.getElementsByTagName('p'), function (p) {
            var a = (+p.getAttribute('t') || 0) / 1000, s = (p.textContent || '').trim();
            if (s) cues.push([a, a + (+p.getAttribute('d') || 0) / 1000, s]);
          });
          if (!cues.length) Array.prototype.forEach.call(doc.getElementsByTagName('text'), function (p) {
            var a = +p.getAttribute('start') || 0, s = (p.textContent || '').trim();
            if (s) cues.push([a, a + (+p.getAttribute('dur') || 0), s]);
          });
        }
        cues.sort(function (x, y) { return x[0] - y[0]; });
        // automatic captions roll two lines at once: a line ends where the next one starts
        for (var i = 0; i + 1 < cues.length; i++) {
          if (cues[i][1] > cues[i + 1][0] && cues[i + 1][0] > cues[i][0]) cues[i][1] = cues[i + 1][0];
        }
        return cues;
      }
      function grab(url, text) {
        if (!url || url.indexOf('/api/timedtext') < 0 || !text) return;
        post({ type: 'cues', lang: param(url, 'lang'), kind: param(url, 'kind'), list: parse(text) });
      }

      // the caption track the player downloads for itself
      var open = XMLHttpRequest.prototype.open, send = XMLHttpRequest.prototype.send;
      XMLHttpRequest.prototype.open = function (m, u) { this.__ykUrl = String(u); return open.apply(this, arguments); };
      XMLHttpRequest.prototype.send = function () {
        var x = this;
        x.addEventListener('load', function () {
          try { if (x.responseType === '' || x.responseType === 'text') grab(x.__ykUrl, x.responseText); } catch (e) {}
        });
        return send.apply(this, arguments);
      };
      if (window.fetch) {
        var f = window.fetch;
        window.fetch = function (input) {
          var url = typeof input === 'string' ? input : (input && input.url) || '';
          return f.apply(this, arguments).then(function (r) {
            if (url.indexOf('/api/timedtext') >= 0) r.clone().text().then(function (t) { grab(url, t); }).catch(function () {});
            return r;
          });
        };
      }

      function player() { return document.getElementById('movie_player'); }
      window.ykCommand = function (c, v) {
        var p = player();
        if (!p) return;
        if (c === 'play') p.playVideo();
        else if (c === 'pause') p.pauseVideo();
        else if (c === 'seek') p.seekTo(v, true);
      };

      // the Japanese track (made by people before the automatic one)
      var picked = false, tries = 0, listened = false;
      function pick(p) {
        try { p.loadModule('captions'); } catch (e) {}
        var list = [];
        try { list = p.getOption('captions', 'tracklist') || []; } catch (e) {}
        if (!list.length && tries < 50) return false;
        post({ type: 'tracks', list: list.map(function (t) {
          return { code: t.languageCode || '', name: t.displayName || t.languageName || '', kind: t.kind || '' };
        }) });
        var ja = list.filter(function (t) { return (t.languageCode || '').indexOf('ja') === 0; });
        var best = ja.filter(function (t) { return t.kind !== 'asr'; })[0] || ja[0];
        if (best) { try { p.setOption('captions', 'track', best); } catch (e) {} }
        return true;
      }
      setInterval(function () {
        var p = player();
        if (!p || typeof p.getCurrentTime !== 'function') return;
        if (!listened) {
          listened = true;
          try { p.addEventListener('onError', function (e) { post({ type: 'error', code: +(e && e.data !== undefined ? e.data : e) || 0 }); }); } catch (e) {}
        }
        if (!picked) { tries++; picked = pick(p); }
        var title = '';
        try { title = (p.getVideoData() || {}).title || ''; } catch (e) {}
        var s = -1;
        try { s = p.getPlayerState(); } catch (e) {}
        post({ type: 'tick', t: p.getCurrentTime() || 0, d: p.getDuration() || 0, s: s, title: title });
      }, 200);
    })();
    """#
}

private struct YouTubeWebView: UIViewRepresentable {
    let webView: WKWebView

    func makeUIView(context: Context) -> WKWebView {
        webView
    }

    func updateUIView(_ uiView: WKWebView, context: Context) {}
}

/// A YouTube video in the app: the official player, the Japanese captions under it with word lookup and mining, line
/// buttons, double tap to replay a line, swipe to seek, subtitle delay, saved position and watching statistics.
@available(iOS 16.0, *)
struct YouTubePlayerScreen: View {
    let videoID: String
    @Environment(\.dismiss) private var dismiss
    @StateObject private var player = YouTubeController()
    @State private var line = ""
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

    private var progressName: String {
        YouTubeHistory.progressName(videoID)
    }

    var body: some View {
        VStack(spacing: 10) {
            header
            video
            controls
            subtitles
            Spacer(minLength: 0)
        }
        .background(Color.black.ignoresSafeArea())
        .preferredColorScheme(.dark)
        .navigationBarHidden(true)
        .toolbar(.hidden, for: .tabBar)
        .onAppear(perform: start)
        .onDisappear(perform: stop)
        .onReceive(Timer.publish(every: 0.2, on: .main, in: .common).autoconnect()) { _ in
            tick()
        }
        .onChange(of: player.title) { title in
            YouTubeHistory.add(videoID, title: title)
        }
        .sheet(isPresented: $showLookup) {
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
        HStack(spacing: 12) {
            Button {
                dismiss()
            } label: {
                Image(systemName: "xmark")
                    .font(.system(size: 20, weight: .semibold))
                    .frame(width: 40, height: 40)
            }
            Text(player.title.isEmpty ? "YouTube" : player.title)
                .font(.headline)
                .lineLimit(1)
                .frame(maxWidth: .infinity)
            Button {
                showMenu = true
            } label: {
                Image(systemName: "ellipsis.circle")
                    .font(.system(size: 20, weight: .semibold))
                    .frame(width: 40, height: 40)
            }
        }
        .foregroundColor(.white)
        .padding(.horizontal, 12)
    }

    private var video: some View {
        ZStack {
            YouTubeWebView(webView: player.webView)
            // the app takes all touches: the YouTube controls never show up
            Color.black.opacity(0.001)
                .contentShape(Rectangle())
                .onTapGesture(count: 2) { replayLine() }
                .onTapGesture { togglePlay() }
                .gesture(DragGesture(minimumDistance: 20)
                    .onChanged { value in swipeChanged(value.translation.width) }
                    .onEnded { _ in swipeEnded() })
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
        .frame(maxWidth: .infinity)
    }

    private var controls: some View {
        VStack(spacing: 6) {
            Slider(value: Binding(get: { swipeTarget ?? player.time },
                                  set: { swipeTarget = $0 }),
                   in: 0 ... max(player.duration, 1),
                   onEditingChanged: { editing in
                       if !editing, let target = swipeTarget {
                           swipeTarget = nil
                           player.seek(to: target)
                       }
                   })
            .tint(.blue)
            HStack {
                Text(timeText(swipeTarget ?? player.time))
                Spacer()
                Text(timeText(player.duration))
            }
            .font(.caption.monospacedDigit())
            .foregroundColor(.secondary)
            HStack(spacing: 36) {
                controlButton("backward.end.fill") { jumpLine(-1) }
                controlButton(player.playing ? "pause.fill" : "play.fill", size: 30) { togglePlay() }
                controlButton("forward.end.fill") { jumpLine(1) }
            }
        }
        .padding(.horizontal, 16)
    }

    private func controlButton(_ symbol: String, size: CGFloat = 22, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Image(systemName: symbol)
                .font(.system(size: size, weight: .semibold))
                .foregroundColor(.white)
                .frame(width: 52, height: 44)
        }
    }

    @ViewBuilder
    private var subtitles: some View {
        if !line.isEmpty {
            SubtitleLookupBar(line: line, onTap: { _ in openLookup() })
        } else if !player.status.isEmpty {
            Text(player.status)
                .font(.footnote)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 20)
        }
    }

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
        let saved = VideoProgress.position(progressName)
        let length = UserDefaults.standard.double(forKey: "duration." + progressName)
        let resume = saved > 10 && (length <= 0 || saved < length - 30) ? saved : 0
        lastSaved = resume
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
    }

    private func tick() {
        let t = player.time - subDelay
        let next = player.cues.filter { $0.start <= t && t < $0.end }.map { $0.text }.joined(separator: "\n")
        if next != line {
            line = next
        }
        if player.duration > 0, abs(player.time - lastSaved) >= 5 {
            lastSaved = player.time
            VideoProgress.save(progressName, position: player.time, duration: player.duration)
        }
        recordWatching()
    }

    private func togglePlay() {
        if showLookup {
            showLookup = false
        } else if player.playing {
            player.pause()
        } else {
            player.play()
        }
    }

    /// The cue under the current time (with the delay), or the last one before it.
    private func currentCueIndex() -> Int? {
        let t = player.time - subDelay
        return player.cues.lastIndex { $0.start <= t + 0.05 }
    }

    private func jumpLine(_ step: Int) {
        guard !player.cues.isEmpty else {
            player.seek(to: min(max(player.time + Double(step) * 15, 0), player.duration))
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
            swipeStart = player.time
        }
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
        subDelay = (subDelay + by * 100).rounded() / 100
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
        lookupWord = line
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

/// A YouTube link typed or pasted.
@available(iOS 16.0, *)
struct YouTubeLinkSheet: View {
    let onOpen: (String) -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var link = ""

    private var videoID: String? {
        YouTubeLink.videoID(from: link)
    }

    var body: some View {
        NavigationView {
            Form {
                Section {
                    TextField("https://youtu.be/…", text: $link)
                        .keyboardType(.URL)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                    PasteButton(payloadType: String.self) { strings in
                        if let first = strings.first {
                            link = first
                        }
                    }
                } header: {
                    Text("Ссылка на видео YouTube")
                } footer: {
                    Text(link.isEmpty || videoID != nil
                         ? "Видео откроется в плеере YouTube, японские субтитры — под ним, с поиском слов и майнингом."
                         : "Это не ссылка на видео YouTube.")
                }
            }
            .navigationTitle("YouTube")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Отмена") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Открыть") {
                        if let id = videoID {
                            dismiss()
                            onOpen(id)
                        }
                    }
                    .disabled(videoID == nil)
                }
            }
        }
    }
}

/// The YouTube videos opened before, at the top of the video list.
@available(iOS 16.0, *)
struct YouTubeRecentSection: View {
    /// loaded by the list when it appears
    @Binding var items: [YouTubeItem]

    var body: some View {
        Group {
            if !items.isEmpty {
                Section {
                    ForEach(items) { item in
                        NavigationLink(destination: YouTubePlayerScreen(videoID: item.id)) {
                            VStack(alignment: .leading, spacing: 6) {
                                Text(item.title.isEmpty ? item.id : item.title)
                                    .lineLimit(2)
                                if let part = VideoProgress.fraction(YouTubeHistory.progressName(item.id)) {
                                    ProgressView(value: part)
                                        .tint(.blue)
                                }
                            }
                            .padding(.vertical, 2)
                        }
                        .swipeActions(edge: .trailing, allowsFullSwipe: true) {
                            Button(role: .destructive) {
                                YouTubeHistory.remove(item.id)
                                items = YouTubeHistory.load()
                            } label: {
                                Label("Удалить", systemImage: "trash")
                            }
                        }
                    }
                } header: {
                    Text("YouTube")
                }
            }
        }
    }
}
