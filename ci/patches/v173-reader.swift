
// MARK: - Reading v1.73: analysis of novels, volume jump, precise place, queue, statistics while reading

/// The analysis of any lines (subtitle cues, sentences of a novel): known words, clear lines, unknown words, by the
/// rules of WordKnowledge. A clear line has at most one unknown word.
@available(iOS 16.0, *)
enum TextAnalysis {
    static func analyze(lines: [String], index: KnownWordsIndex, level: Int, vocabulary: Int) -> EpisodeAnalysis? {
        let judge = WordKnowledge(index: index, level: level, vocabulary: vocabulary)
        var words = 0
        var knownWords = 0
        var lineCount = 0
        var clearLines = 0
        var unknownCounts: [String: Int] = [:]
        for text in lines {
            guard !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { continue }
            let tokens = autoreleasepool { NativeLookup.tokenize(text, charAt: 0).tokens }
            var lineWords = 0
            var lineUnknown = 0
            for token in tokens where WordKnowledge.counted(token) {
                lineWords += 1
                if judge.known(token) {
                    continue
                }
                lineUnknown += 1
                let base = token.base.isEmpty ? token.text : token.base
                unknownCounts[base, default: 0] += 1
            }
            guard lineWords > 0 else { continue }
            words += lineWords
            knownWords += lineWords - lineUnknown
            lineCount += 1
            if lineUnknown <= 1 {
                clearLines += 1
            }
        }
        guard words > 0, lineCount > 0 else { return nil }
        let knownShare = Double(knownWords) / Double(words)
        let clear = Double(clearLines) / Double(lineCount)
        let difficulty: Int? = words >= 50 ? VideoLibraryStore.classify(known: knownShare, clear: clear) : nil
        var list: [UnknownWord] = []
        for (word, count) in unknownCounts {
            list.append(UnknownWord(word: word, reading: judge.reading(of: word), count: count))
        }
        list.sort { first, second in
            first.count != second.count ? first.count > second.count : first.word < second.word
        }
        return EpisodeAnalysis(coverage: Int((knownShare * 100).rounded()), difficulty: difficulty,
                               knownShare: knownShare, clearShare: clear, words: words, lines: lineCount, unknown: list)
    }
}

/// The analysis of one episode of a novel.
struct NovelEpisodeAnalysis: Codable {
    let known: Double
    let clear: Double
    let words: Int
    let lines: Int
    let difficulty: Int?
    let unknown: [CatalogUnknown]
}

/// All analysed episodes of a novel, with what they were counted against.
struct NovelAnalysisFile: Codable {
    let knownWords: UInt64
    let level: Int
    let vocabulary: Int
    var episodes: [Int: NovelEpisodeAnalysis]
}

/// Difficulty and coverage of the downloaded episodes, counted in the background (like the episodes of the videos);
/// a volume and a novel are the average of their episodes, weighted by words and lines.
@available(iOS 16.0, *)
@MainActor
final class NovelAnalyzer: ObservableObject {
    static let shared = NovelAnalyzer()

    @Published private(set) var episodes: [String: [Int: NovelEpisodeAnalysis]] = [:]
    @Published private(set) var busy: String? = nil
    private var queue: [String] = []
    private var worker: Task<Void, Never>? = nil

    private static func file(_ ncode: String) -> URL {
        FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("Novels").appendingPathComponent(ncode).appendingPathComponent("analysis.json")
    }

    private static func load(_ ncode: String) -> NovelAnalysisFile? {
        guard let data = try? Data(contentsOf: file(ncode)) else { return nil }
        return try? JSONDecoder().decode(NovelAnalysisFile.self, from: data)
    }

    private static func save(_ analysis: NovelAnalysisFile, _ ncode: String) {
        if let data = try? JSONEncoder().encode(analysis) {
            try? data.write(to: file(ncode))
        }
    }

    func analysis(_ ncode: String, _ number: Int) -> NovelEpisodeAnalysis? {
        episodes[ncode]?[number]
    }

