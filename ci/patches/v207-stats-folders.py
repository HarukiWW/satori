# v2.07: the statistics of the grammar, the live background in the reader, a folder's unknown words and subtitles.
# - «Статистика → Грамматика»: today (cards, time, «Снова», the kinds of answers, mature ones), the true retention
#   (young and mature, today … all time), the difficulty and the retrievability of the cards, for all the decks or
#   one. Every answer is kept for it (GrammarSave.log, with the time the card was on screen, at most a minute).
# - The live background in the chapters, dim and slower, so it does not get in the way; «Фон в читалке» turns it off.
# - The menu of a folder (long press or swipe): its unknown words, all its series taken as one text (the line shown is
#   the clearest one of all of them, with the frame and the sound of its series), and Jimaku for every video in it
#   that has no subtitles from it yet.
# - No more explanations under the sections anywhere (the settings lost them in 2.06); the attributions of Jiten and
#   Shikimori and the texts that say a state stay.
import pathlib
import re


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


here = pathlib.Path(__file__).resolve().parent
hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")

# --- explanations under the sections
literal = r"\"(?:[^\"\\\n]|\\.)*\""
footer = re.compile(r"\n(\s*)\} footer: \{[ \t]*\n\s*Text\((" + literal + r"(?:\s*\+\s*" + literal
                    + r")*|footerText\(\)|GrammarHome\.about)\)[ \t]*\n\s*\}")
kept = ("Jiten (jiten.moe)", "Shikimori")


def drop(match):
    if any(word in match.group(2) for word in kept):
        return match.group(0)
    return "\n" + match.group(1) + "}"


s, n = footer.subn(drop, s)
assert n == 17, "footers: " + str(n)

# --- grammar: every answer kept for the statistics
s = once(s, '''    /// the last level test of each level, percent
    var tests: [String: Int] = [:]
}
''', '''    /// the last level test of each level, percent
    var tests: [String: Int] = [:]
    /// every answer, for «Статистика → Грамматика» (since 2.07)
    var log: [GrammarReview]? = nil
}
''', "grammar log field")
s = once(s, '''    @Published private(set) var canUndo = false
''', '''    @Published private(set) var canUndo = false
    /// when the card on screen was shown: the time of the answer, for the statistics
    var shownAt: Date? = nil
''', "grammar shown at")
s = once(s, '''        save.cards[point.id] = card
        canUndo = true
        persist()
''', '''        save.cards[point.id] = card
        let seconds: Double = shownAt.map { min(max(now.timeIntervalSince($0), 0), 60) } ?? 0
        var log = save.log ?? []
        log.append(GrammarReview(time: now, id: point.id, grade: min(max(grade, 1), 4), state: old?.state ?? 0,
                                 interval: old?.interval ?? 0, seconds: seconds))
        // a very long history loses its oldest answers
        if log.count > 50_000 {
            log.removeFirst(log.count - 50_000)
        }
        save.log = log
        shownAt = nil
        canUndo = true
        persist()
''', "grammar answer log")
s = once(s, '''        save.cards[step.id] = step.card
        save.newToday = step.newToday
''', '''        save.cards[step.id] = step.card
        if save.log?.last?.id == step.id {
            save.log?.removeLast()
        }
        save.newToday = step.newToday
''', "grammar undo log")
s = once(s, '''    private func show(_ point: GrammarPoint) {
        current = point
        shown = false
''', '''    private func show(_ point: GrammarPoint) {
        current = point
        shown = false
        store.shownAt = Date()
''', "grammar shown")

# --- «Статистика»: the third mode
s = once(s, '''                Picker("Период", selection: $period) {
                    Text("Сегодня").tag(0)
                    Text("7 дней").tag(1)
                    Text("Всё время").tag(2)
                }
                .pickerStyle(.segmented)
''', '''                if mode != 2 {
                    Picker("Период", selection: $period) {
                        Text("Сегодня").tag(0)
                        Text("7 дней").tag(1)
                        Text("Всё время").tag(2)
                    }
                    .pickerStyle(.segmented)
                }
''', "stats period")
s = once(s, '''                    Text("Чтение").tag(0)
                    Text("Просмотр").tag(1)
                }
                .pickerStyle(.segmented)
''', '''                    Text("Чтение").tag(0)
                    Text("Просмотр").tag(1)
                    Text("Грамматика").tag(2)
                }
                .pickerStyle(.segmented)
''', "stats mode")
first_grid = '''                LazyVGrid(
                    columns: [GridItem(.flexible(), spacing: 12), GridItem(.flexible(), spacing: 12)],
                    spacing: 12
                ) {
                    StatCard(title: "Слов в Anki", value: statNumber(s.minedWords))'''
