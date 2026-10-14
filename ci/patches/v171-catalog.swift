
// MARK: - Known words (v1.71) and the catalog (Jiten)

/// Whether a word is known, by the same rules for the episodes and for the catalog: a card in any form, JLPT up to the
/// level, one of the `vocabulary` most frequent words; a merged expression (ここに) when all its content parts are
/// known; a noun made of a verb stem (守り) through the verb. One instance per background job (it caches readings).
@available(iOS 16.0, *)
final class WordKnowledge {
    let index: KnownWordsIndex
    let level: Int
    let vocabulary: Int
    private var readings: [String: String] = [:]

    init(index: KnownWordsIndex, level: Int, vocabulary: Int) {
        self.index = index
        self.level = level
        self.vocabulary = vocabulary
    }

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

    /// Content words only: no particles, auxiliaries, symbols, interjections, proper nouns, numbers, katakana-only
    /// words, Latin, reduplicated onomatopoeia.
    static func isContent(_ token: LookupToken) -> Bool {
        guard token.text.unicodeScalars.contains(where: { KnownWordsIndex.isJapanese($0) }) else { return false }
        if token.pos.hasPrefix("助詞") || token.pos.hasPrefix("助動詞") || token.pos.contains("記号") { return false }
        if token.pos.hasPrefix("感動詞") || token.pos2.contains("固有名詞") || token.pos2.contains("数詞") { return false }
        if KnownWordsIndex.isKatakana(token.text) || KnownWordsIndex.isReduplicated(token.text) { return false }
        return true
    }

    /// A content word; an expression made only of grammar is not a word.
    static func counted(_ token: LookupToken) -> Bool {
        guard isContent(token) else { return false }
        return token.parts.isEmpty || token.parts.contains { isContent($0) }
    }

    func known(_ token: LookupToken) -> Bool {
        let base = token.base.isEmpty ? token.text : token.base
        if isKnown(base: base, text: token.text, tokenReading: token.reading) { return true }
        let content = token.parts.filter { WordKnowledge.isContent($0) }
        if !content.isEmpty, content.allSatisfy({ part in
            isKnown(base: part.base.isEmpty ? part.text : part.base, text: part.text, tokenReading: part.reading)
        }) { return true }
        if let verb = KnownWordsIndex.verbOfNoun(base) {
            return isKnown(base: verb, text: verb, tokenReading: "")
        }
        return false
    }
}

/// One title (or one episode) of the Jiten library.
struct JitenDeck: Decodable, Identifiable {
    let deckId: Int
    var id: Int { deckId }
    let originalTitle: String?
    let romajiTitle: String?
    let englishTitle: String?
    let coverName: String?
    let mediaType: Int?
    let wordCount: Int?
    let uniqueWordCount: Int?
    let uniqueKanjiCount: Int?
    let difficulty: Double?
    let difficultyRaw: Double?
    let childrenDeckCount: Int?
    let speechSpeed: Double?

    var title: String {
        for name in [romajiTitle, englishTitle, originalTitle] {
            if let name, !name.isEmpty { return name }
        }
        return "—"
    }

    /// the other names, for the second line
    var subtitle: String {
        var names: [String] = []
        for name in [originalTitle, englishTitle] {
            if let name, !name.isEmpty, name != title, !names.contains(name) {
                names.append(name)
            }
        }
        return names.joined(separator: " · ")
    }

    /// Jiten difficulty, 0 (easy) … 5 (hard)
    var jitenDifficulty: Double? {
        difficultyRaw ?? difficulty
    }

    var coverURL: URL? {
        guard let name = coverName, name.hasPrefix("http") else { return nil }
        return URL(string: name)
    }
}

/// A word of a title: as Jiten counts it.
struct CatalogWord: Codable {
    let word: String
    let kana: String
    let count: Int
}

struct CatalogUnknown: Codable, Identifiable {
    let word: String
    let kana: String
    let count: Int
    var id: String { word + "|" + kana }
}

