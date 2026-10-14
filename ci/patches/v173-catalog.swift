/// Covers of the catalog: small copies kept in memory and in Caches/catalog (a Jiten cover is a full-size picture).
enum CoverCache {
    private static let memory = NSCache<NSURL, UIImage>()

    static func image(_ url: URL?) async -> UIImage? {
        guard let url else { return nil }
        if let hit = memory.object(forKey: url as NSURL) {
            return hit
        }
        let name = url.pathComponents.filter { $0 != "/" }.joined(separator: "-")
        let base = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("catalog-covers")
        try? FileManager.default.createDirectory(at: base, withIntermediateDirectories: true)
        let file = base.appendingPathComponent(name)
        if let saved = UIImage(contentsOfFile: file.path) {
            memory.setObject(saved, forKey: url as NSURL)
            return saved
        }
        var request = URLRequest(url: url, timeoutInterval: 20)
        request.setValue("Satori/1.73 (iOS)", forHTTPHeaderField: "User-Agent")
        guard let loaded = try? await URLSession.shared.data(for: request),
              let small = downsample(loaded.0, maxPixels: 300) else { return nil }
        memory.setObject(small, forKey: url as NSURL)
        try? small.jpegData(compressionQuality: 0.8)?.write(to: file)
        return small
    }

    private static func downsample(_ data: Data, maxPixels: Int) -> UIImage? {
        guard let source = CGImageSourceCreateWithData(data as CFData, nil) else { return nil }
        let options: [CFString: Any] = [
            kCGImageSourceCreateThumbnailFromImageAlways: true,
            kCGImageSourceThumbnailMaxPixelSize: maxPixels,
            kCGImageSourceCreateThumbnailWithTransform: true,
        ]
        guard let image = CGImageSourceCreateThumbnailAtIndex(source, 0, options as CFDictionary) else { return nil }
        return UIImage(cgImage: image)
    }
}

/// The cover of a title.
@available(iOS 16.0, *)
struct CatalogCover: View {
    let url: URL?
    var width: CGFloat = 46
    @State private var image: UIImage? = nil

    var body: some View {
        ZStack {
            if let image {
                Image(uiImage: image)
                    .resizable()
                    .scaledToFill()
            } else {
                Color.secondary.opacity(0.2)
            }
        }
        .frame(width: width, height: width * 1.42)
        .clipShape(RoundedRectangle(cornerRadius: 6, style: .continuous))
        .task(id: url) {
            image = await CoverCache.image(url)
        }
    }
}

/// Filters and sorting of the catalog (kept between launches).
struct CatalogFilter: Codable, Equatable {
    var sort = "popularity"
    var descending = true
    var difficultyMin: Double = 0
    var difficultyMax: Double = 5
    var yearMin = 0
    var genres: [Int] = []
    var excludeSequels = false

    static let sorts: [(id: String, name: String)] = [
        ("popularity", "Популярность"), ("coverage", "Моё покрытие"), ("difficulty", "Сложность Jiten"),
        ("releaseDate", "Дата выхода"), ("wordCount", "Объём (слов)"), ("title", "Название"),
    ]

    static let genreNames: [(id: Int, name: String)] = [
        (1, "Боевик"), (2, "Приключения"), (3, "Комедия"), (4, "Драма"), (6, "Фэнтези"), (14, "Повседневность"),
        (12, "Романтика"), (10, "Детектив"), (11, "Психологическое"), (13, "Фантастика"), (16, "Сверхъестественное"),
        (17, "Триллер"), (7, "Ужасы"), (9, "Музыка"), (15, "Спорт"), (8, "Меха"), (5, "Этти"),
    ]

    var isDefault: Bool {
        self == CatalogFilter()
    }

