# v1.57: one analysis of an episode for the coverage and the difficulty. Known words: the cards in any form, the JLPT
# words up to the user's level, and the most frequent words (Jiten) up to the vocabulary size of that level. Proper
# nouns, numbers and interjections no longer count. The unknown words of an episode can be seen (tap on the difficulty
# badge, or swipe "Слова").
import pathlib

hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


# ---------- the detailed part of speech (固有名詞, 数詞) ----------
s = once(s, '    var pos: String = ""\n}\n\nstruct LookupEntry', '    var pos: String = ""\n    var pos2: String = ""\n}\n\nstruct LookupEntry', "pos2 field")
s = once(s, '                                      pos: t["pos"] as? String ?? ""))',
         '                                      pos: t["pos"] as? String ?? "",\n'
         '                                      pos2: t["pos2"] as? String ?? ""))', "pos2 parse")

# ---------- the analysis ----------
a = s.index("    nonisolated static func coverage(of file: URL, index: KnownWordsIndex) -> Int? {")
b = s.index("    private static let videoExtensions", a)
s = s[:a] + '''    static var userLevel: Int {
        let saved = UserDefaults.standard.integer(forKey: "ykUserLevel")
        return (1 ... 5).contains(saved) ? saved : 5
    }

    static func jimakuFile(for video: URL) -> URL? {
        let base = video.deletingPathExtension()
        for ext in ["srt", "ass", "ssa", "vtt"] {
            let file = base.appendingPathExtension("jimaku." + ext)
            if FileManager.default.fileExists(atPath: file.path) {
                return file
            }
        }
        return nil
    }

    /// One pass over the subtitles. Content words only: no particles, auxiliaries, symbols, interjections, proper
    /// nouns, numbers or katakana-only words (names, loanwords). A word is known when it is among the cards in any
    /// form, in the JLPT lists up to the level, or among the most frequent words (Jiten) up to the vocabulary of the level.
    nonisolated static func analyze(of file: URL, index: KnownWordsIndex, level: Int) -> EpisodeAnalysis? {
        // about how many of the most frequent words are known at each JLPT level
        let vocabularyByLevel: [Int: Int] = [5: 800, 4: 1500, 3: 3700, 2: 6000, 1: 10000]
        let vocabulary: Int = vocabularyByLevel[level] ?? 800
        var total = 0
        var familiar = 0
        var lines = 0
        var clearLines = 0
        var readings: [String: String] = [:]
        var unknownCounts: [String: UnknownWord] = [:]
        for cue in EmbeddedSubtitles.cues(fromFile: file) {
            guard !cue.text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { continue }
            let tokens = autoreleasepool { NativeLookup.tokenize(cue.text, charAt: 0).tokens }
            var words = 0
            var unknown = 0
            for token in tokens {
                guard token.text.unicodeScalars.contains(where: { CharacterSet.letters.contains($0) }) else { continue }
                if token.pos.hasPrefix("助詞") || token.pos.hasPrefix("助動詞") || token.pos.contains("記号") { continue }
                if token.pos.hasPrefix("感動詞") || token.pos2.contains("固有名詞") || token.pos2.contains("数詞") { continue }
                if KnownWordsIndex.isKatakana(token.text) { continue }
                words += 1
                let base = token.base.isEmpty ? token.text : token.base
                if index.forms.contains(base) || index.forms.contains(token.text) { continue }
                let reading: String
                if let saved = readings[base] {
                    reading = saved
                } else {
                    reading = KnownWordsIndex.isKana(base) ? HighlightData.hiragana(base) : autoreleasepool {
                        HighlightData.hiragana(NativeLookup.tokenize(base, charAt: 0).tokens.map { $0.reading }.joined())
                    }
                    readings[base] = reading
                }
                if !reading.isEmpty {
                    if index.kanaReadings.contains(reading) { continue }
                    if let kanji = index.kanjiByReading[reading],
                       KnownWordsIndex.isKana(token.text) || !kanji.isDisjoint(with: KnownWordsIndex.kanji(base)) { continue }
                }
                let lookupReading = reading.isEmpty ? HighlightData.hiragana(token.reading) : reading
                let jlpt = HighlightData.jlptLevel(base: base, reading: lookupReading)
                if jlpt > 0, jlpt >= level { continue }
                let rank = HighlightData.rank(base: base, reading: lookupReading, dict: "main", text: token.text)
                    ?? HighlightData.rank(base: base, reading: "", dict: "main", text: token.text)
                if let rank, rank <= vocabulary { continue }
                unknown += 1
                let count = (unknownCounts[base]?.count ?? 0) + 1
                unknownCounts[base] = UnknownWord(word: base, reading: lookupReading, count: count)
            }
            guard words > 0 else { continue }
            total += words
            familiar += words - unknown
            lines += 1
            if unknown <= 1 {
                clearLines += 1
            }
        }
        guard total > 0, lines > 0 else { return nil }
        let known = Double(familiar) / Double(total)
        let clear = Double(clearLines) / Double(lines)
        var difficulty: Int? = nil
        if total >= 50 {
            if known >= 0.90 && clear >= 0.65 {
                difficulty = 0
            } else if known >= 0.80 && clear >= 0.40 {
                difficulty = 1
            } else {
                difficulty = 2
            }
        }
        let list = unknownCounts.values.sorted { first, second in
            first.count != second.count ? first.count > second.count : first.word < second.word
        }
        return EpisodeAnalysis(coverage: Int((known * 100).rounded()), difficulty: difficulty, knownShare: known,
                               clearShare: clear, words: total, lines: lines, unknown: list)
    }

    /// The known word index, built once for a number of known words.
    func knownWordsIndex() async -> KnownWordsIndex {
        let known = HighlightData.minedWords()
        // the JLPT and frequency tables are loaded here, on the main thread
        _ = HighlightData.jlptLevel(base: "の", reading: "の")
        _ = HighlightData.rank(base: "の", reading: "の", dict: "main")
        if let saved = knownIndex, saved.count == known.count {
            return saved.index
        }
        CrashTrail.mark("покрытие: индекс знакомых слов (" + String(known.count) + ")")
        let index = await Task.detached(priority: .utility) { KnownWordsIndex(known) }.value
        knownIndex = (known.count, index)
        CrashTrail.mark("покрытие: индекс готов")
        return index
    }

    /// Coverage and difficulty of every video with Jimaku subtitles; kept until the known words, the level or the file change.
    func updateCoverage() {
        let candidates: [(String, URL)] = items.compactMap { item in
            guard !item.isFolder, VideoLibraryStore.isVideo(item.url.lastPathComponent),
                  let file = VideoLibraryStore.jimakuFile(for: item.url) else { return nil }
            return (item.url.lastPathComponent, file)
        }
        guard !candidates.isEmpty else { return }
        let knownCount = HighlightData.minedWords().count
        let level = VideoLibraryStore.userLevel
        var pending: [(String, URL, String)] = []
        for (name, file) in candidates {
            let size = ((try? FileManager.default.attributesOfItem(atPath: file.path)[.size]) as? Int) ?? 0
            let stamp = "4|" + String(level) + "|" + String(knownCount) + "|" + String(size)
            if let saved = UserDefaults.standard.string(forKey: "coverage." + name), saved.hasPrefix(stamp + "|") {
                let parts = saved.dropFirst(stamp.count + 1).split(separator: "|")
                if parts.count == 2, let value = Int(parts[0]), let hardness = Int(parts[1]) {
                    coverage[name] = value
                    difficulty[name] = hardness >= 0 ? hardness : nil
                    continue
                }
            }
            pending.append((name, file, stamp))
        }
        guard !pending.isEmpty, !coverageRunning else { return }
        coverageRunning = true
        Task { @MainActor in
            defer { coverageRunning = false }
            let index = await knownWordsIndex()
            for (name, file, stamp) in pending {
                CrashTrail.mark("покрытие: начало " + name)
                let result = await Task.detached(priority: .utility) {
                    VideoLibraryStore.analyze(of: file, index: index, level: level)
                }.value
                CrashTrail.mark("покрытие: готово " + name)
                guard let result else { continue }
                coverage[name] = result.coverage
                difficulty[name] = result.difficulty
                let hardness = String(result.difficulty ?? -1)
                UserDefaults.standard.set(stamp + "|" + String(result.coverage) + "|" + hardness, forKey: "coverage." + name)
            }
        }
    }

''' + s[b:]