/// Our coverage of a title, kept until the known words, the level or the vocabulary change.
struct CatalogCoverage: Codable {
    let knownWords: UInt64
    let level: Int
    let vocabulary: Int
    /// share of the word occurrences that are known
    let known: Double
    /// share of the distinct words that are known
    let uniqueKnown: Double
    let words: Int
    let unknown: [CatalogUnknown]

    /// easy / normal / hard by the known words only (the catalog has no lines)
    var difficulty: Int {
        known >= 0.90 ? 0 : (known >= 0.80 ? 1 : 2)
    }
}

/// The public Jiten API (api.jiten.moe), asked only when the user opens the catalog; word lists are cached.
@available(iOS 16.0, *)
enum JitenAPI {
    static let base = "https://api.jiten.moe/api/media-deck/"

    private static func request(_ url: URL) -> URLRequest {
        var request = URLRequest(url: url, timeoutInterval: 30)
        request.setValue("Satori/1.71 (iOS)", forHTTPHeaderField: "User-Agent")
        return request
    }

    private static func get<T: Decodable>(_ url: URL) async throws -> T {
        let (data, response) = try await URLSession.shared.data(for: request(url))
        let status = (response as? HTTPURLResponse)?.statusCode ?? 0
        guard status == 200 else { throw JimakuService.Failure.status(status) }
        return try JSONDecoder().decode(T.self, from: data)
    }

    private struct Page: Decodable {
        let data: [JitenDeck]
    }

    private struct Detail: Decodable {
        struct Body: Decodable {
            let mainDeck: JitenDeck
            let subDecks: [JitenDeck]?
        }
        let data: Body
    }

    /// English, Japanese and romaji titles all match (the search is Jiten's).
    static func search(_ query: String, type: Int) async throws -> [JitenDeck] {
        guard var parts = URLComponents(string: base + "get-media-decks") else { return [] }
        var items = [URLQueryItem(name: "mediaType", value: String(type))]
        if !query.isEmpty {
            items.append(URLQueryItem(name: "titleFilter", value: query))
        }
        parts.queryItems = items
        guard let url = parts.url else { return [] }
        let page: Page = try await get(url)
        return page.data
    }

    /// The title and 25 of its episodes from `offset`.
    static func detail(_ id: Int, offset: Int) async throws -> (deck: JitenDeck, episodes: [JitenDeck]) {
        guard let url = URL(string: base + String(id) + "/detail?offset=" + String(offset)) else {
            throw JimakuService.Failure.badURL
        }
        let detail: Detail = try await get(url)
        return (detail.data.mainDeck, detail.data.subDecks ?? [])
    }

    /// Every word of a title with its count (one CSV download, kept in Caches/catalog for 30 days).
    static func words(_ id: Int) async throws -> [CatalogWord] {
        let file = CatalogStore.folder.appendingPathComponent("words-" + String(id) + ".json")
        if let attributes = try? FileManager.default.attributesOfItem(atPath: file.path),
           let date = attributes[.modificationDate] as? Date, Date().timeIntervalSince(date) < 30 * 86400,
           let data = try? Data(contentsOf: file),
           let saved = try? JSONDecoder().decode([CatalogWord].self, from: data) {
            return saved
        }
        guard let url = URL(string: base + String(id) + "/download") else { throw JimakuService.Failure.badURL }
        var post = request(url)
        post.httpMethod = "POST"
        post.setValue("application/json", forHTTPHeaderField: "Content-Type")
        // CSV, the whole deck, most frequent first, no example sentences
        post.httpBody = Data(#"{"format":2,"downloadType":1,"order":3,"excludeExampleSentences":true}"#.utf8)
        let (data, response) = try await URLSession.shared.data(for: post)
        let status = (response as? HTTPURLResponse)?.statusCode ?? 0
        guard status == 200 else { throw JimakuService.Failure.status(status) }
        let words = CatalogStore.parseCSV(String(decoding: data, as: UTF8.self))
        if let encoded = try? JSONEncoder().encode(words) {
            try? encoded.write(to: file)
        }
        return words
    }
}

/// The catalog cache and the coverage of a title.
@available(iOS 16.0, *)
enum CatalogStore {
    static var folder: URL {
        let base = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask)[0].appendingPathComponent("catalog")
        try? FileManager.default.createDirectory(at: base, withIntermediateDirectories: true)
        return base
    }

