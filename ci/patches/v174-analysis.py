# v1.74: a smarter analysis and a faster catalog.
# - A word is common when it is common in any frequency list (Jiten, Jiten WebNovel …): お前, お嬢様.
# - Numbers with counters (１０歳, 三人), prefixes and suffixes (お, 様, さん) are not words to learn; お祖父様 is judged
#   by 祖父.
# - A word without an entry in the dictionary (a name written in kana like ぜにす, a sound, a misread piece) is not
#   an unknown word: it is left out.
# - The saved analyses carry the version of the rules: everything is counted again once.
# - Catalog: a verdict per word is shared by all titles (they have most words in common), three titles are counted
#   at once, Jiten's "slow down" waits and retries; the unknown word lists have no limit any more.
import pathlib


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


def between(text, start, end, new, label):
    assert text.count(start) == 1, "start not found exactly once: " + label
    a = text.index(start)
    b = text.index(end, a)
    return text[:a] + new + text[b:]


hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")

# ---------- the best rank of all frequency lists ----------
s = once(s, "    static func color(hex: String) -> Color? {\n", r'''    /// The best rank of all frequency lists (Jiten, Jiten WebNovel …): a word common in any of them is common.
    static func bestRank(base: String, reading: String, text: String) -> Int? {
        var best: Int? = nil
        for entry in freqTables() {
            let found = rank(base: base, reading: reading, dict: entry.id, text: text)
                ?? rank(base: base, reading: "", dict: entry.id, text: text)
            if let found, found < (best ?? Int.max) {
                best = found
            }
        }
        return best
    }

    static func color(hex: String) -> Color? {
''', "best rank")

# ---------- the rules of a known word ----------
s = once(s, '''        let rank = HighlightData.rank(base: base, reading: lookup, dict: "main", text: text)
            ?? HighlightData.rank(base: base, reading: "", dict: "main", text: text)
        if let rank, rank <= vocabulary { return true }
''', '''        if let rank = HighlightData.bestRank(base: base, reading: lookup, text: text), rank <= vocabulary { return true }
        // お前: the dictionary form is 御前 (read ごぜん alone), the lists know the word as written
        if text != base, !tokenReading.isEmpty,
           let rank = HighlightData.bestRank(base: text, reading: HighlightData.hiragana(tokenReading), text: text),
           rank <= vocabulary { return true }
''', "known by rank")
s = once(s, '''        if KnownWordsIndex.isKatakana(token.text) || KnownWordsIndex.isReduplicated(token.text) { return false }
        return true
    }

    /// A content word; an expression made only of grammar is not a word.
    static func counted(_ token: LookupToken) -> Bool {
        guard isContent(token) else { return false }
''', '''        if KnownWordsIndex.isKatakana(token.text) || KnownWordsIndex.isReduplicated(token.text) { return false }
        // お, ご, 様, さん, 的 …: parts of words, not words to learn
        if token.pos.hasPrefix("接頭辞") || token.pos.hasPrefix("接尾辞") { return false }
        // digits: a number with its counter (１０歳) is understood without learning it
        if token.text.unicodeScalars.contains(where: { CharacterSet.decimalDigits.contains($0) }) { return false }
        // kana the tokenizer does not know at all (UNK): a name written in kana, a sound
        if token.pos == "UNK" && token.parts.isEmpty && KnownWordsIndex.isKana(token.text) { return false }
        return true
    }

    /// A content word; an expression made only of grammar is not a word, nor a number with its counter (三人).
    static func counted(_ token: LookupToken) -> Bool {
        guard isContent(token) else { return false }
        if token.parts.contains(where: { $0.pos2.contains("数詞") }) { return false }
''', "content rules")
s = once(s, '''        if let verb = KnownWordsIndex.verbOfNoun(base) {
            return isKnown(base: verb, text: verb, tokenReading: "")
        }
        return false
    }
}
''', '''        // おじいさま, お嬢さん: the same word with さん, or the word under the honorifics
        for form in WordKnowledge.honorificForms(base) where isKnown(base: form, text: form, tokenReading: "") {
            return true
        }
        if let verb = KnownWordsIndex.verbOfNoun(base) {
            return isKnown(base: verb, text: verb, tokenReading: "")
        }
        return false
    }

    /// おじいさま → おじいさん, おじい, じい; ご主人様 → ご主人さん, ご主人, 主人; お手紙 → 手紙. Only words that start with
    /// お, ご or 御: 同様 or 主君 are not honorifics.
    static func honorificForms(_ word: String) -> [String] {
        guard let prefix = ["お", "ご", "御"].first(where: { word.hasPrefix($0) }) else { return [] }
        var forms: [String] = []
        var stem = word
        for suffix in ["様", "さま", "さん", "ちゃん", "くん"] where word.hasSuffix(suffix) && word.count > suffix.count + 1 {
            stem = String(word.dropLast(suffix.count))
            if suffix != "さん" {
                forms.append(stem + "さん")
            }
            forms.append(stem)
            break
        }
        if stem.count > prefix.count + 1 {
            forms.append(String(stem.dropFirst(prefix.count)))
        }
        return forms
    }

    private var dictionaryHits: [String: Bool] = [:]

    /// The word has an entry of its own in the dictionary: a name written in kana, a sound or a misread piece has
    /// none and is not a word to learn.
    func inDictionary(_ token: LookupToken) -> Bool {
        let base = token.base.isEmpty ? token.text : token.base
        if let saved = dictionaryHits[base] {
            return saved
        }
        let entries = autoreleasepool { NativeLookup.tokenize(base, charAt: 0).entries }
        let kana = reading(of: base)
        let found = entries.contains { entry in
            entry.headword == base || entry.reading == base || (!kana.isEmpty && entry.reading == kana)
        }
        dictionaryHits[base] = found
        return found
    }
}
''', "known helpers")

