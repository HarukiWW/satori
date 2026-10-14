# v1.75: names out of the unknown words, words written in kana, and a catalog that lives with Jiten's limit.
# - Jiten's word lists carry the JMdict id of every word: names (JMnedict, 5 000 000+) are left out. The cached
#   lists are read again (a new file name).
# - A word written in kana is judged as the dictionary writes it: おまえ → お前, ばあちゃん → 婆ちゃん; ばあちゃん is
#   also known when おばあさん is. A word is "in the dictionary" only when the backend reads it as one word that has
#   a word entry (a name has only a name entry).
# - Jiten gives about ten word lists a minute to one phone (measured): the background counting goes one title at a
#   time with a pause, waits a minute when Jiten asks, and stops while a title page downloads its own list, which
#   retries by itself. The lists stay on the phone, so a title counted in the background opens without a download.
# - Back from a title page the catalog keeps its pages and progress (it was searched again from the first page).
# - A title counted in the background shows "count the unknown words" instead of "0".
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

# ---------- the rules: version 3 ----------
s = once(s, "    static let algorithm = 2\n", "    static let algorithm = 3\n", "algorithm 3")

# ---------- words written in kana: as the dictionary writes them ----------
s = once(s, '''           rank <= vocabulary { return true }
        return false
    }
''', '''           rank <= vocabulary { return true }
        // おまえ, ばあちゃん: the word as the dictionary writes it (お前, 婆ちゃん)
        if KnownWordsIndex.isKana(text) || text != base,
           knownAsWritten(text, kana: kana.isEmpty ? HighlightData.hiragana(tokenReading) : kana) { return true }
        return false
    }

    /// Known as the dictionary writes the word: its first two word entries, when they are the same word (the same
    /// writing or reading).
    private func knownAsWritten(_ written: String, kana: String) -> Bool {
        let writtenKana = HighlightData.hiragana(written)
        for entry in entries(of: written).prefix(2) {
            let reading = HighlightData.hiragana(entry.reading)
            guard entry.headword == written || reading == kana || reading == writtenKana else { continue }
            if index.forms.contains(entry.headword) { return true }
            let jlpt = HighlightData.jlptLevel(base: entry.headword, reading: reading)
            if jlpt > 0, jlpt >= level { return true }
            if let rank = HighlightData.bestRank(base: entry.headword, reading: reading, text: written), rank <= vocabulary {
                return true
            }
        }
        return false
    }
''', "known as written")

s = between(s, "    /// おじいさま → おじいさん, おじい, じい; ご主人様 → ご主人さん, ご主人, 主人; お手紙 → 手紙. Only words that start with\n",
            "    private var dictionaryHits: [String: Bool] = [:]", '''    /// おじいさま → おじいさん, おじい, じい; ご主人様 → ご主人さん, ご主人, 主人; お手紙 → 手紙; ばあちゃん → おばあさん,
    /// おばあちゃん, ばあさん. Without お, ご or 御 only the same word with other honorifics: 同様, 主君 or さかさま are
    /// not honorifics.
    static func honorificForms(_ word: String) -> [String] {
        guard let prefix = ["お", "ご", "御"].first(where: { word.hasPrefix($0) }) else {
            guard let suffix = ["さま", "さん", "ちゃん"].first(where: { word.hasSuffix($0) && word.count > $0.count }) else {
                return []
            }
            let stem = String(word.dropLast(suffix.count))
            var forms = ["お" + stem + "さん", "お" + stem + "ちゃん"]
            if suffix != "さん" {
                forms.append(stem + "さん")
            }
            return forms
        }
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

''', "honorific forms")

s = between(s, "    private var dictionaryHits: [String: Bool] = [:]\n", "/// One title (or one episode) of the Jiten library.",
            '''    private var writtenEntries: [String: [LookupEntry]] = [:]

    /// The word entries (names are not words) of a text the backend reads as one word; none when it splits the text.
    func entries(of written: String) -> [LookupEntry] {
        if let saved = writtenEntries[written] {
            return saved
        }
        let result = autoreleasepool { NativeLookup.tokenize(written, charAt: 0) }
        let found: [LookupEntry] = result.tokens.count == 1 ? result.entries : []
        writtenEntries[written] = found
        return found
    }

    /// The word has a word entry of its own: a name (it has only a name entry), a sound or a misread piece has none
    /// and is not a word to learn.
    func inDictionary(_ token: LookupToken) -> Bool {
        let base = token.base.isEmpty ? token.text : token.base
        let kana = reading(of: base)
        let written = HighlightData.hiragana(token.text)
        return entries(of: token.text).contains { entry in
            let reading = HighlightData.hiragana(entry.reading)
            return entry.headword == base || entry.headword == token.text || reading == written
                || (!kana.isEmpty && reading == kana)
        }
    }
}

''', "in dictionary")