    /// The share and the grade of several episodes (no word list: quick enough for every redraw).
    func brief(_ ncode: String, _ numbers: [Int]) -> (known: Double, difficulty: Int?)? {
        guard let saved = episodes[ncode] else { return nil }
        var words = 0
        var lines = 0
        var known = 0.0
        var clear = 0.0
        for number in numbers {
            guard let part = saved[number] else { continue }
            words += part.words
            lines += part.lines
            known += part.known * Double(part.words)
            clear += part.clear * Double(part.lines)
        }
        guard words > 0, lines > 0 else { return nil }
        let knownShare = known / Double(words)
        let clearShare = clear / Double(lines)
        let difficulty: Int? = words >= 50 ? VideoLibraryStore.classify(known: knownShare, clear: clearShare) : nil
        return (knownShare, difficulty)
    }

    /// The unknown words of several episodes, most frequent first.
    func unknown(_ ncode: String, _ numbers: [Int]) -> [CatalogUnknown] {
        guard let saved = episodes[ncode] else { return [] }
        var counts: [String: CatalogUnknown] = [:]
        for number in numbers {
            for word in saved[number]?.unknown ?? [] {
                let old = counts[word.word]
                counts[word.word] = CatalogUnknown(word: word.word, kana: old?.kana ?? word.kana,
                                                   count: (old?.count ?? 0) + word.count)
            }
        }
        let list = counts.values.sorted { $0.count > $1.count }
        return Array(list.prefix(500))
    }

    /// The downloaded episodes of a novel that have no analysis yet.
    func ensure(_ ncode: String) {
        if busy != ncode, !queue.contains(ncode) {
            queue.append(ncode)
        }
        start()
    }

    private func start() {
        guard worker == nil, !queue.isEmpty else { return }
        worker = Task { @MainActor in
            while !queue.isEmpty {
                let ncode = queue.removeFirst()
                busy = ncode
                await analyze(ncode)
                busy = nil
            }
            worker = nil
        }
    }

    /// Sentences of paragraphs: a line of the analysis is a sentence (closing brackets stay with it).
    nonisolated static func sentences(_ paragraphs: [String]) -> [String] {
        let ends: Set<Character> = ["。", "！", "？", "!", "?"]
        let closers: Set<Character> = ["」", "』", "）", ")", "】"]
        var result: [String] = []
        for paragraph in paragraphs {
            let letters = Array(paragraph)
            var current = ""
            var i = 0
            while i < letters.count {
                current.append(letters[i])
                if ends.contains(letters[i]) {
                    while i + 1 < letters.count, closers.contains(letters[i + 1]) {
                        i += 1
                        current.append(letters[i])
                    }
                    if !current.trimmingCharacters(in: .whitespaces).isEmpty {
                        result.append(current)
                    }
                    current = ""
                }
                i += 1
            }
            if !current.trimmingCharacters(in: .whitespaces).isEmpty {
                result.append(current)
            }
        }
        return result
    }

    private func analyze(_ ncode: String) async {
        let store = NovelStore.shared
        let saved = store.downloaded[ncode] ?? []
        guard !saved.isEmpty else { return }
        let level = VideoLibraryStore.userLevel
        let vocabulary = VideoLibraryStore.vocabulary(level: level)
        let index = await CatalogStore.knownIndex()
        var current: NovelAnalysisFile
        if let loaded = NovelAnalyzer.load(ncode), loaded.knownWords == index.fingerprint, loaded.level == level,
           loaded.vocabulary == vocabulary {
            current = loaded
        } else {
            current = NovelAnalysisFile(knownWords: index.fingerprint, level: level, vocabulary: vocabulary, episodes: [:])
        }
        episodes[ncode] = current.episodes
        var unsaved = 0
        for number in saved.sorted() where current.episodes[number] == nil {
            guard store.novel(ncode) != nil else { return }
            guard let text = try? await store.text(ncode, number) else { continue }
            let lines = NovelAnalyzer.sentences(text.body)
            let result = await Task.detached(priority: .utility) {
                TextAnalysis.analyze(lines: lines, index: index, level: level, vocabulary: vocabulary)
            }.value
            guard let result else { continue }
            var unknown: [CatalogUnknown] = []
            for word in result.unknown.prefix(200) {
                unknown.append(CatalogUnknown(word: word.word, kana: word.reading, count: word.count))
            }
            let entry = NovelEpisodeAnalysis(known: result.knownShare, clear: result.clearShare, words: result.words,
                                             lines: result.lines, difficulty: result.difficulty, unknown: unknown)
            current.episodes[number] = entry
            episodes[ncode, default: [:]][number] = entry
            unsaved += 1
            if unsaved >= 10 {
                NovelAnalyzer.save(current, ncode)
                unsaved = 0
            }
        }
        if store.novel(ncode) != nil {
            NovelAnalyzer.save(current, ncode)
        }
    }
}