# ---------- the analysis of lines ----------
s = once(s, "enum TextAnalysis {\n", "enum TextAnalysis {\n    /// changes with the rules: the saved analyses are counted again\n    static let algorithm = 2\n\n",
         "algorithm version")
s = once(s, '''            for token in tokens where WordKnowledge.counted(token) {
                lineWords += 1
                if judge.known(token) {
                    continue
                }
                lineUnknown += 1
''', '''            for token in tokens where WordKnowledge.counted(token) {
                if judge.known(token) {
                    lineWords += 1
                    continue
                }
                // not in the dictionary (a name in kana, a sound, a misread piece): not a word to learn
                guard judge.inDictionary(token) else { continue }
                lineWords += 1
                lineUnknown += 1
''', "analysis loop")

# ---------- the saved analyses know the version of the rules ----------
s = once(s, "    let knownShare: Double\n    let clearShare: Double\n}\n\nstruct EpisodeAnalysis",
         "    let knownShare: Double\n    let clearShare: Double\n    /// TextAnalysis.algorithm (nil before 1.74)\n    var algorithm: Int? = nil\n}\n\nstruct EpisodeAnalysis",
         "coverage entry version")
s = once(s, "saved.level == level, saved.vocabulary == vocabulary, saved.knownWords == knownWords, saved.size == size {",
         "saved.level == level, saved.vocabulary == vocabulary, saved.knownWords == knownWords, saved.size == size,\n"
         "               saved.algorithm == TextAnalysis.algorithm {", "coverage entry check")
s = once(s, "knownShare: result.knownShare, clearShare: result.clearShare)",
         "knownShare: result.knownShare, clearShare: result.clearShare,\n"
         "                                          algorithm: TextAnalysis.algorithm)", "coverage entry write")
s = once(s, "    let vocabulary: Int\n    var episodes: [Int: NovelEpisodeAnalysis]\n}\n",
         "    let vocabulary: Int\n    var episodes: [Int: NovelEpisodeAnalysis]\n    /// TextAnalysis.algorithm (nil before 1.74)\n"
         "    var algorithm: Int? = nil\n}\n", "novel analysis version")