    private static func coverageFile(_ id: Int) -> URL {
        folder.appendingPathComponent("coverage-" + String(id) + ".json")
    }

    /// The saved coverage, when it was counted with the same known words, level and vocabulary.
    static func saved(_ id: Int, knownWords: UInt64, level: Int, vocabulary: Int) -> CatalogCoverage? {
        guard let data = try? Data(contentsOf: coverageFile(id)),
              let saved = try? JSONDecoder().decode(CatalogCoverage.self, from: data),
              saved.knownWords == knownWords, saved.level == level, saved.vocabulary == vocabulary else { return nil }
        return saved
    }

    static func save(_ coverage: CatalogCoverage, for id: Int) {
        if let data = try? JSONEncoder().encode(coverage) {
            try? data.write(to: coverageFile(id))
        }
    }

    /// "Word","ReadingFurigana","ReadingKana","Occurences",…: quoted fields, "" inside a field is a quote.
    static func parseCSV(_ text: String) -> [CatalogWord] {
        var rows: [[String]] = []
        var row: [String] = []
        var field = ""
        var quoted = false
        var iterator = text.makeIterator()
        var pending: Character? = nil
        while let char = pending ?? iterator.next() {
            pending = nil
            if quoted {
                if char == "\"" {
                    if let next = iterator.next() {
                        if next == "\"" {
                            field.append("\"")
                        } else {
                            quoted = false
                            pending = next
                        }
                    } else {
                        quoted = false
                    }
                } else {
                    field.append(char)
                }
            } else if char == "\"" {
                quoted = true
            } else if char == "," {
                row.append(field)
                field = ""
            } else if char == "\n" || char == "\r\n" || char == "\r" {
                row.append(field)
                field = ""
                rows.append(row)
                row = []
            } else {
                field.append(char)
            }
        }
        if !field.isEmpty || !row.isEmpty {
            row.append(field)
            rows.append(row)
        }
        guard let header = rows.first else { return [] }
        let wordColumn = header.firstIndex(of: "Word") ?? 0
        let kanaColumn = header.firstIndex(of: "ReadingKana") ?? 2
        let countColumn = header.firstIndex { $0.hasPrefix("Occur") } ?? 3
        var words: [CatalogWord] = []
        for fields in rows.dropFirst() where fields.count > max(wordColumn, kanaColumn, countColumn) {
            let word = fields[wordColumn]
            guard !word.isEmpty else { continue }
            words.append(CatalogWord(word: word, kana: fields[kanaColumn], count: Int(fields[countColumn]) ?? 1))
        }
        return words
    }

    /// Our coverage of a title: every word of Jiten's list is read by our tokenizer, filtered and judged like the
    /// words of the subtitles; the shares are weighted by how often the words occur.
    static func coverage(of words: [CatalogWord], index: KnownWordsIndex, level: Int,
                         vocabulary: Int) -> CatalogCoverage {
        let judge = WordKnowledge(index: index, level: level, vocabulary: vocabulary)
        var total = 0
        var knownTotal = 0
        var distinct = 0
        var knownDistinct = 0
        var unknown: [CatalogUnknown] = []
        for item in words {
            let tokens = autoreleasepool { NativeLookup.tokenize(item.word, charAt: 0).tokens }
            guard let first = tokens.first else { continue }
            var token = first
            if tokens.count > 1 {
                let main = tokens.first { WordKnowledge.isContent($0) } ?? first
                token = LookupToken(id: 0, text: item.word, start: 0, base: item.word, reading: item.kana,
                                    pos: main.pos, pos2: main.pos2, parts: tokens)
            }
            guard WordKnowledge.counted(token) else { continue }
            distinct += 1
            total += item.count
            if judge.known(token) {
                knownDistinct += 1
                knownTotal += item.count
            } else if unknown.count < 500 {
                unknown.append(CatalogUnknown(word: item.word, kana: item.kana, count: item.count))
            }
        }
        let known = total > 0 ? Double(knownTotal) / Double(total) : 0
        let uniqueKnown = distinct > 0 ? Double(knownDistinct) / Double(distinct) : 0
        unknown.sort { $0.count > $1.count }
        return CatalogCoverage(knownWords: index.fingerprint, level: level, vocabulary: vocabulary, known: known,
                               uniqueKnown: uniqueKnown, words: distinct, unknown: unknown)
    }