    /// The parameters for Jiten; "coverage" sorts here, on the phone (Jiten does not know our words).
    var queryItems: [URLQueryItem] {
        var items: [URLQueryItem] = []
        let apiSort: String = sort == "coverage" ? "popularity" : sort
        items.append(URLQueryItem(name: "sortBy", value: apiSort))
        items.append(URLQueryItem(name: "sortOrder", value: descending || sort == "coverage" ? "1" : "0"))
        if difficultyMin > 0 {
            items.append(URLQueryItem(name: "difficultyMin", value: String(difficultyMin)))
        }
        if difficultyMax < 5 {
            items.append(URLQueryItem(name: "difficultyMax", value: String(difficultyMax)))
        }
        if yearMin > 0 {
            items.append(URLQueryItem(name: "releaseYearMin", value: String(yearMin)))
        }
        if !genres.isEmpty {
            items.append(URLQueryItem(name: "genres", value: genres.map(String.init).joined(separator: ",")))
        }
        if excludeSequels {
            items.append(URLQueryItem(name: "excludeSequels", value: "true"))
        }
        return items
    }

    static func load() -> CatalogFilter {
        guard let data = UserDefaults.standard.data(forKey: "catalog.filter.v1"),
              let saved = try? JSONDecoder().decode(CatalogFilter.self, from: data) else { return CatalogFilter() }
        return saved
    }

    func save() {
        if let data = try? JSONEncoder().encode(self) {
            UserDefaults.standard.set(data, forKey: "catalog.filter.v1")
        }
    }
}

@available(iOS 16.0, *)
extension JitenAPI {
    private struct BrowsePage: Decodable {
        let data: [JitenDeck]
        let totalItems: Int?
    }

    /// A page of 50 titles: the search (English, Japanese, romaji) with the filters and the sorting.
    static func browse(_ query: String, type: Int, filter: CatalogFilter, offset: Int) async throws -> (decks: [JitenDeck], total: Int) {
        guard var parts = URLComponents(string: base + "get-media-decks") else { return ([], 0) }
        var items = [URLQueryItem(name: "mediaType", value: String(type)), URLQueryItem(name: "offset", value: String(offset))]
        if !query.isEmpty {
            items.append(URLQueryItem(name: "titleFilter", value: query))
        }
        parts.queryItems = items + filter.queryItems
        guard let url = parts.url else { return ([], 0) }
        var request = URLRequest(url: url, timeoutInterval: 30)
        request.setValue("Satori/1.73 (iOS)", forHTTPHeaderField: "User-Agent")
        let (data, response) = try await URLSession.shared.data(for: request)
        let status = (response as? HTTPURLResponse)?.statusCode ?? 0
        guard status == 200 else { throw JimakuService.Failure.status(status) }
        let page = try JSONDecoder().decode(BrowsePage.self, from: data)
        return (page.data, page.totalItems ?? page.data.count)
    }
}

/// Our coverage of the titles on screen, counted one by one in the background (the newest request first): the
/// rows show it without opening a title. Jiten is asked at most about once a second.
@available(iOS 16.0, *)
@MainActor
final class CatalogCoverageQueue: ObservableObject {
    static let shared = CatalogCoverageQueue()

    @Published private(set) var results: [Int: CatalogCoverage] = [:]
    @Published private(set) var working: Int? = nil
    @Published private(set) var waiting: [Int] = []
    private var failed = Set<Int>()
    private var worker: Task<Void, Never>? = nil
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

    /// A row came on screen.
    func request(_ id: Int) {
        let now = currentStamp()
        guard results[id] == nil, !failed.contains(id), working != id else { return }
        if let saved = CatalogStore.saved(id, knownWords: now.knownWords, level: now.level, vocabulary: now.vocabulary) {
            results[id] = saved
            return
        }
        waiting.removeAll { $0 == id }
        waiting.insert(id, at: 0)
        if waiting.count > 40 {
            waiting.removeLast(waiting.count - 40)
        }
        start()
    }

    /// A row left the screen before its turn.
    func forget(_ id: Int) {
        waiting.removeAll { $0 == id }
    }