# ---------- the list: unknown words of an episode ----------
s = once(s, "    @State private var queueVideo: String? = nil\n",
         "    @State private var queueVideo: String? = nil\n    @State private var wordsVideo: URL? = nil\n", "words state")
s = once(s, '''                            Label("Очередь", systemImage: "tray.full")
                            }
                            .tint(.blue)
''', '''                            Label("Очередь", systemImage: "tray.full")
                            }
                            .tint(.blue)
                            Button {
                                wordsVideo = item.url
                            } label: {
                                Label("Слова", systemImage: "text.magnifyingglass")
                            }
                            .tint(.orange)
''', "words swipe")
s = once(s, '''                            .background([Color.green, Color.yellow, Color.red][step].opacity(0.85))
                            .cornerRadius(4)
                    }
''', '''                            .background([Color.green, Color.yellow, Color.red][step].opacity(0.85))
                            .cornerRadius(4)
                            .highPriorityGesture(TapGesture().onEnded { wordsVideo = item.url })
                    }
''', "badge tap")
s = once(s, "        .sheet(isPresented: Binding(get: { queueVideo != nil }, set: { if !$0 { queueVideo = nil } })) {\n",
         '''        .sheet(isPresented: Binding(get: { wordsVideo != nil }, set: { if !$0 { wordsVideo = nil } })) {
            if let video = wordsVideo {
                UnknownWordsView(video: video, library: library)
            }
        }
        .sheet(isPresented: Binding(get: { queueVideo != nil }, set: { if !$0 { queueVideo = nil } })) {
''', "words sheet")
s = once(s, '"Слова JLPT до этого уровня считаются знакомыми при оценке сложности серий (easy / normal / hard)."',
         '"Знакомыми считаются ваши карточки, слова JLPT до этого уровня и самые частые слова в объёме этого уровня (N5 ≈ 800, N4 ≈ 1500, N3 ≈ 3700, N2 ≈ 6000, N1 ≈ 10 000). Так считаются покрытие и сложность серий."',
         "settings footer")