# ---------- Jiten's lists without names ----------
s = once(s, '''            guard !word.isEmpty else { continue }
''', '''            guard !word.isEmpty else { continue }
            // names (JMnedict ids 5 000 000+): characters and places are not words to learn
            if let idColumn, idColumn < fields.count, let id = Int(fields[idColumn]), id >= 5_000_000, id < 6_000_000 {
                continue
            }
''', "csv names")
s = once(s, '''        let countColumn = header.firstIndex { $0.hasPrefix("Occur") } ?? 3
''', '''        let countColumn = header.firstIndex { $0.hasPrefix("Occur") } ?? 3
        let idColumn = header.firstIndex(of: "JmDictWordId")
''', "csv id column")
s = once(s, '''        let file = CatalogStore.folder.appendingPathComponent("words-" + String(id) + ".json")
''', '''        let file = JitenAPI.wordsFile(id)
''', "words file")
s = once(s, '''    /// Every word of a title with its count (one CSV download, kept in Caches/catalog for 30 days).
    /// `keep`: the list stays in the cache (the titles opened); the background counting does not keep it.
    static func words(_ id: Int, keep: Bool = true) async throws -> [CatalogWord] {
''', '''    /// The cached list of a title ("list-": without names, since 1.75).
    static func wordsFile(_ id: Int) -> URL {
        CatalogStore.folder.appendingPathComponent("list-" + String(id) + ".json")
    }

    /// Every word of a title with its count (one CSV download, kept in Caches/catalog for 30 days).
    static func words(_ id: Int, keep: Bool = true) async throws -> [CatalogWord] {
''', "words file func")

# ---------- the background counting: one at a time ----------
s = between(s, "/// Our coverage of the titles, counted in the background, three at a time: the rows on screen first, then a whole\n",
            "/// The badge of our coverage: the share in the colour of the difficulty.", r'''/// Our coverage of the titles, counted in the background one at a time: the rows on screen first, then the rest of a
/// list sorted by coverage. Jiten gives about ten word lists a minute: a pause after every download, a minute's wait
/// when it asks to slow down, and none at all while a title page downloads its own list.
@available(iOS 16.0, *)
@MainActor
final class CatalogCoverageQueue: ObservableObject {
    static let shared = CatalogCoverageQueue()

    @Published private(set) var results: [Int: CatalogCoverage] = [:]
    @Published private(set) var working: Set<Int> = []
    @Published private(set) var waiting: [Int] = []
    /// Jiten asked to slow down
    @Published private(set) var pausedByJiten = false
    private var failed = Set<Int>()
    /// asked as part of a whole list: a row leaving the screen does not take them out
    private var pinned = Set<Int>()
    private var worker: Task<Void, Never>? = nil
    /// title pages downloading their own lists
    private var held = 0
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

    /// A title page downloads its own list: the background waits.
    func hold(_ on: Bool) {
        held = max(0, held + (on ? 1 : -1))
    }

    private func start() {
        guard worker == nil, !waiting.isEmpty else { return }
        worker = Task { @MainActor in
            await run()
            worker = nil
        }
    }

    private func run() async {
        while !waiting.isEmpty {
            while held > 0 {
                try? await Task.sleep(nanoseconds: 500_000_000)
            }
            guard !waiting.isEmpty else { break }
            let id = waiting.removeFirst()
            working.insert(id)
            let cached = FileManager.default.fileExists(atPath: JitenAPI.wordsFile(id).path)
            do {
                let words = try await JitenAPI.words(id)
                let index = await CatalogStore.knownIndex()
                let now = currentStamp()
                let key = CatalogWordCache.key(index.fingerprint, now.level, now.vocabulary)
                let result = await Task.detached(priority: .utility) {
                    CatalogStore.coverage(of: words, index: index, level: now.level, vocabulary: now.vocabulary,
                                          cacheKey: key)
                }.value
                // the numbers only: the list of words is counted again when the title is opened (from the saved list)
                let summary = result.summary
                CatalogStore.save(summary, for: id)
                results[id] = summary
            } catch JimakuService.Failure.status(let code) where code == 429 {
                // Jiten asks to slow down: this title goes first after a minute
                working.remove(id)
                waiting.insert(id, at: 0)
                pausedByJiten = true
                try? await Task.sleep(nanoseconds: 60_000_000_000)
                pausedByJiten = false
                continue
            } catch {
                failed.insert(id)
            }
            working.remove(id)
            pinned.remove(id)
            if !cached {
                try? await Task.sleep(nanoseconds: 7_000_000_000)
            }
        }
    }
}

''', "catalog queue")

# ---------- the catalog list: kept when coming back, no "count all" ----------
s = once(s, "    @State private var showFilter = false\n    @State private var loadingAll = false\n",
         "    @State private var showFilter = false\n    /// the search the list shows: coming back from a title page does not search again\n"
         "    @State private var searchedKey: String? = nil\n", "searched key state")