    private static var index: KnownWordsIndex?

    /// The known word index, built again when the known words change (on the main thread: the tables load here).
    @MainActor
    static func knownIndex() async -> KnownWordsIndex {
        let known = HighlightData.minedWords()
        _ = HighlightData.jlptLevel(base: "の", reading: "の")
        _ = HighlightData.rank(base: "の", reading: "の", dict: "main")
        if let index, index.fingerprint == KnownWordsIndex.fingerprint(known) {
            return index
        }
        let built = await Task.detached(priority: .userInitiated) { KnownWordsIndex(known) }.value
        index = built
        return built
    }

    static func percent(_ value: Double) -> String {
        String(Int((value * 100).rounded())) + "%"
    }

    static func difficultyName(_ value: Int) -> String {
        ["easy", "normal", "hard"][min(max(value, 0), 2)]
    }

    static func difficultyColor(_ value: Int) -> Color {
        [Color.green, Color.yellow, Color.red][min(max(value, 0), 2)]
    }

    static func jitenText(_ value: Double?) -> String {
        guard let value else { return "—" }
        return String(format: "%.1f", value).replacingOccurrences(of: ".", with: ",") + " из 5"
    }
}

/// The cover of a title.
@available(iOS 16.0, *)
struct CatalogCover: View {
    let url: URL?
    var width: CGFloat = 46

    var body: some View {
        AsyncImage(url: url) { image in
            image.resizable().scaledToFill()
        } placeholder: {
            Color.secondary.opacity(0.2)
        }
        .frame(width: width, height: width * 1.42)
        .clipShape(RoundedRectangle(cornerRadius: 6, style: .continuous))
    }
}

/// The library of Jiten: anime, dramas and films with their difficulty, and our coverage of them.
@available(iOS 16.0, *)
struct CatalogView: View {
    @State private var query = ""
    @State private var type = 1
    @State private var results: [JitenDeck] = []
    @State private var loading = false
    @State private var message = ""
    @State private var knownWords: UInt64 = 0

    var body: some View {
        List {
            Section {
                Picker("Тип", selection: $type) {
                    Text("Аниме").tag(1)
                    Text("Дорамы").tag(2)
                    Text("Фильмы").tag(3)
                }
                .pickerStyle(.segmented)
            }
            Section {
                if loading && results.isEmpty {
                    HStack(spacing: 10) {
                        ProgressView()
                        Text("Ищу…")
                    }
                } else if !message.isEmpty {
                    Text(message).foregroundColor(.secondary)
                }
                ForEach(results) { deck in
                    NavigationLink(destination: CatalogDetailView(deck: deck)) {
                        row(deck)
                    }
                }
            } footer: {
                Text("Поиск по английскому, японскому и ромадзи названию. Данные: Jiten (jiten.moe), CC BY-SA 4.0.")
            }
        }
        .navigationTitle("Каталог")
        .searchable(text: $query, prompt: "Название: English, 日本語, rōmaji")
        .autocorrectionDisabled()
        .task(id: query + "|" + String(type)) {
            await search()
        }
        .onAppear {
            knownWords = KnownWordsIndex.fingerprint(HighlightData.minedWords())
        }
    }

    private func row(_ deck: JitenDeck) -> some View {
        let level = VideoLibraryStore.userLevel
        let saved = CatalogStore.saved(deck.deckId, knownWords: knownWords, level: level,
                                       vocabulary: VideoLibraryStore.vocabulary(level: level))
        return HStack(spacing: 12) {
            CatalogCover(url: deck.coverURL)
            VStack(alignment: .leading, spacing: 4) {
                Text(deck.title).lineLimit(2)
                if !deck.subtitle.isEmpty {
                    Text(deck.subtitle)
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .lineLimit(1)
                }
                HStack(spacing: 8) {
                    Text("Jiten " + CatalogStore.jitenText(deck.jitenDifficulty))
                        .font(.caption2.bold())
                        .foregroundColor(.secondary)
                    if let episodes = deck.childrenDeckCount, episodes > 0 {
                        Text(String(episodes) + " сер.")
                            .font(.caption2)
                            .foregroundColor(.secondary)
                    }
                    if let saved {
                        Text(CatalogStore.percent(saved.known))
                            .font(.caption2.bold())
                            .foregroundColor(.black)
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(CatalogStore.difficultyColor(saved.difficulty).opacity(0.85))
                            .cornerRadius(4)
                    }
                }
            }
        }
    }

