
// MARK: - Reading v1.74: smooth lists while downloading, folding volumes, search, chapters in the statistics

/// The download in progress, apart from the store: only the small progress rows redraw on every page.
@MainActor
final class NovelProgress: ObservableObject {
    static let shared = NovelProgress()
    @Published var job: NovelStore.Job? = nil
}

/// "Скачать всё" or the progress of this novel.
@available(iOS 16.0, *)
struct NovelDownloadRow: View {
    let ncode: String
    let missing: [Int]
    @ObservedObject private var progress = NovelProgress.shared

    var body: some View {
        if let job = progress.job, job.ncode == ncode {
            NovelJobRow(job: job)
        } else if !missing.isEmpty {
            Button {
                NovelStore.shared.download(ncode, missing)
            } label: {
                Label("Скачать всё (" + String(missing.count) + " гл.)", systemImage: "arrow.down.circle")
            }
        } else {
            Label("Все главы скачаны", systemImage: "checkmark.circle")
                .foregroundColor(.secondary)
        }
    }
}

/// Words from a list of unknown words go to the mining queue, not straight to AnkiMobile; the hooks of the screen
/// below come back when the list closes.
@available(iOS 16.0, *)
struct QueueMiningHooks: ViewModifier {
    let source: String
    @State private var savedOpen: ((URL) -> URL?)? = nil
    @State private var savedQueued: (() -> [String])? = nil

    func body(content: Content) -> some View {
        content
            .onAppear {
                savedOpen = yomikiriOpenLinkHook
                savedQueued = yomikiriQueuedWordsHook
                MiningFrame.jpegBase64 = nil
                let name = source
                yomikiriQueuedWordsHook = {
                    MiningQueue.shared.entries.map { MiningQueue.statsWord(of: $0.url) }
                }
                yomikiriOpenLinkHook = { link in
                    guard MiningFrame.isAddNote(link) else { return link }
                    MiningQueue.shared.add(link, video: name)
                    UINotificationFeedbackGenerator().notificationOccurred(.success)
                    return nil
                }
            }
            .onDisappear {
                yomikiriOpenLinkHook = savedOpen
                yomikiriQueuedWordsHook = savedQueued
            }
    }
}

/// A text field that opens with the Japanese keyboard (when it is turned on in the iOS settings).
final class JapaneseUITextField: UITextField {
    override var textInputMode: UITextInputMode? {
        UITextInputMode.activeInputModes.first { ($0.primaryLanguage ?? "").hasPrefix("ja") } ?? super.textInputMode
    }
}

struct JapaneseTextField: UIViewRepresentable {
    @Binding var text: String
    var placeholder: String
    var onSubmit: () -> Void

    func makeUIView(context: Context) -> JapaneseUITextField {
        let field = JapaneseUITextField()
        field.placeholder = placeholder
        field.returnKeyType = .search
        field.autocorrectionType = .no
        field.autocapitalizationType = .none
        field.clearButtonMode = .whileEditing
        field.font = UIFont.preferredFont(forTextStyle: .title3)
        field.delegate = context.coordinator
        field.addTarget(context.coordinator, action: #selector(Coordinator.changed(_:)), for: .editingChanged)
        DispatchQueue.main.async {
            field.becomeFirstResponder()
        }
        return field
    }

    func updateUIView(_ uiView: JapaneseUITextField, context: Context) {
        if uiView.text != text {
            uiView.text = text
        }
    }

    func makeCoordinator() -> Coordinator {
        Coordinator(text: $text, onSubmit: onSubmit)
    }

    final class Coordinator: NSObject, UITextFieldDelegate {
        let text: Binding<String>
        let onSubmit: () -> Void

        init(text: Binding<String>, onSubmit: @escaping () -> Void) {
            self.text = text
            self.onSubmit = onSubmit
        }

        @objc func changed(_ field: UITextField) {
            text.wrappedValue = field.text ?? ""
        }

        func textFieldShouldReturn(_ textField: UITextField) -> Bool {
            onSubmit()
            return true
        }
    }
}

/// A word typed while reading: the dictionary of the app, the Japanese keyboard opens at once.
@available(iOS 16.0, *)
struct ReaderSearchSheet: View {
    @State private var query = ""
    @State private var submitted = ""