s = once(s, "           loaded.vocabulary == vocabulary {\n", "           loaded.vocabulary == vocabulary, loaded.algorithm == TextAnalysis.algorithm {\n",
         "novel analysis check")
s = once(s, "vocabulary: vocabulary, episodes: [:])", "vocabulary: vocabulary, episodes: [:],\n"
         "                                        algorithm: TextAnalysis.algorithm)", "novel analysis write")
s = once(s, "            for word in result.unknown.prefix(200) {\n", "            for word in result.unknown {\n", "novel words all")
s = once(s, "        return Array(list.prefix(500))\n", "        return list\n", "novel merged words all")
s = once(s, "    let words: Int\n    let unknown: [CatalogUnknown]\n\n    /// easy / normal / hard by the known words only",
         "    let words: Int\n    let unknown: [CatalogUnknown]\n    /// TextAnalysis.algorithm (nil before 1.74)\n    var algorithm: Int? = nil\n"
         "    /// false: counted in the background, the numbers only (thousands of titles would take hundreds of MB)\n"
         "    var full: Bool? = nil\n\n"
         "    /// The numbers without the list of unknown words.\n"
         "    var summary: CatalogCoverage {\n"
         "        CatalogCoverage(knownWords: knownWords, level: level, vocabulary: vocabulary, known: known,\n"
         "                        uniqueKnown: uniqueKnown, words: words, unknown: [], algorithm: algorithm, full: false)\n"
         "    }\n\n"
         "    /// easy / normal / hard by the known words only", "catalog coverage version")
s = once(s, """        if let saved = CatalogStore.saved(deck.deckId, knownWords: knownWords, level: level, vocabulary: vocabulary) {
            coverage = saved
        } else {
""", """        if let saved = CatalogStore.saved(deck.deckId, knownWords: knownWords, level: level, vocabulary: vocabulary) {
            coverage = saved
            // counted in the background: the numbers are shown, the list of unknown words is counted now
            if saved.full == false {
                await countCoverage()
            }
        } else {
""", "detail full list")
s = once(s, "saved.knownWords == knownWords, saved.level == level, saved.vocabulary == vocabulary else { return nil }",
         "saved.knownWords == knownWords, saved.level == level, saved.vocabulary == vocabulary,\n"
         "              saved.algorithm == TextAnalysis.algorithm else { return nil }", "catalog coverage check")

# ---------- the catalog: shared verdicts per word ----------
s = between(s, "    /// Our coverage of a title: every word of Jiten's list is read by our tokenizer, filtered and judged like the",
            "    private static var index: KnownWordsIndex?", r'''    /// Our coverage of a title: every word of Jiten's list is judged like the words of the subtitles (the verdicts
    /// are shared by all titles); the shares are weighted by how often the words occur.
    static func coverage(of words: [CatalogWord], index: KnownWordsIndex, level: Int, vocabulary: Int,
                         cacheKey: UInt64? = nil) -> CatalogCoverage {
        let judge = WordKnowledge(index: index, level: level, vocabulary: vocabulary)
        let key = cacheKey ?? CatalogWordCache.key(index.fingerprint, level, vocabulary)
        var total = 0
        var knownTotal = 0
        var distinct = 0
        var knownDistinct = 0
        var unknown: [CatalogUnknown] = []
        for item in words {
            switch CatalogWordCache.shared.verdict(item.word, item.kana, judge: judge, key: key) {
            case .skip:
                continue
            case .known:
                distinct += 1
                total += item.count
                knownDistinct += 1
                knownTotal += item.count
            case .unknown:
                distinct += 1
                total += item.count
                unknown.append(CatalogUnknown(word: item.word, kana: item.kana, count: item.count))
            }
        }
        let known = total > 0 ? Double(knownTotal) / Double(total) : 0
        let uniqueKnown = distinct > 0 ? Double(knownDistinct) / Double(distinct) : 0
        unknown.sort { $0.count > $1.count }
        return CatalogCoverage(knownWords: index.fingerprint, level: level, vocabulary: vocabulary, known: known,
                               uniqueKnown: uniqueKnown, words: distinct, unknown: unknown,
                               algorithm: TextAnalysis.algorithm)
    }

''', "catalog coverage")
s = once(s, "    static func words(_ id: Int) async throws -> [CatalogWord] {\n",
         "    /// `keep`: the list stays in the cache (the titles opened); the background counting does not keep it.\n"
         "    static func words(_ id: Int, keep: Bool = true) async throws -> [CatalogWord] {\n", "words keep")
