# v1.60: the episode analysis without "half known": a word is known or not. The vocabulary is one number (the most
# frequent words known, 0 = from the level). A merged expression made only of grammar (particles, auxiliaries) is not
# a word. The saved analysis depends on the known words themselves (a fingerprint), not on their number, and is kept
# as JSON instead of a "|"-joined string.
import pathlib

hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


def between(text, start, end, new, label):
    assert text.count(start) == 1, "start not found exactly once: " + label
    a = text.index(start)
    b = text.index(end, a)
    return text[:a] + new + text[b:]


# ---------- the analysis ----------
s = between(s, "    /// One pass over the subtitles. Content words only: no particles, auxiliaries, symbols",
            "    /// The known word index, built once", '''    /// easy / normal / hard from the share of known words and of clear lines.
    nonisolated static func classify(known: Double, clear: Double) -> Int {
        if known >= 0.90 && clear >= 0.65 { return 0 }
        if known >= 0.80 && clear >= 0.40 { return 1 }
        return 2
    }

    /// How many of the most frequent words (Jiten) are known: the number of the settings (ykVocabSure);
    /// 0 means from the level (N5 800, N4 1500, N3 3700, N2 6000, N1 10 000).
    static func vocabulary(level: Int) -> Int {
        let saved = UserDefaults.standard.integer(forKey: "ykVocabSure")
        if saved > 0 {
            return saved
        }
        let byLevel: [Int: Int] = [5: 800, 4: 1500, 3: 3700, 2: 6000, 1: 10000]
        return byLevel[level] ?? 800
    }

    /// One pass over the subtitles. Content words only (no particles, auxiliaries, symbols, interjections, proper
    /// nouns, numbers, katakana-only words, Latin, reduplicated onomatopoeia, expressions made only of grammar).
    /// A word is known or not: a card in any form, JLPT up to the level, one of the `vocabulary` most frequent words;
    /// a merged expression (ここに) when all its content parts are known; a noun made of a verb stem (守り) through
    /// the verb. A clear line has at most one unknown word.
    nonisolated static func analyze(of file: URL, index: KnownWordsIndex, level: Int, vocabulary: Int) -> EpisodeAnalysis? {
        var readings: [String: String] = [:]
        func reading(of base: String) -> String {
            if let saved = readings[base] {
                return saved
            }
            let value = KnownWordsIndex.isKana(base) ? HighlightData.hiragana(base) : autoreleasepool {
                HighlightData.hiragana(NativeLookup.tokenize(base, charAt: 0).tokens.map { $0.reading }.joined())
            }
            readings[base] = value
            return value
        }
        func isKnown(base: String, text: String, tokenReading: String) -> Bool {
            if index.forms.contains(base) || index.forms.contains(text) { return true }
            let kana = reading(of: base)
            if !kana.isEmpty {
                if index.kanaReadings.contains(kana) { return true }
                if let kanji = index.kanjiByReading[kana],
                   KnownWordsIndex.isKana(text) || !kanji.isDisjoint(with: KnownWordsIndex.kanji(base)) { return true }
            }
            let lookup = kana.isEmpty ? HighlightData.hiragana(tokenReading) : kana
            let jlpt = HighlightData.jlptLevel(base: base, reading: lookup)
            if jlpt > 0, jlpt >= level { return true }
            let rank = HighlightData.rank(base: base, reading: lookup, dict: "main", text: text)
                ?? HighlightData.rank(base: base, reading: "", dict: "main", text: text)
            if let rank, rank <= vocabulary { return true }
            return false
        }
        func isContent(_ token: LookupToken) -> Bool {
            guard token.text.unicodeScalars.contains(where: { KnownWordsIndex.isJapanese($0) }) else { return false }
            if token.pos.hasPrefix("助詞") || token.pos.hasPrefix("助動詞") || token.pos.contains("記号") { return false }
            if token.pos.hasPrefix("感動詞") || token.pos2.contains("固有名詞") || token.pos2.contains("数詞") { return false }
            if KnownWordsIndex.isKatakana(token.text) || KnownWordsIndex.isReduplicated(token.text) { return false }
            return true
        }
        func counted(_ token: LookupToken) -> Bool {
            guard isContent(token) else { return false }
            return token.parts.isEmpty || token.parts.contains { isContent($0) }
        }
        func known(_ token: LookupToken) -> Bool {
            let base = token.base.isEmpty ? token.text : token.base
            if isKnown(base: base, text: token.text, tokenReading: token.reading) { return true }
            let content = token.parts.filter { isContent($0) }
            if !content.isEmpty, content.allSatisfy({ part in
                isKnown(base: part.base.isEmpty ? part.text : part.base, text: part.text, tokenReading: part.reading)
            }) { return true }
            if let verb = KnownWordsIndex.verbOfNoun(base) {
                return isKnown(base: verb, text: verb, tokenReading: "")
            }
            return false
        }

        var words = 0
        var knownWords = 0
        var lines = 0
        var clearLines = 0
        var unknownCounts: [String: Int] = [:]
        for cue in EmbeddedSubtitles.cues(fromFile: file) {
            guard !cue.text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { continue }
            let tokens = autoreleasepool { NativeLookup.tokenize(cue.text, charAt: 0).tokens }
            var lineWords = 0
            var lineUnknown = 0
            for token in tokens where counted(token) {
                lineWords += 1
                if known(token) {
                    continue
                }
                lineUnknown += 1
                let base = token.base.isEmpty ? token.text : token.base
                unknownCounts[base, default: 0] += 1
            }
            guard lineWords > 0 else { continue }
            words += lineWords
            knownWords += lineWords - lineUnknown
            lines += 1
            if lineUnknown <= 1 {
                clearLines += 1
            }
        }
        guard words > 0, lines > 0 else { return nil }
        let knownShare = Double(knownWords) / Double(words)
        let clear = Double(clearLines) / Double(lines)
        let difficulty: Int? = words >= 50 ? classify(known: knownShare, clear: clear) : nil
        var list: [UnknownWord] = []
        for (word, count) in unknownCounts {
            list.append(UnknownWord(word: word, reading: reading(of: word), count: count))
        }
        list.sort { first, second in
            first.count != second.count ? first.count > second.count : first.word < second.word
        }
        return EpisodeAnalysis(coverage: Int((knownShare * 100).rounded()), difficulty: difficulty,
                               knownShare: knownShare, clearShare: clear, words: words, lines: lines, unknown: list)
    }

''', "analysis")