    private var pageURL: URL? {
        let page = Bundle.main.url(forResource: "dictionary", withExtension: "html", subdirectory: "res")
        return page?.withPathComponents([
            URLQueryItem(name: "context", value: "app"),
            URLQueryItem(name: "search", value: submitted),
        ])
    }

    var body: some View {
        VStack(spacing: 10) {
            HStack(spacing: 10) {
                Image(systemName: "magnifyingglass").foregroundColor(.secondary)
                JapaneseTextField(text: $query, placeholder: "Слово или фраза по-японски") {
                    submitted = query.trimmingCharacters(in: .whitespacesAndNewlines)
                }
                .frame(height: 36)
            }
            .padding(.horizontal, 14)
            .padding(.vertical, 6)
            .background(Color(.secondarySystemBackground))
            .cornerRadius(12)
            .padding(.horizontal, 12)
            .padding(.top, 14)
            if !submitted.isEmpty, let url = pageURL {
                YomikiriWebView(url: url)
                    .scrollable(false)
                    .overscroll(false)
                    .edgeToEdge(true)
                    .ignoresSafeArea(.keyboard)
                    .clipShape(RoundedRectangle(cornerRadius: 22, style: .continuous))
                    .padding(.horizontal, 8)
                    .id(submitted)
            } else {
                Text("Введите слово и нажмите «Поиск» на клавиатуре.")
                    .font(.footnote)
                    .foregroundColor(.secondary)
                    .padding(.top, 8)
                Spacer()
            }
        }
        .presentationDetents([.medium, .large])
        .presentationDragIndicator(.visible)
    }
}

/// The saved novels.
@available(iOS 16.0, *)
struct NovelLibraryView: View {
    @ObservedObject private var store = NovelStore.shared
    @ObservedObject private var analyzer = NovelAnalyzer.shared
    @ObservedObject private var progress = NovelProgress.shared
    @State private var showAdd = false
    @State private var showQueue = false
    @State private var pendingDelete: NovelInfo? = nil

    var body: some View {
        List {
            if let job = progress.job {
                Section {
                    NovelJobRow(job: job)
                }
            }
            if !store.message.isEmpty {
                Text(store.message)
                    .font(.footnote)
                    .foregroundColor(.secondary)
            }
            if store.novels.isEmpty {
                Text("Пусто. Нажмите «+», чтобы найти новеллу на Syosetu или вставить ссылку на неё.")
                    .foregroundColor(.secondary)
            }
            ForEach(store.novels) { novel in
                NavigationLink(destination: NovelDetailView(ncode: novel.ncode)) {
                    row(novel)
                }
                .swipeActions(edge: .trailing, allowsFullSwipe: false) {
                    Button(role: .destructive) {
                        pendingDelete = novel
                    } label: {
                        Label("Удалить", systemImage: "trash")
                    }
                }
                .contextMenu {
                    Button(role: .destructive) {
                        pendingDelete = novel
                    } label: {
                        Label("Удалить", systemImage: "trash")
                    }
                }
            }
        }
        .navigationTitle("Чтение")
        .toolbar {
            ToolbarItem(placement: .navigationBarLeading) {
                Button {
                    showQueue = true
                } label: {
                    Image(systemName: "tray.full")
                }
            }
            ToolbarItem(placement: .navigationBarTrailing) {
                Button {
                    showAdd = true
                } label: {
                    Image(systemName: "plus")
                }
            }
        }
        .sheet(isPresented: $showAdd) {
            NovelAddSheet()
        }
        .sheet(isPresented: $showQueue) {
            MiningQueueView(video: nil)
        }
        .alert(pendingDelete.map { "Удалить «" + $0.title + "»?" } ?? "Удалить?",
               isPresented: Binding(get: { pendingDelete != nil }, set: { if !$0 { pendingDelete = nil } })) {
            Button("Удалить", role: .destructive) {
                if let novel = pendingDelete {
                    withAnimation(.easeInOut(duration: 0.35)) {
                        store.remove(novel.ncode)
                    }
                }
                pendingDelete = nil
            }
            Button("Отмена", role: .cancel) {
                pendingDelete = nil
            }
        } message: {
            Text("Скачанные главы и место чтения будут удалены.")
        }
        .onAppear {
            for novel in store.novels {
                analyzer.ensure(novel.ncode)
            }
        }
    }