s = once(s, first_grid, '''                if mode == 2 {
                    if #available(iOS 16.0, *) {
                        GrammarStatsView()
                    }
                } else {
''' + first_grid, "stats grammar branch")
s = once(s, '''                    Text("Сбросить статистику")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.bordered)
            }
''', '''                    Text("Сбросить статистику")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.bordered)
                }
            }
''', "stats branch end")
s = once(s, '''            .padding(16)
        }
        .sheet(isPresented: $showMined, onDismiss: { model.reload() }) {''', '''            .padding(16)
            .animation(.easeInOut(duration: 0.25), value: mode)
        }
        .sheet(isPresented: $showMined, onDismiss: { model.reload() }) {''', "stats mode animation")

# --- the live background: dimmer and slower where asked (the reader)
s = once(s, '''    /// only the background on screen is drawn (every tab has its own)
    @State private var visible = false
''', '''    /// only the background on screen is drawn (every tab has its own)
    @State private var visible = false
    /// how bright the letters are and how often they move (the reader dims them under its text)
    let dim: Double
    let fps: Double

    init(dim: Double = 1, fps: Double = 30) {
        self.dim = dim
        self.fps = fps
    }
''', "backdrop dim")
s = once(s, "TimelineView(.animation(minimumInterval: 1.0 / 30, paused:",
         "TimelineView(.animation(minimumInterval: 1.0 / fps, paused:", "backdrop fps")
s = once(s, '''                ctx.opacity = level
                ctx.draw(symbol, at: CGPoint(x: x, y: y))''', '''                ctx.opacity = level * dim
                ctx.draw(symbol, at: CGPoint(x: x, y: y))''', "backdrop opacity")
s = once(s, '''    @State private var showSearch = false
    @AppStorage("ykReaderFurigana") private var furigana = true
''', '''    @State private var showSearch = false
    @AppStorage("ykReaderFurigana") private var furigana = true
    @AppStorage("ykReaderBackdrop") private var readerBackdrop = true
''', "reader backdrop setting")
s = once(s, '''        .navigationTitle(NovelDetailView.cleanTitle(novel?.episodes.first { $0.number == number }?.title ?? ""))
        .navigationBarTitleDisplayMode(.inline)
''', '''        .navigationTitle(NovelDetailView.cleanTitle(novel?.episodes.first { $0.number == number }?.title ?? ""))
        .navigationBarTitleDisplayMode(.inline)
        .background {
            if readerBackdrop {
                SatoriBackdrop(dim: 0.4, fps: 20)
            }
        }
''', "reader backdrop")
s = once(s, '''    @AppStorage("ykBackdropSpeed") private var backdropSpeed = 1.0
    /// words imported from Anki decks''', '''    @AppStorage("ykBackdropSpeed") private var backdropSpeed = 1.0
    @AppStorage("ykReaderBackdrop") private var readerBackdrop = true
    /// words imported from Anki decks''', "settings reader backdrop")
s = once(s, '''                Toggle("Живой фон", isOn: $backdrop)
                if backdrop {
''', '''                Toggle("Живой фон", isOn: $backdrop)
                if backdrop {
                    Toggle("Фон в читалке", isOn: $readerBackdrop)
''', "settings reader toggle")