/// The grade and the share of known words, like the badges of the videos.
@available(iOS 16.0, *)
struct AnalysisBadges: View {
    let known: Double
    let difficulty: Int?

    /// green at 100 %, yellow at 55 %, red at 0 %
    static func coverageColor(_ share: Double) -> Color {
        let v = min(max(share * 100, 0), 100)
        var hue: Double = 0.15 * v / 55
        if v >= 55 {
            hue = 0.15 + 0.18 * (v - 55) / 45
        }
        return Color(hue: hue, saturation: 0.75, brightness: 0.88)
    }

    var body: some View {
        HStack(spacing: 6) {
            if let difficulty {
                Text(CatalogStore.difficultyName(difficulty))
                    .font(.caption2.bold())
                    .foregroundColor(difficulty == 2 ? .white : .black)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(CatalogStore.difficultyColor(difficulty).opacity(0.85))
                    .cornerRadius(4)
            }
            Text(CatalogStore.percent(known))
                .font(.caption2.bold())
                .foregroundColor(.black)
                .padding(.horizontal, 6)
                .padding(.vertical, 2)
                .background(AnalysisBadges.coverageColor(known))
                .cornerRadius(4)
        }
    }
}

/// The saved novels.
@available(iOS 16.0, *)
struct NovelLibraryView: View {
    @ObservedObject private var store = NovelStore.shared
    @ObservedObject private var analyzer = NovelAnalyzer.shared
    @State private var showAdd = false
    @State private var showQueue = false
    @State private var pendingDelete: NovelInfo? = nil