    private func row(_ novel: NovelInfo) -> some View {
        let count = novel.episodes.count
        let saved = store.downloaded[novel.ncode]?.count ?? 0
        let read = novel.read.count
        let grade = analyzer.brief(novel.ncode, novel.episodes.map { $0.number })
        return VStack(alignment: .leading, spacing: 5) {
            Text(novel.title)
                .lineLimit(2)
            HStack(spacing: 8) {
                Text(novel.writer)
                    .lineLimit(1)
                Text("скачано " + String(saved) + " из " + String(count))
            }
            .font(.caption)
            .foregroundColor(.secondary)
            if let grade {
                AnalysisBadges(known: grade.known, difficulty: grade.difficulty)
            }
            if count > 0, read > 0 {
                ProgressView(value: Double(min(read, count)), total: Double(count))
                    .tint(.accentColor)
            }
        }
        .padding(.vertical, 2)
    }
}

/// A novel: the synopsis, downloads, the grade, and the volumes, folded except the one being read.
@available(iOS 16.0, *)
struct NovelDetailView: View {
    let ncode: String
    @ObservedObject private var store = NovelStore.shared
    @ObservedObject private var analyzer = NovelAnalyzer.shared
    @State private var showStory = false
    @State private var refreshing = false
    @State private var note = ""
    @State private var wordsOf: NovelWordsRequest? = nil
    @State private var expanded: Set<String> = []
    @State private var expansionReady = false

    private struct Volume: Identifiable {
        let id: String
        let title: String
        let episodes: [NovelEpisode]
    }

    /// The unknown words of an episode or the whole novel.
    struct NovelWordsRequest: Identifiable {
        let id = UUID()
        let title: String
        let numbers: [Int]
    }

    /// Episodes in order, grouped by their volume headings.
    private func volumes(_ novel: NovelInfo) -> [Volume] {
        var result: [Volume] = []
        for episode in novel.episodes {
            if let last = result.last, last.title == episode.volume {
                result[result.count - 1] = Volume(id: last.id, title: last.title, episodes: last.episodes + [episode])
            } else {
                result.append(Volume(id: "volume-" + String(result.count), title: episode.volume, episodes: [episode]))
            }
        }
        return result
    }

    var body: some View {
        if let novel = store.novel(ncode) {
            content(novel)
        } else {
            Text("Новелла удалена").foregroundColor(.secondary)
        }
    }

    /// The title of an episode without the author's runs of spaces.
    static func cleanTitle(_ title: String) -> String {
        title.split(whereSeparator: { $0.isWhitespace }).joined(separator: " ")
    }

    /// "author · finished · 286 гл." built in steps (one long expression is slow for the type checker)
    static func summary(_ novel: NovelInfo) -> String {
        let state: String = novel.finished ? "завершена" : "выходит"
        let count: String = String(novel.episodes.count) + " гл."
        return [novel.writer, state, count].filter { !$0.isEmpty }.joined(separator: " · ")
    }