s = s.rstrip("\n") + '''

struct UnknownWord: Identifiable {
    var id: String { word }
    let word: String
    let reading: String
    let count: Int
}

struct EpisodeAnalysis {
    let coverage: Int
    let difficulty: Int?
    let knownShare: Double
    let clearShare: Double
    let words: Int
    let lines: Int
    let unknown: [UnknownWord]
}

/// What the analysis counted as unknown in an episode, with the numbers behind its badge.
@available(iOS 16.0, *)
struct UnknownWordsView: View {
    let video: URL
    @ObservedObject var library: VideoLibraryStore
    @Environment(\\.dismiss) private var dismiss
    @State private var analysis: EpisodeAnalysis? = nil
    @State private var loading = true

    private func verdict(_ difficulty: Int?) -> String {
        guard let difficulty else { return "—" }
        let names: [String] = ["easy", "normal", "hard"]
        return names[min(max(difficulty, 0), 2)]
    }

    private func percent(_ value: Double) -> String {
        String(Int((value * 100).rounded())) + "%"
    }

    private func row(_ title: String, _ value: String) -> some View {
        HStack {
            Text(title)
            Spacer()
            Text(value).foregroundColor(.secondary)
        }
    }

    var body: some View {
        NavigationView {
            List {
                if loading {
                    HStack(spacing: 10) {
                        ProgressView()
                        Text("Считаю…")
                    }
                } else if let result = analysis {
                    Section {
                        row("Сложность", verdict(result.difficulty))
                        row("Знакомых слов", percent(result.knownShare))
                        row("Понятных реплик", percent(result.clearShare))
                        row("Слов в субтитрах", String(result.words))
                        row("Реплик", String(result.lines))
                    } footer: {
                        Text("easy: от 90% знакомых слов и 65% понятных реплик; normal: от 80% и 40%; иначе hard. Понятная реплика — не больше одного незнакомого слова. Уровень: N" + String(VideoLibraryStore.userLevel) + ".")
                    }
                    Section {
                        ForEach(result.unknown.prefix(300)) { word in
                            HStack {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(word.word)
                                        .font(.system(size: 20))
                                    if !word.reading.isEmpty && word.reading != word.word {
                                        Text(word.reading)
                                            .font(.caption)
                                            .foregroundColor(.secondary)
                                    }
                                }
                                Spacer()
                                Text("×" + String(word.count))
                                    .foregroundColor(.secondary)
                            }
                        }
                    } header: {
                        Text("Незнакомые слова: " + String(result.unknown.count))
                    }
                } else {
                    Text("У этой серии нет субтитров Jimaku.")
                        .foregroundColor(.secondary)
                }
            }
            .navigationTitle(video.deletingPathExtension().lastPathComponent)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Закрыть") { dismiss() }
                }
            }
            .task {
                await load()
            }
        }
    }

    private func load() async {
        guard let file = VideoLibraryStore.jimakuFile(for: video) else {
            loading = false
            return
        }
        let index = await library.knownWordsIndex()
        let level = VideoLibraryStore.userLevel
        analysis = await Task.detached(priority: .userInitiated) {
            VideoLibraryStore.analyze(of: file, index: index, level: level)
        }.value
        loading = false
    }
}
'''
hv.write_text(s, encoding="utf-8")
print("v1.57 analysis applied")