s = once(s, "        if let encoded = try? JSONEncoder().encode(words) {\n            try? encoded.write(to: file)\n        }\n",
         "        if keep, let encoded = try? JSONEncoder().encode(words) {\n            try? encoded.write(to: file)\n        }\n",
         "words keep write")

# ---------- the catalog queue: three at once ----------
s = between(s, "/// Our coverage of the titles on screen, counted one by one in the background (the newest request first): the",
            "/// The badge of our coverage: the share in the colour of the difficulty.", r'''/// What our rules say about a word of Jiten's lists, shared by all titles (they have most of their words in common)
/// until the known words, the level, the vocabulary or the rules change.
@available(iOS 16.0, *)
final class CatalogWordCache: @unchecked Sendable {
    static let shared = CatalogWordCache()

    enum Verdict {
        case skip
        case known
        case unknown
    }

    private let lock = NSLock()
    private var currentKey: UInt64 = 0
    private var verdicts: [String: Verdict] = [:]

    static func key(_ fingerprint: UInt64, _ level: Int, _ vocabulary: Int) -> UInt64 {
        fingerprint &+ UInt64(level) &* 1_000_003 &+ UInt64(vocabulary) &* 7_919 &+ UInt64(TextAnalysis.algorithm) &* 104_729
    }

    func verdict(_ word: String, _ kana: String, judge: WordKnowledge, key: UInt64) -> Verdict {
        let name = word + "|" + kana
        lock.lock()
        if currentKey != key {
            currentKey = key
            verdicts = [:]
        }
        let saved = verdicts[name]
        lock.unlock()
        if let saved {
            return saved
        }
        let result = CatalogWordCache.judge(word, kana, judge)
        lock.lock()
        if currentKey == key {
            verdicts[name] = result
        }
        lock.unlock()
        return result
    }

    private static func judge(_ word: String, _ kana: String, _ judge: WordKnowledge) -> Verdict {
        let tokens = autoreleasepool { NativeLookup.tokenize(word, charAt: 0).tokens }
        guard let first = tokens.first else { return .skip }
        var token = first
        if tokens.count > 1 {
            let main = tokens.first { WordKnowledge.isContent($0) } ?? first
            token = LookupToken(id: 0, text: word, start: 0, base: word, reading: kana, pos: main.pos, pos2: main.pos2,
                                parts: tokens)
        }
        guard WordKnowledge.counted(token) else { return .skip }
        if judge.known(token) {
            return .known
        }
        // Jiten's words come from the dictionary; a single word is checked against ours (names written in kana)
        return tokens.count > 1 || judge.inDictionary(token) ? .unknown : .skip
    }
}

/// Our coverage of the titles, counted in the background, three at a time: the rows on screen first, then a whole
/// list when it is sorted by coverage. Jiten's "slow down" waits and retries.
@available(iOS 16.0, *)
@MainActor
final class CatalogCoverageQueue: ObservableObject {
    static let shared = CatalogCoverageQueue()
    private static let parallel = 3

    @Published private(set) var results: [Int: CatalogCoverage] = [:]
    @Published private(set) var working: Set<Int> = []
    @Published private(set) var waiting: [Int] = []
    private var failed = Set<Int>()
    /// asked as part of a whole list: a row leaving the screen does not take them out
    private var pinned = Set<Int>()
    private var workers = 0
    private var stamp: (time: CFTimeInterval, knownWords: UInt64, level: Int, vocabulary: Int)? = nil

    /// The known words, the level and the vocabulary now (read again at most every 10 s).
    private func currentStamp() -> (knownWords: UInt64, level: Int, vocabulary: Int) {
        let now = CACurrentMediaTime()
        if let stamp, now - stamp.time < 10 {
            return (stamp.knownWords, stamp.level, stamp.vocabulary)
        }
        let level = VideoLibraryStore.userLevel
        let fresh = (time: now, knownWords: KnownWordsIndex.fingerprint(HighlightData.minedWords()), level: level,
                     vocabulary: VideoLibraryStore.vocabulary(level: level))
        if let old = stamp, old.knownWords != fresh.knownWords || old.level != fresh.level || old.vocabulary != fresh.vocabulary {
            results = [:]
            failed = []
        }
        stamp = fresh
        return (fresh.knownWords, fresh.level, fresh.vocabulary)
    }

    func store(_ id: Int, _ coverage: CatalogCoverage) {
        results[id] = coverage
    }

    private func saved(_ id: Int) -> Bool {
        let now = currentStamp()
        guard let coverage = CatalogStore.saved(id, knownWords: now.knownWords, level: now.level,
                                                vocabulary: now.vocabulary) else { return false }
        results[id] = coverage
        return true
    }

    /// A row came on screen: it goes first.
    func request(_ id: Int) {
        _ = currentStamp()
        guard results[id] == nil, !failed.contains(id), !working.contains(id), !saved(id) else { return }
        waiting.removeAll { $0 == id }
        waiting.insert(id, at: 0)
        start()
    }

    /// A whole list (sorting by coverage): after the rows on screen.
    func requestAll(_ ids: [Int]) {
        for id in ids where results[id] == nil && !failed.contains(id) && !working.contains(id) && !waiting.contains(id) {
            if !saved(id) {
                pinned.insert(id)
                waiting.append(id)
            }
        }
        start()
    }

    /// A row left the screen before its turn.
    func forget(_ id: Int) {
        guard !pinned.contains(id) else { return }
        waiting.removeAll { $0 == id }
    }

    private func start() {
        while workers < CatalogCoverageQueue.parallel, !waiting.isEmpty {
            workers += 1
            Task { @MainActor in
                await runWorker()
                workers -= 1
            }
        }
    }

    private func runWorker() async {
        while !waiting.isEmpty {
            let id = waiting.removeFirst()
            working.insert(id)
            let cached = FileManager.default.fileExists(atPath: CatalogStore.folder
                .appendingPathComponent("words-" + String(id) + ".json").path)
            do {
                let words = try await JitenAPI.words(id, keep: !pinned.contains(id))
                let index = await CatalogStore.knownIndex()
                let now = currentStamp()
                let key = CatalogWordCache.key(index.fingerprint, now.level, now.vocabulary)
                let result = await Task.detached(priority: .utility) {
                    CatalogStore.coverage(of: words, index: index, level: now.level, vocabulary: now.vocabulary,
                                          cacheKey: key)
                }.value
                // the numbers only: the list of words is counted again when the title is opened
                let summary = result.summary
                CatalogStore.save(summary, for: id)
                results[id] = summary
            } catch JimakuService.Failure.status(let code) where code == 429 {
                // Jiten asks to slow down: this title waits at the end of the queue
                working.remove(id)
                waiting.append(id)
                try? await Task.sleep(nanoseconds: 10_000_000_000)
                continue
            } catch {
                failed.insert(id)
            }
            working.remove(id)
            pinned.remove(id)
            if !cached {
                try? await Task.sleep(nanoseconds: 300_000_000)
            }
        }
    }
}

''', "catalog queue")