    private func content(_ novel: NovelInfo) -> some View {
        let saved = store.downloaded[ncode] ?? []
        let missing = novel.episodes.map { $0.number }.filter { !saved.contains($0) }
        let next = novel.lastRead ?? novel.episodes.first?.number
        let allVolumes = volumes(novel)
        let grade = analyzer.brief(ncode, novel.episodes.map { $0.number })
        return ScrollViewReader { proxy in
            List {
                Section {
                    VStack(alignment: .leading, spacing: 6) {
                        Text(novel.title).font(.headline)
                        Text(NovelDetailView.summary(novel))
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                        if !novel.story.isEmpty {
                            Text(novel.story)
                                .font(.footnote)
                                .foregroundColor(.secondary)
                                .lineLimit(showStory ? nil : 3)
                                .onTapGesture {
                                    withAnimation { showStory.toggle() }
                                }
                        }
                    }
                    .padding(.vertical, 4)
                }
                Section {
                    if let next, let episode = novel.episodes.first(where: { $0.number == next }) {
                        NavigationLink(destination: NovelReaderView(ncode: ncode, number: next)) {
                            HStack(spacing: 12) {
                                Image(systemName: "book")
                                    .foregroundColor(.accentColor)
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(novel.lastRead == nil ? "Начать чтение" : "Продолжить")
                                        .font(.caption)
                                        .foregroundColor(.secondary)
                                    Text(NovelDetailView.cleanTitle(episode.title))
                                        .lineLimit(2)
                                }
                            }
                        }
                    }
                    NovelDownloadRow(ncode: ncode, missing: missing)
                    if !novel.shortStory {
                        Button {
                            refresh()
                        } label: {
                            Label(refreshing ? "Проверяю…" : "Проверить новые главы", systemImage: "arrow.clockwise")
                        }
                        .disabled(refreshing)
                    }
                    if !note.isEmpty {
                        Text(note).font(.footnote).foregroundColor(.secondary)
                    }
                } footer: {
                    Text("Главы скачиваются по одной, примерно раз в секунду, и потом читаются без интернета.")
                }
                Section {
                    // the counting shows in this row: a row coming and going would move the list under the finger
                    HStack(spacing: 8) {
                        Text("Новелла")
                        Spacer()
                        if analyzer.busy == ncode {
                            ProgressView()
                        }
                        if let grade {
                            AnalysisBadges(known: grade.known, difficulty: grade.difficulty)
                        } else if analyzer.busy != ncode {
                            Text("—").foregroundColor(.secondary)
                        }
                    }
                    if grade != nil {
                        Button {
                            wordsOf = NovelWordsRequest(title: novel.title, numbers: novel.episodes.map { $0.number })
                        } label: {
                            Label("Незнакомые слова новеллы", systemImage: "text.magnifyingglass")
                        }
                    }
                } header: {
                    Text("Сложность")
                } footer: {
                    Text("Считается по скачанным главам так же, как у серий: знакомые слова и понятные предложения. Том сворачивается нажатием на его название; свайп по главе → «Слова».")
                }
                ForEach(allVolumes) { volume in
                    Section {
                        if expanded.contains(volume.id) {
                            ForEach(volume.episodes) { episode in
                                NavigationLink(destination: NovelReaderView(ncode: ncode, number: episode.number)) {
                                    episodeRow(episode, saved: saved.contains(episode.number),
                                               read: novel.read.contains(episode.number))
                                }
                                .swipeActions(edge: .trailing, allowsFullSwipe: true) {
                                    if !saved.contains(episode.number) {
                                        Button {
                                            store.download(ncode, [episode.number])
                                        } label: {
                                            Label("Скачать", systemImage: "arrow.down.circle")
                                        }
                                        .tint(.accentColor)
                                    } else if analyzer.analysis(ncode, episode.number) != nil {
                                        Button {
                                            wordsOf = NovelWordsRequest(title: episode.title, numbers: [episode.number])
                                        } label: {
                                            Label("Слова", systemImage: "text.magnifyingglass")
                                        }
                                        .tint(.orange)
                                    }
                                }
                            }
                        }
                    } header: {
                        volumeHeader(volume, saved: saved)
                            .id(volume.id)
                    }
                }
            }
            .navigationTitle(novel.title)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Menu {
                        Button("Развернуть все тома") {
                            withAnimation { expanded = Set(allVolumes.map { $0.id }) }
                        }
                        Button("Свернуть все тома") {
                            withAnimation { expanded = [] }
                        }
                        if allVolumes.count > 1 {
                            Divider()
                            ForEach(allVolumes) { volume in
                                Button(volumeTitle(volume)) {
                                    jump(to: volume, proxy)
                                }
                            }
                        }
                    } label: {
                        Image(systemName: "list.bullet")
                    }
                }
            }
            .onAppear {
                guard !expansionReady else { return }
                expansionReady = true
                // the volume being read is open, the others are folded
                if let next, let current = allVolumes.first(where: { volume in
                    volume.episodes.contains { $0.number == next }
                }) {
                    expanded = [current.id]
                } else if let first = allVolumes.first {
                    expanded = [first.id]
                }
            }
        }
        .sheet(item: $wordsOf) { request in
            NavigationView {
                CatalogUnknownView(title: request.title, words: analyzer.unknown(ncode, request.numbers))
            }
        }
        .onAppear {
            analyzer.ensure(ncode)
        }
        .onChange(of: saved.count) { _ in
            analyzer.ensure(ncode)
        }
    }

    /// The volume opens, and the list goes to it.
    private func jump(to volume: Volume, _ proxy: ScrollViewProxy) {
        expanded.insert(volume.id)
        guard let first = volume.episodes.first?.number else { return }
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.15) {
            withAnimation {
                proxy.scrollTo(first, anchor: .top)
            }
        }
    }

    private func toggle(_ id: String) {
        withAnimation(.easeInOut(duration: 0.2)) {
            if expanded.contains(id) {
                expanded.remove(id)
            } else {
                expanded.insert(id)
            }
        }
    }

    private func volumeTitle(_ volume: Volume) -> String {
        let name: String = volume.title.isEmpty ? "Главы" : volume.title
        return name + " (" + String(volume.episodes.count) + ")"
    }

    private func volumeHeader(_ volume: Volume, saved: Set<Int>) -> some View {
        let missing = volume.episodes.map { $0.number }.filter { !saved.contains($0) }
        let grade = analyzer.brief(ncode, volume.episodes.map { $0.number })
        let open = expanded.contains(volume.id)
        return VStack(alignment: .leading, spacing: 4) {
            HStack(alignment: .firstTextBaseline) {
                Button {
                    toggle(volume.id)
                } label: {
                    HStack(alignment: .firstTextBaseline, spacing: 6) {
                        Image(systemName: open ? "chevron.down" : "chevron.right")
                            .font(.caption.bold())
                        Text(volume.title.isEmpty ? "Главы" : volume.title)
                            .lineLimit(2)
                            .multilineTextAlignment(.leading)
                        Text(String(volume.episodes.count))
                            .foregroundColor(.secondary)
                    }
                }
                .buttonStyle(.borderless)
                .foregroundColor(.primary)
                Spacer()
                if !missing.isEmpty {
                    Button("Скачать (" + String(missing.count) + ")") {
                        store.download(ncode, missing)
                    }
                    .font(.caption)
                    .buttonStyle(.borderless)
                }
            }
            if let grade {
                AnalysisBadges(known: grade.known, difficulty: grade.difficulty)
            }
        }
        .textCase(nil)
    }

    private func episodeRow(_ episode: NovelEpisode, saved: Bool, read: Bool) -> some View {
        HStack(spacing: 10) {
            VStack(alignment: .leading, spacing: 4) {
                Text(NovelDetailView.cleanTitle(episode.title))
                    .foregroundColor(read ? .secondary : .primary)
                    .lineLimit(2)
                if let analysis = analyzer.analysis(ncode, episode.number) {
                    AnalysisBadges(known: analysis.known, difficulty: analysis.difficulty)
                }
            }
            Spacer()
            Image(systemName: saved ? "checkmark.circle.fill" : "icloud.and.arrow.down")
                .foregroundColor(saved ? .accentColor : .secondary)
                .font(.footnote)
        }
    }

    private func refresh() {
        refreshing = true
        note = ""
        Task { @MainActor in
            defer { refreshing = false }
            let before = store.novel(ncode)?.episodes.count ?? 0
            do {
                try await store.refresh(ncode)
                let after = store.novel(ncode)?.episodes.count ?? 0
                note = after > before ? "Новых глав: " + String(after - before) : "Новых глав нет"
            } catch {
                note = "Не удалось проверить: нет связи с Syosetu"
            }
        }
    }
}