# --- the unknown words of a folder
s = once(s, '''struct UnknownWordsView: View {
    let video: URL
''', '''struct UnknownWordsView: View {
    let video: URL
    /// a folder: the list is of all its series (`video` is the folder)
    var folderVideos: [URL] = []
''', "words folder")
s = once(s, '''    private func open(_ word: UnknownWord) {
        guard preparing == nil else { return }
''', '''    private func open(_ word: UnknownWord) {
        guard preparing == nil else { return }
        if !folderVideos.isEmpty {
            openInFolder(word)
            return
        }
''', "words open folder")
s = once(s, '''    private func load() async {
        guard let file = VideoLibraryStore.jimakuFile(for: video) else {
            loading = false
            return
        }
''', '''    /// In a folder: the clearest line of all its series, with the frame and the sound of that series.
    private func openInFolder(_ word: UnknownWord) {
        let pairs: [(video: URL, file: URL)] = folderVideos.compactMap { video in
            VideoLibraryStore.jimakuFile(for: video).map { (video: video, file: $0) }
        }
        preparing = word.word
        Task { @MainActor in
            let index = await library.knownWordsIndex()
            let level = VideoLibraryStore.userLevel
            let judge = WordKnowledge(index: index, level: level, vocabulary: VideoLibraryStore.vocabulary(level: level))
            let target = word.word
            let found = await Task.detached(priority: .userInitiated) {
                ListMining.bestLine(for: target, in: pairs, judge: judge)
            }.value
            if let found {
                await ListMining.prepare(video: found.video, line: found.line)
                QueueMiningHooks.queue(into: VideoKey.of(found.video))
                lineLookup = LineLookup(text: found.line.text, charAt: found.line.charAt)
            } else {
                MiningFrame.jpegBase64 = nil
                lookup = word
            }
            preparing = nil
        }
    }

    private func load() async {
        if !folderVideos.isEmpty {
            let files = folderVideos.compactMap { VideoLibraryStore.jimakuFile(for: $0) }
            if !files.isEmpty {
                let index = await library.knownWordsIndex()
                let level = VideoLibraryStore.userLevel
                let vocabulary = VideoLibraryStore.vocabulary(level: level)
                analysis = await Task.detached(priority: .userInitiated) {
                    VideoLibraryStore.analyze(files: files, index: index, level: level, vocabulary: vocabulary)
                }.value
            }
            loading = false
            return
        }
        guard let file = VideoLibraryStore.jimakuFile(for: video) else {
            loading = false
            return
        }
''', "words load folder")
s = once(s, '''                    Text("У этой серии нет субтитров Jimaku.")''', '''                    Text(folderVideos.isEmpty ? "У этой серии нет субтитров Jimaku."
                         : "В этой папке нет видео с субтитрами Jimaku.")''', "words empty")
s = once(s, '''            .navigationTitle(video.deletingPathExtension().lastPathComponent)''',
         '''            .navigationTitle(folderVideos.isEmpty ? video.deletingPathExtension().lastPathComponent : video.lastPathComponent)''',
         "words title")
s = once(s, '''    static func bestLine(for word: String, file: URL, judge: WordKnowledge) -> Line? {
        guard let first = word.first else { return nil }''', '''    static func bestLine(for word: String, file: URL, judge: WordKnowledge) -> Line? {
        scoredLine(for: word, file: file, judge: judge)?.line
    }

    /// The clearest line with the word in a file, and its score (lower is clearer).
    static func scoredLine(for word: String, file: URL, judge: WordKnowledge) -> (score: Double, line: Line)? {
        guard let first = word.first else { return nil }''', "scored line")
s = once(s, '''        return best?.line
    }''', '''        return best
    }''', "scored line return")

# --- the menu of a folder in the video list
s = once(s, '''    @State private var wordsVideo: URL? = nil
''', '''    @State private var wordsVideo: URL? = nil
    @State private var wordsFolder: URL? = nil
''', "list folder words state")
s = once(s, '''                            .tint(.orange)
                        }
                    }
                    .contextMenu {
                        if !item.isFolder && VideoLibraryStore.isVideo(item.url.lastPathComponent) {''', '''                            .tint(.orange)
                        } else {
                            Button {
                                wordsFolder = item.url
                            } label: {
                                Label("Слова", systemImage: "text.magnifyingglass")
                            }
                            .tint(.orange)
                        }
                    }
                    .contextMenu {
                        if item.isFolder {
                            Button {
                                library.findSubtitles(inFolder: item.url)
                            } label: {
                                Label("Найти субтитры для всех видео", systemImage: "captions.bubble")
                            }
                            Button {
                                wordsFolder = item.url
                            } label: {
                                Label("Незнакомые слова", systemImage: "text.magnifyingglass")
                            }
                        }
                        if !item.isFolder && VideoLibraryStore.isVideo(item.url.lastPathComponent) {''', "list folder menu")
s = once(s, '''        .sheet(isPresented: Binding(get: { wordsVideo != nil }, set: { if !$0 { wordsVideo = nil } })) {
            if let video = wordsVideo {
                UnknownWordsView(video: video, library: library)
            }
        }
''', '''        .sheet(isPresented: Binding(get: { wordsVideo != nil }, set: { if !$0 { wordsVideo = nil } })) {
            if let video = wordsVideo {
                UnknownWordsView(video: video, library: library)
            }
        }
        .sheet(isPresented: Binding(get: { wordsFolder != nil }, set: { if !$0 { wordsFolder = nil } })) {
            if let folder = wordsFolder {
                UnknownWordsView(video: folder, folderVideos: VideoLibraryStore.videos(in: folder), library: library)
            }
        }
''', "list folder sheet")

s = s.rstrip("\n") + "\n" + (here / "v207-stats-folders.swift").read_text(encoding="utf-8")
hv.write_text(s, encoding="utf-8")
print("v2.07 statistics and folders applied")