# ---------- the known word index and the saved results ----------
s = once(s, "    private var knownIndex: (count: Int, index: KnownWordsIndex)?\n",
         "    private var knownIndex: KnownWordsIndex?\n", "known index property")
s = between(s, "    /// The known word index, built once", "    /// known share, clear share and coverage of each analysed video",
            '''    /// The known word index, built again when the known words change.
    func knownWordsIndex() async -> KnownWordsIndex {
        let known = HighlightData.minedWords()
        // the JLPT and frequency tables are loaded here, on the main thread
        _ = HighlightData.jlptLevel(base: "の", reading: "の")
        _ = HighlightData.rank(base: "の", reading: "の", dict: "main")
        if let saved = knownIndex, saved.fingerprint == KnownWordsIndex.fingerprint(known) {
            return saved
        }
        CrashTrail.mark("покрытие: индекс знакомых слов (" + String(known.count) + ")")
        let index = await Task.detached(priority: .utility) { KnownWordsIndex(known) }.value
        knownIndex = index
        CrashTrail.mark("покрытие: индекс готов")
        return index
    }

    /// Coverage and difficulty of every video with Jimaku subtitles here and in the folders here (a folder shows the
    /// average of its episodes); kept until the known words, the level, the vocabulary or the file change.
    func updateCoverage() {
        var candidates: [(String, URL)] = []
        var folderVideos: [String: [String]] = [:]
        let fm = FileManager.default
        for item in items {
            if item.isFolder {
                let inside = (try? fm.contentsOfDirectory(at: item.url, includingPropertiesForKeys: nil)) ?? []
                var names: [String] = []
                for video in inside where VideoLibraryStore.isVideo(video.lastPathComponent) {
                    if let file = VideoLibraryStore.jimakuFile(for: video) {
                        candidates.append((video.lastPathComponent, file))
                        names.append(video.lastPathComponent)
                    }
                }
                folderVideos[item.url.lastPathComponent] = names
            } else if VideoLibraryStore.isVideo(item.url.lastPathComponent),
                      let file = VideoLibraryStore.jimakuFile(for: item.url) {
                candidates.append((item.url.lastPathComponent, file))
            }
        }
        guard !candidates.isEmpty else { return }
        let knownWords = KnownWordsIndex.fingerprint(HighlightData.minedWords())
        let level = VideoLibraryStore.userLevel
        let vocabulary = VideoLibraryStore.vocabulary(level: level)
        var pending: [(String, URL, Int)] = []
        for (name, file) in candidates {
            let size = ((try? fm.attributesOfItem(atPath: file.path)[.size]) as? Int) ?? 0
            if let data = UserDefaults.standard.data(forKey: "coverage." + name),
               let saved = try? JSONDecoder().decode(CoverageEntry.self, from: data),
               saved.level == level, saved.vocabulary == vocabulary, saved.knownWords == knownWords, saved.size == size {
                coverage[name] = saved.coverage
                difficulty[name] = saved.difficulty
                shares[name] = (saved.knownShare, saved.clearShare, saved.coverage)
                continue
            }
            pending.append((name, file, size))
        }
        updateFolders(folderVideos)
        guard !pending.isEmpty, !coverageRunning else { return }
        coverageRunning = true
        Task { @MainActor in
            defer { coverageRunning = false }
            let index = await knownWordsIndex()
            for (name, file, size) in pending {
                CrashTrail.mark("покрытие: начало " + name)
                let result = await Task.detached(priority: .utility) {
                    VideoLibraryStore.analyze(of: file, index: index, level: level, vocabulary: vocabulary)
                }.value
                CrashTrail.mark("покрытие: готово " + name)
                guard let result else { continue }
                coverage[name] = result.coverage
                difficulty[name] = result.difficulty
                shares[name] = (result.knownShare, result.clearShare, result.coverage)
                let entry = CoverageEntry(level: level, vocabulary: vocabulary, knownWords: index.fingerprint, size: size,
                                          coverage: result.coverage, difficulty: result.difficulty,
                                          knownShare: result.knownShare, clearShare: result.clearShare)
                if let data = try? JSONEncoder().encode(entry) {
                    UserDefaults.standard.set(data, forKey: "coverage." + name)
                }
                updateFolders(folderVideos)
            }
        }
    }

''', "known index and coverage")