/// The reader: one episode, word lookup and mining (also into the mining queue), the exact place kept, the next
/// episode; the paragraphs read count in the statistics as they scroll past. It does not observe the stores: the
/// downloads and the analysis do not redraw the text.
@available(iOS 16.0, *)
struct NovelReaderView: View {
    let ncode: String
    @State private var number: Int
    private let store = NovelStore.shared
    @AppStorage("ykReaderFontSize") private var fontSize: Double = 19
    /// the novel when the episode opened
    @State private var info: NovelInfo? = nil
    @State private var text: NovelText? = nil
    @State private var failed = false
    @State private var lookup: ReaderLookup? = nil
    @State private var showSearch = false
    @State private var topParagraph = 0
    /// the id of the view at the top edge (iOS 17+)
    @State private var scrollID: Int? = nil
    @State private var countedUpTo = -1
    @State private var lastActivity = CACurrentMediaTime()
    @State private var lastTick = CACurrentMediaTime()
    @State private var pendingSeconds: Double = 0
    @State private var pendingCharacters = 0
    @State private var pendingSentences = 0
    @State private var pendingWords = 0
    @Environment(\.scenePhase) private var scenePhase
    private let ticker = Timer.publish(every: 5, on: .main, in: .common).autoconnect()

    init(ncode: String, number: Int) {
        self.ncode = ncode
        _number = State(initialValue: number)
    }