# ---------- the catalog list: sorting by coverage counts the whole list ----------
s = once(s, "                    } else if queue.working == deck.deckId {\n",
         "                    } else if queue.working.contains(deck.deckId) {\n", "row progress")
s = once(s, '''            results = page.decks
            total = page.total
            message = page.decks.isEmpty ? "Ничего не найдено" : ""
''', '''            results = page.decks
            total = page.total
            message = page.decks.isEmpty ? "Ничего не найдено" : ""
            if filter.sort == "coverage" {
                queue.requestAll(page.decks.map { $0.deckId })
            }
''', "coverage sort first page")
s = once(s, '''            results += fresh
            if fresh.isEmpty {
''', '''            results += fresh
            if filter.sort == "coverage" {
                queue.requestAll(fresh.map { $0.deckId })
            }
            if fresh.isEmpty {
''', "coverage sort next pages")
s = once(s, "    @State private var showFilter = false\n\n    /// \"Моё покрытие\"",
         "    @State private var showFilter = false\n    @State private var loadingAll = false\n\n    /// \"Моё покрытие\"",
         "load all state")
s = once(s, '''                } else if !message.isEmpty {
                    Text(message).foregroundColor(.secondary)
                }
                ForEach(shown) { deck in
''', '''                } else if !message.isEmpty {
                    Text(message).foregroundColor(.secondary)
                }
                if filter.sort == "coverage" && total > 0 {
                    countAllRow
                }
                ForEach(shown) { deck in
''', "count all row")
s = once(s, 'Text("Поиск по английскому, японскому и ромадзи названию. Покрытие считается само для тайтлов на экране. '
            'Данные: Jiten (jiten.moe), CC BY-SA 4.0.")',
         'Text("Поиск по английскому, японскому и ромадзи названию. Покрытие считается само для тайтлов на экране, а при "\n'
         '                     + "сортировке «Моё покрытие» — для всего загруженного списка. Данные: Jiten (jiten.moe), CC BY-SA 4.0.")',
         "catalog footer")