    var body: some View {
        List {
            if let job = store.job {
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

/// A novel: the synopsis, downloads, the grade, and the table of contents by volumes with a jump to any volume.
@available(iOS 16.0, *)
struct NovelDetailView: View {
    let ncode: String
    @ObservedObject private var store = NovelStore.shared
    @ObservedObject private var analyzer = NovelAnalyzer.shared
    @State private var showStory = false
    @State private var refreshing = false
    @State private var note = ""
    @State private var wordsOf: NovelWordsRequest? = nil

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

    static func continueTitle(_ novel: NovelInfo, _ episode: NovelEpisode) -> String {
        let action: String = novel.lastRead == nil ? "Начать: " : "Продолжить: "
        return action + episode.title
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
                            Label(NovelDetailView.continueTitle(novel, episode), systemImage: "book")
                                .lineLimit(1)
                        }
                    }
                    if let job = store.job, job.ncode == ncode {
                        NovelJobRow(job: job)
                    } else if !missing.isEmpty {
                        Button {
                            store.download(ncode, missing)
                        } label: {
                            Label("Скачать всё (" + String(missing.count) + " гл.)", systemImage: "arrow.down.circle")
                        }
                    } else {
                        Label("Все главы скачаны", systemImage: "checkmark.circle")
                            .foregroundColor(.secondary)
                    }
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
                    HStack {
                        Text("Новелла")
                        Spacer()
                        if let grade {
                            AnalysisBadges(known: grade.known, difficulty: grade.difficulty)
                        } else {
                            Text("—").foregroundColor(.secondary)
                        }
                    }
                    if analyzer.busy == ncode {
                        HStack(spacing: 10) {
                            ProgressView()
                            Text("Считаю скачанные главы…").foregroundColor(.secondary)
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
                    Text("Считается по скачанным главам так же, как у серий: знакомые слова и понятные предложения. У каждой главы и тома — своя оценка; свайп по главе → «Слова».")
                }
                ForEach(allVolumes) { volume in
                    Section {
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
                    } header: {
                        volumeHeader(volume, saved: saved)
                    }
                }
            }
            .navigationTitle(novel.title)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    if allVolumes.count > 1 {
                        Menu {
                            ForEach(allVolumes) { volume in
                                Button(volumeTitle(volume)) {
                                    if let first = volume.episodes.first {
                                        withAnimation {
                                            proxy.scrollTo(first.number, anchor: .top)
                                        }
                                    }
                                }
                            }
                        } label: {
                            Image(systemName: "list.bullet")
                        }
                    }
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

    private func volumeTitle(_ volume: Volume) -> String {
        let name: String = volume.title.isEmpty ? "Главы" : volume.title
        return name + " (" + String(volume.episodes.count) + ")"
    }

    private func volumeHeader(_ volume: Volume, saved: Set<Int>) -> some View {
        let missing = volume.episodes.map { $0.number }.filter { !saved.contains($0) }
        let grade = analyzer.brief(ncode, volume.episodes.map { $0.number })
        return VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(volume.title.isEmpty ? "Главы" : volume.title)
                    .lineLimit(2)
                Spacer()
                if !missing.isEmpty {
                    Button("Скачать том (" + String(missing.count) + ")") {
                        store.download(ncode, missing)
                    }
                    .font(.caption)
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
                Text(episode.title)
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

/// iOS 17+: the paragraph at the top edge of the reader is reported exactly (the ids of the paragraphs).
@available(iOS 16.0, *)
private struct ReaderScrollPosition: ViewModifier {
    @Binding var id: Int?

    func body(content: Content) -> some View {
        if #available(iOS 17.0, *) {
            content.scrollPosition(id: $id, anchor: .top)
        } else {
            content
        }
    }
}

@available(iOS 16.0, *)
private struct ReaderTargetLayout: ViewModifier {
    func body(content: Content) -> some View {
        if #available(iOS 17.0, *) {
            content.scrollTargetLayout()
        } else {
            content
        }
    }
}

/// The reader: one episode, word lookup and mining (also into the mining queue), the exact place kept, the next
/// episode; the paragraphs read count in the statistics as they scroll past.
@available(iOS 16.0, *)
struct NovelReaderView: View {
    let ncode: String
    @State private var number: Int
    @ObservedObject private var store = NovelStore.shared
    @AppStorage("ykReaderFontSize") private var fontSize: Double = 19
    @State private var text: NovelText? = nil
    @State private var failed = false
    @State private var lookup: ReaderLookup? = nil
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
        store.novel(ncode)
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
                        Text(text.title)
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
        .navigationTitle(novel?.episodes.first { $0.number == number }?.title ?? "")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItemGroup(placement: .navigationBarTrailing) {
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
        // back from AnkiMobile: the dictionary closes, the text stays where it was
        .onReceive(NotificationCenter.default.publisher(for: Notification.Name("yomikiri.ankiReturn"))) { _ in
            Task { @MainActor in
                for delay in [0.1, 0.4, 1.0] {
                    lookup = nil
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
            savePosition()
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
        savePosition()
        text = nil
        topParagraph = 0
        number = next
        proxy.scrollTo(-1, anchor: .top)
    }

    private func load(_ proxy: ScrollViewProxy) async {
        failed = false
        do {
            let loaded = try await store.text(ncode, number)
            text = loaded
            countedUpTo = novel?.counted[number] ?? -1
            store.update(ncode) { $0.lastRead = number }
            // the paragraphs are tokenized ahead, so the words show at once
            let paragraphs = loaded.body
            Task.detached(priority: .utility) {
                for paragraph in paragraphs where !paragraph.isEmpty {
                    _ = SubtitleTokenCache.shared.tokens(paragraph)
                }
            }
            if let position = novel?.positions[number], position > 0 {
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
        // the statistics take the paragraphs above in groups (the info file is not written on every line)
        if let text, first - countedUpTo > 5 {
            countPassed(upTo: first, in: text)
        }
    }

    /// The paragraphs before `end` count in the statistics once.
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
        let current = number
        let last = countedUpTo
        store.update(ncode) { $0.counted[current] = last }
    }

    /// The last paragraph marks the episode as read and counts the rest of it.
    private func reached(_ index: Int, of text: NovelText) {
        lastActivity = CACurrentMediaTime()
        if #unavailable(iOS 17.0) {
            // without the exact position: about a screen above the deepest paragraph shown
            updateTop(max(0, index - 8))
        }
        guard index == text.body.count - 1 else { return }
        countPassed(upTo: text.body.count, in: text)
        if novel?.read.contains(number) == false {
            store.update(ncode) { $0.read.insert(number) }
        }
    }

    private func savePosition() {
        let current = number
        let top = topParagraph
        store.update(ncode) { $0.positions[current] = top }
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