    private var novel: NovelInfo? {
        info ?? store.novel(ncode)
    }

    private var episodeIndex: Int? {
        novel?.episodes.firstIndex { $0.number == number }
    }

    var body: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(alignment: .leading, spacing: fontSize * 0.5) {
                    Color.clear.frame(height: 1).id(-1)
                    if let text {
                        if !text.chapter.isEmpty {
                            Text(text.chapter)
                                .font(.footnote)
                                .foregroundColor(.secondary)
                        }
                        Text(NovelDetailView.cleanTitle(text.title))
                            .font(.system(size: fontSize * 1.2, weight: .bold))
                            .padding(.bottom, fontSize * 0.6)
                        ForEach(Array(text.preface.enumerated()), id: \.offset) { offset, paragraph in
                            ReaderParagraph(text: paragraph, fontSize: fontSize * 0.88, secondary: true, onTap: open)
                                .id(-1000 - offset)
                        }
                        if !text.preface.isEmpty {
                            Divider().padding(.vertical, 8)
                        }
                        ForEach(Array(text.body.enumerated()), id: \.offset) { index, paragraph in
                            ReaderParagraph(text: paragraph, fontSize: fontSize, onTap: open)
                                .id(index)
                                .onAppear {
                                    reached(index, of: text)
                                }
                        }
                        if !text.afterword.isEmpty {
                            Divider().padding(.vertical, 8)
                        }
                        ForEach(Array(text.afterword.enumerated()), id: \.offset) { offset, paragraph in
                            ReaderParagraph(text: paragraph, fontSize: fontSize * 0.88, secondary: true, onTap: open)
                                .id(-2000 - offset)
                        }
                        navigation(proxy)
                    } else if failed {
                        VStack(spacing: 12) {
                            Text("Глава не скачана, а Syosetu сейчас недоступен.")
                                .foregroundColor(.secondary)
                            Button("Повторить") {
                                Task { await load(proxy) }
                            }
                        }
                        .frame(maxWidth: .infinity)
                        .padding(.top, 60)
                    } else {
                        ProgressView()
                            .frame(maxWidth: .infinity)
                            .padding(.top, 60)
                    }
                }
                .modifier(ReaderTargetLayout())
                .padding(.horizontal, 18)
                .padding(.vertical, 12)
                // with the dictionary open, a tap anywhere closes it
                .contentShape(Rectangle())
                .onTapGesture {
                    if lookup != nil {
                        lookup = nil
                    }
                }
            }
            .modifier(ReaderScrollPosition(id: $scrollID))
            .onChange(of: scrollID) { value in
                if let value, value >= 0 {
                    updateTop(value)
                }
            }
            .task(id: number) {
                await load(proxy)
            }
        }
        .navigationTitle(NovelDetailView.cleanTitle(novel?.episodes.first { $0.number == number }?.title ?? ""))
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItemGroup(placement: .navigationBarTrailing) {
                Button {
                    lookup = nil
                    showSearch = true
                } label: {
                    Image(systemName: "magnifyingglass")
                }
                Button {
                    fontSize = max(13, fontSize - 1)
                } label: {
                    Image(systemName: "textformat.size.smaller")
                }
                Button {
                    fontSize = min(32, fontSize + 1)
                } label: {
                    Image(systemName: "textformat.size.larger")
                }
            }
        }
        .sheet(item: $lookup) { item in
            WordLookupSheet(text: item.text, charAt: item.charAt)
        }
        .sheet(isPresented: $showSearch) {
            ReaderSearchSheet()
        }
        // back from AnkiMobile: the dictionary closes, the text stays where it was
        .onReceive(NotificationCenter.default.publisher(for: Notification.Name("yomikiri.ankiReturn"))) { _ in
            Task { @MainActor in
                for delay in [0.1, 0.4, 1.0] {
                    lookup = nil
                    showSearch = false
                    try? await Task.sleep(nanoseconds: UInt64(delay * 1_000_000_000))
                }
            }
        }
        .onReceive(ticker) { _ in
            tick()
        }
        .onAppear {
            prepareMining()
        }
        .onDisappear {
            if let text {
                countPassed(upTo: topParagraph, in: text)
            }
            saveState()
            flush(force: true)
            yomikiriOpenLinkHook = nil
            yomikiriQueuedWordsHook = nil
        }
    }

    private func navigation(_ proxy: ScrollViewProxy) -> some View {
        HStack {
            if let index = episodeIndex, index > 0, let previous = novel?.episodes[index - 1] {
                Button {
                    go(previous.number, proxy)
                } label: {
                    Label("Назад", systemImage: "chevron.left")
                }
            }
            Spacer()
            if let index = episodeIndex, let episodes = novel?.episodes, index + 1 < episodes.count {
                Button {
                    go(episodes[index + 1].number, proxy)
                } label: {
                    Label("Следующая", systemImage: "chevron.right")
                        .labelStyle(TrailingIconLabelStyle())
                }
                .buttonStyle(.borderedProminent)
            }
        }
        .padding(.vertical, 24)
    }

    /// A tap on a word opens the dictionary; with the dictionary open, it only closes it.
    private func open(_ item: ReaderLookup) {
        lastActivity = CACurrentMediaTime()
        if lookup != nil {
            lookup = nil
            return
        }
        lookup = item
    }

    /// The ⊕ of the dictionary: AnkiMobile, or the mining queue when it is on (Settings → Anki).
    private func prepareMining() {
        MiningFrame.jpegBase64 = nil
        yomikiriQueuedWordsHook = {
            MiningQueue.shared.entries.map { MiningQueue.statsWord(of: $0.url) }
        }
        let source = "Чтение: " + (novel?.title ?? ncode)
        yomikiriOpenLinkHook = { link in
            guard MiningFrame.isAddNote(link) else { return link }
            if UserDefaults.standard.bool(forKey: "ykMiningQueue") {
                MiningQueue.shared.add(link, video: source)
                UINotificationFeedbackGenerator().notificationOccurred(.success)
                return nil
            }
            return link
        }
    }

    private func go(_ next: Int, _ proxy: ScrollViewProxy) {
        if let text {
            countPassed(upTo: topParagraph, in: text)
        }
        saveState()
        text = nil
        topParagraph = 0
        number = next
        proxy.scrollTo(-1, anchor: .top)
    }

    private func load(_ proxy: ScrollViewProxy) async {
        failed = false
        do {
            let loaded = try await store.text(ncode, number)
            let current = number
            store.update(ncode) { $0.lastRead = current }
            info = store.novel(ncode)
            countedUpTo = info?.counted[number] ?? -1
            text = loaded
            // the paragraphs are tokenized ahead, so the words show at once
            let paragraphs = loaded.body
            Task.detached(priority: .utility) {
                for paragraph in paragraphs where !paragraph.isEmpty {
                    _ = SubtitleTokenCache.shared.tokens(paragraph)
                }
            }
            if let position = info?.positions[number], position > 0 {
                try? await Task.sleep(nanoseconds: 150_000_000)
                proxy.scrollTo(position, anchor: .top)
            }
        } catch {
            failed = true
        }
    }

    /// The paragraph at the top edge is the place to come back to.
    private func updateTop(_ first: Int) {
        guard first != topParagraph else { return }
        topParagraph = first
        lastActivity = CACurrentMediaTime()
        if let text, first - countedUpTo > 5 {
            countPassed(upTo: first, in: text)
        }
    }

    /// The paragraphs before `end` count in the statistics once (kept here, written to the novel when leaving).
    private func countPassed(upTo end: Int, in text: NovelText) {
        let start = countedUpTo + 1
        let stop = min(end, text.body.count)
        guard stop > start else { return }
        for paragraph in text.body[start ..< stop] where !paragraph.isEmpty {
            pendingCharacters += paragraph.filter { !$0.isWhitespace }.count
            pendingSentences += max(1, paragraph.filter { "。！？!?".contains($0) }.count)
            pendingWords += SubtitleTokenCache.shared.tokens(paragraph).filter { token in
                token.text.unicodeScalars.contains { CharacterSet.letters.contains($0) } && !token.pos.contains("記号")
            }.count
        }
        countedUpTo = stop - 1
    }

    /// The last paragraph marks the episode as read (a chapter in the statistics) and counts the rest of it.
    private func reached(_ index: Int, of text: NovelText) {
        lastActivity = CACurrentMediaTime()
        if #unavailable(iOS 17.0) {
            // without the exact position: about a screen above the deepest paragraph shown
            updateTop(max(0, index - 8))
        }
        guard index == text.body.count - 1 else { return }
        countPassed(upTo: text.body.count, in: text)
        if info?.read.contains(number) == false {
            let current = number
            store.update(ncode) { $0.read.insert(current) }
            info?.read.insert(current)
            ReadingStats.add(chapters: 1)
        }
    }

    /// The place and the counted paragraphs go to the novel (once, not on every line).
    private func saveState() {
        let current = number
        let top = topParagraph
        let counted = countedUpTo
        store.update(ncode) { novel in
            novel.positions[current] = top
            if counted >= 0 {
                novel.counted[current] = max(novel.counted[current] ?? -1, counted)
            }
        }
    }

    /// Reading time: while the app is open and the text was touched or scrolled in the last 90 s.
    private func tick() {
        let now = CACurrentMediaTime()
        let step = min(10, now - lastTick)
        lastTick = now
        if scenePhase == .active, text != nil, now - lastActivity < 90 {
            pendingSeconds += step
        }
        flush(force: false)
    }

    private func flush(force: Bool) {
        guard force || pendingSeconds >= 60 || pendingCharacters >= 2000 else { return }
        let seconds = Int(pendingSeconds.rounded())
        guard seconds > 0 || pendingCharacters > 0 else { return }
        ReadingStats.add(characters: pendingCharacters, sentences: pendingSentences, words: pendingWords, seconds: seconds)
        pendingSeconds = 0
        pendingCharacters = 0
        pendingSentences = 0
        pendingWords = 0
    }
}