s = once(s, '''    private func row(_ deck: JitenDeck) -> some View {
        HStack(spacing: 12) {
            CatalogCover(url: deck.coverURL)
''', '''    private var countedCount: Int {
        results.filter { queue.results[$0.deckId] != nil }.count
    }

    /// Sorting by coverage: how many titles are counted, and a button that loads and counts the whole list.
    private var countAllRow: some View {
        let counted = countedCount
        let note: String = results.count < total
            ? "Загружено " + String(results.count) + ", остальные посчитаются после загрузки"
            : "Считается по три тайтла сразу, в фоне"
        return HStack(spacing: 10) {
            VStack(alignment: .leading, spacing: 2) {
                Text("Посчитано " + String(counted) + " из " + String(total))
                Text(note)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            Spacer()
            if loadingAll || !queue.waiting.isEmpty || !queue.working.isEmpty {
                ProgressView()
            }
            if !loadingAll && results.count < total {
                Button("Посчитать все") {
                    Task { await loadAll() }
                }
                .buttonStyle(.borderless)
            }
        }
    }

    /// Every page of the list, one by one with a pause; each page is counted as it comes.
    private func loadAll() async {
        guard !loadingAll else { return }
        loadingAll = true
        defer { loadingAll = false }
        let key = query + "|" + String(type) + "|" + String(describing: filter)
        queue.requestAll(results.map { $0.deckId })
        while results.count < total {
            guard key == query + "|" + String(type) + "|" + String(describing: filter) else { return }
            if loadingMore {
                try? await Task.sleep(nanoseconds: 300_000_000)
                continue
            }
            let before = results.count
            await loadMore()
            if results.count == before {
                return
            }
            try? await Task.sleep(nanoseconds: 200_000_000)
        }
    }

    private func row(_ deck: JitenDeck) -> some View {
        HStack(spacing: 12) {
            CatalogCover(url: deck.coverURL)
''', "count all")
hv.write_text(s, encoding="utf-8")
print("v1.74 analysis applied")