s = between(s, "    /// Sorting by coverage: how many titles are counted, and a button that loads and counts the whole list.\n",
            "    private func row(_ deck: JitenDeck) -> some View {", '''    /// Sorting by coverage: how many of the loaded titles are counted.
    private var countAllRow: some View {
        let counted = countedCount
        let note: String = queue.pausedByJiten
            ? "Jiten просит подождать: продолжу через минуту."
            : "Jiten отдаёт около десяти словарей в минуту, поэтому тайтлы считаются по одному. Листайте ниже, чтобы добавить следующие."
        return HStack(spacing: 10) {
            VStack(alignment: .leading, spacing: 2) {
                Text("Посчитано " + String(counted) + " из " + String(results.count))
                Text(note)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            Spacer()
            if !queue.waiting.isEmpty || !queue.working.isEmpty {
                ProgressView()
            }
        }
    }

''', "count row")
s = once(s, '''        let text = query.trimmingCharacters(in: .whitespacesAndNewlines)
        // a new letter or filter cancels this task: Jiten is asked once the typing stops
        try? await Task.sleep(nanoseconds: 450_000_000)
''', '''        let text = query.trimmingCharacters(in: .whitespacesAndNewlines)
        // back from a title page: the list stays as it was, with its pages and progress
        let key = text + "|" + String(type) + "|" + String(describing: filter)
        if key == searchedKey, !results.isEmpty {
            return
        }
        // a new letter or filter cancels this task: Jiten is asked once the typing stops
        try? await Task.sleep(nanoseconds: 450_000_000)
''', "search kept")
s = once(s, '''            results = page.decks
            total = page.total
''', '''            results = page.decks
            total = page.total
            searchedKey = key
''', "search key saved")
s = once(s, "Text(\"Поиск по английскому, японскому и ромадзи названию. Покрытие считается само для тайтлов на экране, а при \"\n"
            "                     + \"сортировке «Моё покрытие» — для всего загруженного списка. Данные: Jiten (jiten.moe), CC BY-SA 4.0.\")",
         "Text(\"Поиск по английскому, японскому и ромадзи названию. Покрытие считается само, по одному тайтлу: сначала \"\n"
         "                     + \"тайтлы на экране, при сортировке «Моё покрытие» — весь загруженный список. Данные: Jiten (jiten.moe), CC BY-SA 4.0.\")",
         "catalog footer")

# ---------- a title page: its own list first, the unknown words counted on the spot ----------
s = once(s, '''                    NavigationLink(destination: CatalogUnknownView(title: shown.title, words: coverage.unknown)) {
                        row("Незнакомые слова", String(coverage.unknown.count))
                    }
                } else if working {''', '''                    if coverage.full != false {
                        NavigationLink(destination: CatalogUnknownView(title: shown.title, words: coverage.unknown)) {
                            row("Незнакомые слова", String(coverage.unknown.count))
                        }
                    } else if working {
                        // counted in the background: the list of words is counted now
                        HStack(spacing: 10) {
                            ProgressView()
                            Text(status)
                        }
                    } else {
                        if !status.isEmpty {
                            Text(status).foregroundColor(.secondary)
                        }
                        Button("Посчитать незнакомые слова") {
                            Task { await countCoverage() }
                        }
                    }
                } else if working {''', "detail words row")
s = between(s, "    private func countCoverage() async {\n", "/// The unknown words of a title, most frequent first;",
            '''    private func countCoverage() async {
        guard !working else { return }
        working = true
        defer { working = false }
        // the background waits: Jiten gives about ten lists a minute
        let queue = CatalogCoverageQueue.shared
        queue.hold(true)
        defer { queue.hold(false) }
        status = "Скачиваю словарь Jiten…"
        var loaded: [CatalogWord]? = nil
        for attempt in 0 ..< 4 {
            do {
                loaded = try await JitenAPI.words(deck.deckId)
                break
            } catch JimakuService.Failure.status(let code) where code == 429 && attempt < 3 {
                status = "Jiten просит подождать, повторю через 20 с…"
                try? await Task.sleep(nanoseconds: 20_000_000_000)
                if Task.isCancelled { return }
                status = "Скачиваю словарь Jiten…"
            } catch JimakuService.Failure.status(let code) {
                status = code == 429 ? "Jiten просит подождать. Попробуйте через минуту."
                    : "Jiten не отдал словарь (код " + String(code) + "). Попробуйте позже."
                return
            } catch {
                status = "Не удалось скачать словарь Jiten. Проверьте интернет."
                return
            }
        }
        guard let words = loaded else { return }
        status = "Считаю покрытие (" + String(words.count) + " слов)…"
        let index = await CatalogStore.knownIndex()
        let level = VideoLibraryStore.userLevel
        let vocabulary = VideoLibraryStore.vocabulary(level: level)
        let result = await Task.detached(priority: .userInitiated) {
            CatalogStore.coverage(of: words, index: index, level: level, vocabulary: vocabulary)
        }.value
        CatalogStore.save(result, for: deck.deckId)
        queue.store(deck.deckId, result)
        coverage = result
        status = ""
    }
}

''', "detail count")
hv.write_text(s, encoding="utf-8")
print("v1.75 catalog applied")