    private func start() {
        guard worker == nil, !waiting.isEmpty else { return }
        worker = Task { @MainActor in
            while !waiting.isEmpty {
                let id = waiting.removeFirst()
                working = id
                let cached = FileManager.default.fileExists(atPath: CatalogStore.folder
                    .appendingPathComponent("words-" + String(id) + ".json").path)
                do {
                    let words = try await JitenAPI.words(id)
                    let index = await CatalogStore.knownIndex()
                    let now = currentStamp()
                    let result = await Task.detached(priority: .utility) {
                        CatalogStore.coverage(of: words, index: index, level: now.level, vocabulary: now.vocabulary)
                    }.value
                    CatalogStore.save(result, for: id)
                    results[id] = result
                } catch {
                    failed.insert(id)
                }
                working = nil
                if !cached {
                    try? await Task.sleep(nanoseconds: 900_000_000)
                }
            }
            worker = nil
        }
    }
}

/// The badge of our coverage: the share in the colour of the difficulty.
@available(iOS 16.0, *)
struct CoverageBadge: View {
    let known: Double
    let difficulty: Int?

    var body: some View {
        let step: Int = difficulty ?? (known >= 0.90 ? 0 : (known >= 0.80 ? 1 : 2))
        Text(CatalogStore.percent(known))
            .font(.caption2.bold())
            .foregroundColor(step == 2 ? .white : .black)
            .padding(.horizontal, 6)
            .padding(.vertical, 2)
            .background(CatalogStore.difficultyColor(step).opacity(0.85))
            .cornerRadius(4)
    }
}

/// The library of Jiten: anime, dramas and films, with filters and sorting, and our coverage of every title.
@available(iOS 16.0, *)
struct CatalogView: View {
    @ObservedObject private var queue = CatalogCoverageQueue.shared
    @State private var query = ""
    @State private var type = 1
    @State private var filter = CatalogFilter.load()
    @State private var results: [JitenDeck] = []
    @State private var total = 0
    @State private var loading = false
    @State private var loadingMore = false
    @State private var message = ""
    @State private var showFilter = false

    /// "Моё покрытие": the titles counted first, by coverage; the others after them in Jiten's order.
    private var shown: [JitenDeck] {
        guard filter.sort == "coverage" else { return results }
        let counted = results.filter { queue.results[$0.deckId] != nil }
            .sorted { (queue.results[$0.deckId]?.known ?? 0) > (queue.results[$1.deckId]?.known ?? 0) }
        let rest = results.filter { queue.results[$0.deckId] == nil }
        return counted + rest
    }

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
                ForEach(shown) { deck in
                    NavigationLink(destination: CatalogDetailView(deck: deck)) {
                        row(deck)
                    }
                    .onAppear {
                        queue.request(deck.deckId)
                    }
                    .onDisappear {
                        queue.forget(deck.deckId)
                    }
                }
                if results.count < total {
                    HStack(spacing: 10) {
                        ProgressView()
                        Text("Загружаю ещё…").foregroundColor(.secondary)
                    }
                    .onAppear {
                        Task { await loadMore() }
                    }
                }
            } header: {
                if total > 0 {
                    Text("Найдено: " + String(total))
                }
            } footer: {
                Text("Поиск по английскому, японскому и ромадзи названию. Покрытие считается само для тайтлов на экране. Данные: Jiten (jiten.moe), CC BY-SA 4.0.")
            }
        }
        .navigationTitle("Каталог")
        .navigationBarTitleDisplayMode(.inline)
        .searchable(text: $query, placement: .navigationBarDrawer(displayMode: .always),
                    prompt: "Название: English, 日本語, rōmaji")
        .autocorrectionDisabled()
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                Button {
                    showFilter = true
                } label: {
                    Image(systemName: filter.isDefault ? "line.3.horizontal.decrease.circle"
                          : "line.3.horizontal.decrease.circle.fill")
                }
            }
        }
        .sheet(isPresented: $showFilter) {
            CatalogFilterSheet(filter: $filter)
        }
        .task(id: query + "|" + String(type) + "|" + String(describing: filter)) {
            await search()
        }
    }

    private func row(_ deck: JitenDeck) -> some View {
        HStack(spacing: 12) {
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
                    if let coverage = queue.results[deck.deckId] {
                        CoverageBadge(known: coverage.known, difficulty: coverage.difficulty)
                    } else if queue.working == deck.deckId {
                        ProgressView().scaleEffect(0.6)
                    }
                }
            }
        }
    }

    private func search() async {
        let text = query.trimmingCharacters(in: .whitespacesAndNewlines)
        // a new letter or filter cancels this task: Jiten is asked once the typing stops
        try? await Task.sleep(nanoseconds: 450_000_000)
        guard !Task.isCancelled else { return }
        filter.save()
        loading = true
        defer { loading = false }
        do {
            let page = try await JitenAPI.browse(text, type: type, filter: filter, offset: 0)
            guard !Task.isCancelled else { return }
            results = page.decks
            total = page.total
            message = page.decks.isEmpty ? "Ничего не найдено" : ""
        } catch {
            if !Task.isCancelled {
                message = "Нет связи с Jiten"
            }
        }
    }

    private func loadMore() async {
        guard !loadingMore, results.count < total else { return }
        loadingMore = true
        defer { loadingMore = false }
        let text = query.trimmingCharacters(in: .whitespacesAndNewlines)
        if let page = try? await JitenAPI.browse(text, type: type, filter: filter, offset: results.count) {
            let known = Set(results.map { $0.deckId })
            let fresh = page.decks.filter { !known.contains($0.deckId) }
            results += fresh
            if fresh.isEmpty {
                total = results.count
            }
        }
    }
}