    private func search() async {
        let text = query.trimmingCharacters(in: .whitespacesAndNewlines)
        // a new letter cancels this task: Jiten is asked once the typing stops
        try? await Task.sleep(nanoseconds: 450_000_000)
        guard !Task.isCancelled else { return }
        loading = true
        defer { loading = false }
        do {
            let found = try await JitenAPI.search(text, type: type)
            guard !Task.isCancelled else { return }
            results = found
            message = found.isEmpty ? "Ничего не найдено" : ""
        } catch {
            if !Task.isCancelled {
                message = "Нет связи с Jiten"
            }
        }
    }
}

/// A title or an episode: Jiten's numbers, our coverage and the unknown words; the episodes of a series.
@available(iOS 16.0, *)
struct CatalogDetailView: View {
    let deck: JitenDeck
    @State private var detail: JitenDeck? = nil
    @State private var episodes: [JitenDeck] = []
    @State private var coverage: CatalogCoverage? = nil
    @State private var status = ""
    @State private var working = false
    @State private var loadingMore = false

    private var shown: JitenDeck {
        detail ?? deck
    }

    var body: some View {
        List {
            Section {
                HStack(alignment: .top, spacing: 14) {
                    CatalogCover(url: shown.coverURL, width: 84)
                    VStack(alignment: .leading, spacing: 6) {
                        Text(shown.title).font(.headline)
                        if !shown.subtitle.isEmpty {
                            Text(shown.subtitle).font(.subheadline).foregroundColor(.secondary)
                        }
                    }
                }
                .padding(.vertical, 4)
            }
            Section {
                if let coverage {
                    row("Знакомых слов", CatalogStore.percent(coverage.known))
                    HStack {
                        Text("Оценка")
                        Spacer()
                        Text(CatalogStore.difficultyName(coverage.difficulty))
                            .font(.callout.bold())
                            .foregroundColor(coverage.difficulty == 2 ? .white : .black)
                            .padding(.horizontal, 8)
                            .padding(.vertical, 2)
                            .background(CatalogStore.difficultyColor(coverage.difficulty).opacity(0.85))
                            .cornerRadius(5)
                    }
                    row("Знакомых разных слов", CatalogStore.percent(coverage.uniqueKnown))
                    NavigationLink(destination: CatalogUnknownView(title: shown.title, words: coverage.unknown)) {
                        row("Незнакомые слова", String(coverage.unknown.count))
                    }
                } else if working {
                    HStack(spacing: 10) {
                        ProgressView()
                        Text(status)
                    }
                } else {
                    if !status.isEmpty {
                        Text(status).foregroundColor(.secondary)
                    }
                    Button("Посчитать покрытие") {
                        Task { await countCoverage() }
                    }
                }
            } header: {
                Text("Ваше покрытие")
            } footer: {
                Text("Знакомыми считаются ваши карточки, слова JLPT до вашего уровня и частые слова (Настройки → «Мой уровень японского»). Доля учитывает, как часто слово встречается. Оценка: easy от 90%, normal от 80%.")
            }
            Section {
                row("Сложность", CatalogStore.jitenText(shown.jitenDifficulty))
                if let words = shown.wordCount {
                    row("Слов", String(words))
                }
                if let unique = shown.uniqueWordCount {
                    row("Разных слов", String(unique))
                }
                if let kanji = shown.uniqueKanjiCount {
                    row("Разных кандзи", String(kanji))
                }
                if let speed = shown.speechSpeed, speed > 0 {
                    row("Скорость речи", String(Int(speed.rounded())) + " мор/мин")
                }
            } header: {
                Text("Jiten")
            }
            if !episodes.isEmpty {
                Section {
                    ForEach(episodes) { episode in
                        NavigationLink(destination: CatalogDetailView(deck: episode)) {
                            HStack {
                                Text(episode.title)
                                Spacer()
                                Text(CatalogStore.jitenText(episode.jitenDifficulty))
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
                        }
                    }
                    if episodes.count < (shown.childrenDeckCount ?? 0) {
                        Button(loadingMore ? "Загружаю…" : "Ещё серии") {
                            Task { await loadMore() }
                        }
                        .disabled(loadingMore)
                    }
                } header: {
                    Text("Серии")
                }
            }
            Section {
            } footer: {
                Text("Данные: Jiten (jiten.moe), CC BY-SA 4.0.")
            }
        }
        .navigationTitle(shown.title)
        .navigationBarTitleDisplayMode(.inline)
        .task {
            await load()
        }
    }

    private func row(_ title: String, _ value: String) -> some View {
        HStack {
            Text(title)
            Spacer()
            Text(value).foregroundColor(.secondary)
        }
    }

    private func load() async {
        guard detail == nil else { return }
        if let found = try? await JitenAPI.detail(deck.deckId, offset: 0) {
            detail = found.deck
            episodes = found.episodes
        }
        let level = VideoLibraryStore.userLevel
        let vocabulary = VideoLibraryStore.vocabulary(level: level)
        let knownWords = KnownWordsIndex.fingerprint(HighlightData.minedWords())
        if let saved = CatalogStore.saved(deck.deckId, knownWords: knownWords, level: level, vocabulary: vocabulary) {
            coverage = saved
        } else {
            await countCoverage()
        }
    }

    private func loadMore() async {
        loadingMore = true
        defer { loadingMore = false }
        if let found = try? await JitenAPI.detail(deck.deckId, offset: episodes.count) {
            let known = Set(episodes.map { $0.deckId })
            episodes += found.episodes.filter { !known.contains($0.deckId) }
        }
    }

    private func countCoverage() async {
        guard !working else { return }
        working = true
        defer { working = false }
        status = "Скачиваю словарь Jiten…"
        do {
            let words = try await JitenAPI.words(deck.deckId)
            status = "Считаю покрытие (" + String(words.count) + " слов)…"
            let index = await CatalogStore.knownIndex()
            let level = VideoLibraryStore.userLevel
            let vocabulary = VideoLibraryStore.vocabulary(level: level)
            let result = await Task.detached(priority: .userInitiated) {
                CatalogStore.coverage(of: words, index: index, level: level, vocabulary: vocabulary)
            }.value
            CatalogStore.save(result, for: deck.deckId)
            coverage = result
            status = ""
        } catch {
            status = "Не удалось скачать словарь Jiten. Проверьте интернет."
        }
    }
}

/// The unknown words of a title, most frequent first; a tap opens the dictionary (with ⊕ for Anki).
@available(iOS 16.0, *)
struct CatalogUnknownView: View {
    let title: String
    let words: [CatalogUnknown]
    @State private var lookup: CatalogUnknown? = nil

    var body: some View {
        List {
            Section {
                ForEach(words) { word in
                    Button {
                        lookup = word
                    } label: {
                        HStack {
                            VStack(alignment: .leading, spacing: 2) {
                                Text(word.word)
                                    .font(.system(size: 20))
                                    .foregroundColor(.primary)
                                if !word.kana.isEmpty && word.kana != word.word {
                                    Text(word.kana)
                                        .font(.caption)
                                        .foregroundColor(.secondary)
                                }
                            }
                            Spacer()
                            Text("×" + String(word.count))
                                .foregroundColor(.secondary)
                        }
                    }
                }
            } footer: {
                Text("Самые частые незнакомые слова (до 500). Нажмите на слово, чтобы открыть словарь и добавить его в Anki.")
            }
        }
        .navigationTitle("Незнакомые слова")
        .navigationBarTitleDisplayMode(.inline)
        .sheet(item: $lookup) { word in
            WordLookupSheet(text: word.word)
        }
    }
}