s = once(s, """struct KnownWordsIndex {
    var forms = Set<String>()
""", """struct KnownWordsIndex {
    /// the known words the index was built from (see fingerprint(_:))
    var fingerprint: UInt64 = 0
    var forms = Set<String>()
""", "index fingerprint property")
s = once(s, """    init(_ words: Set<String>) {
        for raw in words {
            let word = KnownWordsIndex.clean(raw)
""", """    init(_ words: Set<String>) {
        fingerprint = KnownWordsIndex.fingerprint(words)
        for raw in words {
            let word = KnownWordsIndex.clean(raw)
""", "index fingerprint init")
s = once(s, """    /// Words from Anki can carry HTML and furigana in brackets: 食[た]べる.
""", """    /// The same for the same words in any order and between launches (FNV-1a of every word, summed), so a replaced
    /// word changes it while the number of words stays.
    static func fingerprint(_ words: Set<String>) -> UInt64 {
        var sum: UInt64 = UInt64(words.count)
        for word in words {
            var hash: UInt64 = 0xcbf2_9ce4_8422_2325
            for byte in word.utf8 {
                hash = (hash ^ UInt64(byte)) &* 0x0000_0100_0000_01b3
            }
            sum = sum &+ hash
        }
        return sum
    }

    /// Words from Anki can carry HTML and furigana in brackets: 食[た]べる.
""", "fingerprint")