/// Sorting and filters of the catalog.
@available(iOS 16.0, *)
struct CatalogFilterSheet: View {
    @Binding var filter: CatalogFilter
    @Environment(\.dismiss) private var dismiss

    private var years: [Int] {
        Array(stride(from: 2025, through: 1980, by: -5))
    }

    var body: some View {
        NavigationView {
            Form {
                Section {
                    Picker("Сортировка", selection: $filter.sort) {
                        ForEach(CatalogFilter.sorts, id: \.id) { item in
                            Text(item.name).tag(item.id)
                        }
                    }
                    if filter.sort != "coverage" {
                        Toggle("По убыванию", isOn: $filter.descending)
                    }
                } header: {
                    Text("Сортировка")
                } footer: {
                    Text("«Моё покрытие» ставит выше тайтлы, которые вы поймёте лучше всего (среди уже посчитанных).")
                }
                Section {
                    Stepper(value: $filter.difficultyMin, in: 0 ... filter.difficultyMax, step: 0.5) {
                        HStack {
                            Text("От")
                            Spacer()
                            Text(String(format: "%.1f", filter.difficultyMin)).foregroundColor(.secondary)
                        }
                    }
                    Stepper(value: $filter.difficultyMax, in: filter.difficultyMin ... 5, step: 0.5) {
                        HStack {
                            Text("До")
                            Spacer()
                            Text(String(format: "%.1f", filter.difficultyMax)).foregroundColor(.secondary)
                        }
                    }
                } header: {
                    Text("Сложность Jiten (0–5)")
                }
                Section {
                    Picker("Выход не раньше", selection: $filter.yearMin) {
                        Text("Любой год").tag(0)
                        ForEach(years, id: \.self) { year in
                            Text(String(year)).tag(year)
                        }
                    }
                    Toggle("Без сиквелов", isOn: $filter.excludeSequels)
                }
                Section {
                    ForEach(CatalogFilter.genreNames, id: \.id) { genre in
                        Button {
                            toggle(genre.id)
                        } label: {
                            HStack {
                                Text(genre.name).foregroundColor(.primary)
                                Spacer()
                                if filter.genres.contains(genre.id) {
                                    Image(systemName: "checkmark").foregroundColor(.accentColor)
                                }
                            }
                        }
                    }
                } header: {
                    Text("Жанры")
                } footer: {
                    Text("Несколько жанров — тайтлы, в которых есть все выбранные.")
                }
                Section {
                    Button("Сбросить фильтры", role: .destructive) {
                        filter = CatalogFilter()
                    }
                    .disabled(filter.isDefault)
                }
            }
            .navigationTitle("Фильтры")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Готово") { dismiss() }
                }
            }
        }
    }

    private func toggle(_ id: Int) {
        if let index = filter.genres.firstIndex(of: id) {
            filter.genres.remove(at: index)
        } else {
            filter.genres.append(id)
        }
    }
}