# ---------- the unknown words screen ----------
s = once(s, """    let count: Int
    /// inside the frequency band of the highlight settings: counted as half known
    var partial: Bool = false
}

struct EpisodeAnalysis {""", """    let count: Int
}

/// The saved analysis of a video and what it depended on.
struct CoverageEntry: Codable {
    let level: Int
    let vocabulary: Int
    let knownWords: UInt64
    let size: Int
    let coverage: Int
    let difficulty: Int?
    let knownShare: Double
    let clearShare: Double
}

struct EpisodeAnalysis {""", "unknown word and saved entry")
s = once(s, """                                Spacer()
                                if word.partial {
                                    Text("50/50")
                                        .font(.caption2.bold())
                                        .foregroundColor(.orange)
                                }
                                Text("×" + String(word.count))
""", """                                Spacer()
                                Text("×" + String(word.count))
""", "partial mark")
s = once(s, """Понятная реплика — не больше одного незнакомого слова. Уровень: N" + String(VideoLibraryStore.userLevel) + ".")""",
         """Понятная реплика — не больше одного незнакомого слова. Уровень: N" + String(VideoLibraryStore.userLevel) + ", частых слов: " + String(VideoLibraryStore.vocabulary(level: VideoLibraryStore.userLevel)) + ".")""",
         "words screen footer")
s = once(s, """        let band = VideoLibraryStore.frequencyBand(level: level)
        analysis = await Task.detached(priority: .userInitiated) {
            VideoLibraryStore.analyze(of: file, index: index, level: level, lower: band.lower, upper: band.upper)
        }.value
""", """        let vocabulary = VideoLibraryStore.vocabulary(level: level)
        analysis = await Task.detached(priority: .userInitiated) {
            VideoLibraryStore.analyze(of: file, index: index, level: level, vocabulary: vocabulary)
        }.value
""", "words screen analysis")

# ---------- the settings ----------
s = once(s, '    @AppStorage("ykVocabPartial") private var vocabPartial = 0\n', "", "partial storage")
s = once(s, """                HStack {
                    Text("Точно знаю первые")
                    Spacer()
                    TextField("по уровню", value: $vocabSure, format: .number)
                        .keyboardType(.numberPad)
                        .multilineTextAlignment(.trailing)
                        .foregroundColor(.secondary)
                        .frame(width: 100)
                }
                HStack {
                    Text("Наполовину знаю до")
                    Spacer()
                    TextField("по уровню", value: $vocabPartial, format: .number)
                        .keyboardType(.numberPad)
                        .multilineTextAlignment(.trailing)
                        .foregroundColor(.secondary)
                        .frame(width: 100)
                }
""", """                HStack {
                    Text("Знаю частых слов")
                    Spacer()
                    TextField("по уровню", value: $vocabSure, format: .number)
                        .keyboardType(.numberPad)
                        .multilineTextAlignment(.trailing)
                        .foregroundColor(.secondary)
                        .frame(width: 100)
                }
""", "vocab fields")
s = once(s, '"Для покрытия и сложности серий знакомыми считаются ваши карточки, слова JLPT до этого уровня и самые частые слова: первые N точно, дальше до второго числа — наполовину. 0 — по уровню (N5 ≈ 800, N4 ≈ 1500, N3 ≈ 3700, N2 ≈ 6000, N1 ≈ 10 000, наполовину — вдвое больше). Подсветка на это не влияет."',
         '"Для покрытия и сложности серий знакомыми считаются ваши карточки, слова JLPT до этого уровня и столько самых частых слов (Jiten). 0 — по уровню: N5 ≈ 800, N4 ≈ 1500, N3 ≈ 3700, N2 ≈ 6000, N1 ≈ 10 000. Подсветка на это не влияет."',
         "footer")

for gone in ["frequencyBand", "ykVocabPartial", "partial:", "lower: band"]:
    assert gone not in s, "left over: " + gone
hv.write_text(s, encoding="utf-8")
print("v1.60 analysis applied")
