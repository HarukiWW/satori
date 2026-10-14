
// MARK: - Reading: web novels from Syosetu (v1.72)

/// A web novel saved for offline reading: its table of contents and the reading state.
struct NovelInfo: Codable, Identifiable {
    let ncode: String
    var title: String
    var writer: String
    var story: String
    var shortStory: Bool
    var finished: Bool
    var episodes: [NovelEpisode]
    var addedAt: Date
    /// episodes read to the end
    var read: Set<Int> = []
    var lastRead: Int? = nil
    /// the first paragraph shown last time, per episode
    var positions: [Int: Int] = [:]
    var id: String { ncode }
}

struct NovelEpisode: Codable, Identifiable {
    let number: Int
    let title: String
    /// the chapter (章) / volume the episode belongs to, "" without one
    let volume: String
    var id: Int { number }
}

/// The text of one episode: plain paragraphs (ruby, links and pictures removed).
struct NovelText: Codable {
    let title: String
    let chapter: String
    let preface: [String]
    let body: [String]
    let afterword: [String]
}

/// A search result of the Syosetu API.
struct SyosetuHit: Identifiable {
    let ncode: String
    let title: String
    let writer: String
    let episodes: Int
    let shortStory: Bool
    let finished: Bool
    var id: String { ncode }
}

enum SyosetuError: Error {
    case notFound
    case status(Int)
    case empty
}

/// Syosetu (小説家になろう): the public novel API for search and titles, the novel pages for the table of contents and
/// the text. Pages are asked one by one with a pause, as a reader would.
enum SyosetuClient {
    static let api = "https://api.syosetu.com/novelapi/api/"
    static let site = "https://ncode.syosetu.com/"

    /// "n9669bk" from a link or the code itself.
    static func ncode(from text: String) -> String? {
        guard let range = text.range(of: #"(?i)\bn\d{4}[a-z]{1,3}\b"#, options: .regularExpression) else { return nil }
        return text[range].lowercased()
    }

    private static func request(_ url: URL) -> URLRequest {
        var request = URLRequest(url: url, timeoutInterval: 30)
        request.setValue("Satori/1.72 (iOS offline reader)", forHTTPHeaderField: "User-Agent")
        return request
    }

    private static func load(_ url: URL) async throws -> Data {
        let (data, response) = try await URLSession.shared.data(for: request(url))
        let status = (response as? HTTPURLResponse)?.statusCode ?? 0
        guard status == 200 else { throw status == 404 ? SyosetuError.notFound : SyosetuError.status(status) }
        return data
    }

    private static func apiItems(_ query: [URLQueryItem]) async throws -> [[String: Any]] {
        guard var parts = URLComponents(string: api) else { return [] }
        parts.queryItems = [URLQueryItem(name: "out", value: "json"),
                            URLQueryItem(name: "of", value: "t-n-w-s-ga-nt-e")] + query
        guard let url = parts.url else { return [] }
        let data = try await load(url)
        let list = (try? JSONSerialization.jsonObject(with: data)) as? [[String: Any]] ?? []
        // the first element is {allcount}
        return Array(list.dropFirst())
    }

    private static func hit(_ item: [String: Any]) -> SyosetuHit? {
        guard let code = item["ncode"] as? String else { return nil }
        return SyosetuHit(ncode: code.lowercased(), title: item["title"] as? String ?? code,
                          writer: item["writer"] as? String ?? "",
                          episodes: (item["general_all_no"] as? NSNumber)?.intValue ?? 0,
                          shortStory: (item["noveltype"] as? NSNumber)?.intValue == 2,
                          finished: (item["end"] as? NSNumber)?.intValue == 0)
    }

    static func search(_ word: String) async throws -> [SyosetuHit] {
        try await apiItems([URLQueryItem(name: "word", value: word), URLQueryItem(name: "lim", value: "40"),
                            URLQueryItem(name: "order", value: "hyperpoint")]).compactMap(hit)
    }

    /// The title, the author and the synopsis.
    static func info(_ ncode: String) async throws -> (hit: SyosetuHit, story: String) {
        let items = try await apiItems([URLQueryItem(name: "ncode", value: ncode)])
        guard let item = items.first, let found = hit(item) else { throw SyosetuError.notFound }
        return (found, item["story"] as? String ?? "")
    }

    /// The table of contents: 100 episodes per page, chapters (volumes) as headings between them.
    static func toc(_ ncode: String) async throws -> [NovelEpisode] {
        let pattern = #"<div class="p-eplist__chapter-title">(.*?)</div>|<a href="/[a-z0-9]+/(\d+)/" class="p-eplist__subtitle">(.*?)</a>"#
        guard let regex = try? NSRegularExpression(pattern: pattern, options: [.dotMatchesLineSeparators]) else { return [] }
        var episodes: [NovelEpisode] = []
        var volume = ""
        var page = 1
        while page <= 200 {
            guard let url = URL(string: site + ncode + "/?p=" + String(page)) else { break }
            let html = String(decoding: try await load(url), as: UTF8.self)
            let ns = html as NSString
            var found = 0
            for match in regex.matches(in: html, range: NSRange(location: 0, length: ns.length)) {
                if match.range(at: 1).location != NSNotFound {
                    volume = plain(ns.substring(with: match.range(at: 1)))
                } else if let number = Int(ns.substring(with: match.range(at: 2))) {
                    found += 1
                    episodes.append(NovelEpisode(number: number, title: plain(ns.substring(with: match.range(at: 3))),
                                                 volume: volume))
                }
            }
            guard found > 0, html.contains("?p=" + String(page + 1) + "\"") else { break }
            page += 1
            try await Task.sleep(nanoseconds: 1_000_000_000)
        }
        guard !episodes.isEmpty else { throw SyosetuError.empty }
        return episodes
    }

    /// One episode (a short story is the page of the novel itself).
    static func episode(_ ncode: String, _ number: Int, shortStory: Bool) async throws -> NovelText {
        guard let url = URL(string: site + ncode + "/" + (shortStory ? "" : String(number) + "/")) else {
            throw SyosetuError.notFound
        }
        let html = String(decoding: try await load(url), as: UTF8.self)
        func first(_ pattern: String) -> String {
            guard let regex = try? NSRegularExpression(pattern: pattern, options: [.dotMatchesLineSeparators]),
                  let match = regex.firstMatch(in: html, range: NSRange(location: 0, length: (html as NSString).length)),
                  match.numberOfRanges > 1 else { return "" }
            return plain((html as NSString).substring(with: match.range(at: 1)))
        }
        var title = first(#"class="p-novel__subtitle-episode">(.*?)</"#)
        if title.isEmpty {
            title = first(#"<h1 class="p-novel__title[^"]*">(.*?)</h1>"#)
        }
        let chapter = first(#"class="p-novel__subtitle-chapter">(.*?)</"#)
        var preface: [String] = []
        var body: [String] = []
        var afterword: [String] = []
        if let regex = try? NSRegularExpression(pattern: #"<p id="L([pa]?)\d+"[^>]*>(.*?)</p>"#,
                                                options: [.dotMatchesLineSeparators]) {
            let ns = html as NSString
            for match in regex.matches(in: html, range: NSRange(location: 0, length: ns.length)) {
                let kind = ns.substring(with: match.range(at: 1))
                let text = plain(ns.substring(with: match.range(at: 2)), keepPictures: true)
                switch kind {
                case "p": preface.append(text)
                case "a": afterword.append(text)
                default: body.append(text)
                }
            }
        }
        guard !body.isEmpty else { throw SyosetuError.empty }
        return NovelText(title: title, chapter: chapter, preface: preface, body: body, afterword: afterword)
    }

    /// Text of an HTML fragment: ruby readings, tags and entities out.
    static func plain(_ html: String, keepPictures: Bool = false) -> String {
        var s = html.replacingOccurrences(of: "<rp>.*?</rp>", with: "", options: .regularExpression)
        s = s.replacingOccurrences(of: "<rt>.*?</rt>", with: "", options: .regularExpression)
        if keepPictures {
            s = s.replacingOccurrences(of: "<img[^>]*>", with: "［挿絵］", options: .regularExpression)
        }
        s = s.replacingOccurrences(of: "<[^>]+>", with: "", options: .regularExpression)
        let named = ["&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": "\"", "&#39;": "'", "&apos;": "'", "&nbsp;": " "]
        for (entity, value) in named {
            s = s.replacingOccurrences(of: entity, with: value)
        }
        if s.contains("&#"), let regex = try? NSRegularExpression(pattern: "&#(x?)([0-9a-fA-F]+);") {
            let ns = s as NSString
            var out = ""
            var last = 0
            for match in regex.matches(in: s, range: NSRange(location: 0, length: ns.length)) {
                out += ns.substring(with: NSRange(location: last, length: match.range.location - last))
                let hex = ns.substring(with: match.range(at: 1)) == "x"
                let value = UInt32(ns.substring(with: match.range(at: 2)), radix: hex ? 16 : 10) ?? 0x3F
                out += String(Character(Unicode.Scalar(value) ?? "?"))
                last = match.range.location + match.range.length
            }
            out += ns.substring(from: last)
            s = out
        }
        return s.trimmingCharacters(in: .newlines)
    }
}

/// Reading time, characters, sentences and words in the shared statistics (stats.v1), like the Safari extension.
enum ReadingStats {
    static func add(characters: Int = 0, sentences: Int = 0, words: Int = 0, seconds: Int = 0) {
        guard characters > 0 || seconds > 0 else { return }
        var root: [String: Any] = [:]
        if let json = try? Storage.stats.get(), let data = json.data(using: .utf8),
           let saved = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] {
            root = saved
        }
        var days = (root["days"] as? [String: Any]) ?? [:]
        let key = statKey(daysAgo: 0)
        let empty: [String: Any] = ["mined": [String](), "kanji": [String](), "read": 0, "time": 0]
        var day = (days[key] as? [String: Any]) ?? empty
        func number(_ name: String) -> Int {
            (day[name] as? NSNumber)?.intValue ?? 0
        }
        day["read"] = number("read") + characters
        day["time"] = number("time") + seconds
        day["sentences"] = number("sentences") + sentences
        day["words"] = number("words") + words
        days[key] = day
        root["days"] = days
        guard let out = try? JSONSerialization.data(withJSONObject: root),
              let text = String(data: out, encoding: .utf8) else { return }
        _ = try? Storage.stats.set(text)
    }
}

/// The saved novels and the downloads: one episode at a time, with a pause between pages.
@MainActor
final class NovelStore: ObservableObject {
    static let shared = NovelStore()

    struct Job {
        let ncode: String
        let done: Int
        let total: Int
        let failed: Int
    }

    @Published private(set) var novels: [NovelInfo] = []
    /// episode numbers on disk, per novel
    @Published private(set) var downloaded: [String: Set<Int>] = [:]
    @Published private(set) var job: Job? = nil
    @Published var message = ""

    private var pending: [(ncode: String, number: Int)] = []
    private var worker: Task<Void, Never>? = nil
    private var done = 0
    private var total = 0
    private var failed = 0

    private static var root: URL {
        let base = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("Novels")
        try? FileManager.default.createDirectory(at: base, withIntermediateDirectories: true)
        return base
    }

    private static func folder(_ ncode: String) -> URL {
        let url = root.appendingPathComponent(ncode, isDirectory: true)
        try? FileManager.default.createDirectory(at: url, withIntermediateDirectories: true)
        return url
    }

    private static func episodeFile(_ ncode: String, _ number: Int) -> URL {
        folder(ncode).appendingPathComponent("ep-" + String(number) + ".json")
    }

    init() {
        let fm = FileManager.default
        let folders = (try? fm.contentsOfDirectory(at: NovelStore.root, includingPropertiesForKeys: nil)) ?? []
        var loaded: [NovelInfo] = []
        for folder in folders {
            guard let data = try? Data(contentsOf: folder.appendingPathComponent("info.json")),
                  let info = try? JSONDecoder().decode(NovelInfo.self, from: data) else { continue }
            loaded.append(info)
            let files = (try? fm.contentsOfDirectory(atPath: folder.path)) ?? []
            downloaded[info.ncode] = Set(files.compactMap { name -> Int? in
                guard name.hasPrefix("ep-"), name.hasSuffix(".json") else { return nil }
                return Int(name.dropFirst(3).dropLast(5))
            })
        }
        novels = loaded.sorted { $0.addedAt > $1.addedAt }
    }

    func novel(_ ncode: String) -> NovelInfo? {
        novels.first { $0.ncode == ncode }
    }

    private func save(_ info: NovelInfo) {
        if let data = try? JSONEncoder().encode(info) {
            try? data.write(to: NovelStore.folder(info.ncode).appendingPathComponent("info.json"))
        }
    }

    func update(_ ncode: String, _ change: (inout NovelInfo) -> Void) {
        guard let index = novels.firstIndex(where: { $0.ncode == ncode }) else { return }
        change(&novels[index])
        save(novels[index])
    }

    /// A new novel: its title from the API, its table of contents from the novel page.
    func add(_ code: String) async throws {
        let ncode = code.lowercased()
        guard novel(ncode) == nil else { return }
        let (hit, story) = try await SyosetuClient.info(ncode)
        let episodes = hit.shortStory
            ? [NovelEpisode(number: 1, title: hit.title, volume: "")]
            : try await SyosetuClient.toc(ncode)
        let info = NovelInfo(ncode: ncode, title: hit.title, writer: hit.writer, story: story, shortStory: hit.shortStory,
                             finished: hit.finished, episodes: episodes, addedAt: Date())
        save(info)
        downloaded[ncode] = downloaded[ncode] ?? []
        withAnimation(.easeInOut(duration: 0.35)) {
            novels.insert(info, at: 0)
        }
    }

    /// New episodes of a running novel.
    func refresh(_ ncode: String) async throws {
        guard let current = novel(ncode) else { return }
        let (hit, story) = try await SyosetuClient.info(ncode)
        let episodes = current.shortStory ? current.episodes : try await SyosetuClient.toc(ncode)
        update(ncode) { info in
            info.title = hit.title
            info.writer = hit.writer
            info.story = story
            info.finished = hit.finished
            info.episodes = episodes
        }
    }

    func remove(_ ncode: String) {
        if job?.ncode == ncode {
            cancel()
        }
        try? FileManager.default.removeItem(at: NovelStore.folder(ncode))
        downloaded[ncode] = nil
        novels.removeAll { $0.ncode == ncode }
    }

    func isDownloaded(_ ncode: String, _ number: Int) -> Bool {
        downloaded[ncode]?.contains(number) ?? false
    }

    /// The episode from the disk, or from Syosetu right away (it is kept then).
    func text(_ ncode: String, _ number: Int) async throws -> NovelText {
        if let data = try? Data(contentsOf: NovelStore.episodeFile(ncode, number)),
           let saved = try? JSONDecoder().decode(NovelText.self, from: data) {
            return saved
        }
        let text = try await SyosetuClient.episode(ncode, number, shortStory: novel(ncode)?.shortStory ?? false)
        keep(text, ncode, number)
        return text
    }

    private func keep(_ text: NovelText, _ ncode: String, _ number: Int) {
        if let data = try? JSONEncoder().encode(text) {
            try? data.write(to: NovelStore.episodeFile(ncode, number))
            downloaded[ncode, default: []].insert(number)
        }
    }

    /// Episodes go to the queue; the queue runs one page at a time.
    func download(_ ncode: String, _ numbers: [Int]) {
        let have = downloaded[ncode] ?? []
        let queued = Set(pending.filter { $0.ncode == ncode }.map { $0.number })
        let wanted = numbers.filter { !have.contains($0) && !queued.contains($0) }
        guard !wanted.isEmpty else { return }
        pending += wanted.map { (ncode: ncode, number: $0) }
        total += wanted.count
        message = ""
        publish(ncode)
        start()
    }

    func cancel() {
        pending.removeAll()
        worker?.cancel()
    }

    private func publish(_ ncode: String) {
        job = Job(ncode: ncode, done: done, total: total, failed: failed)
    }

    private func start() {
        guard worker == nil, !pending.isEmpty else { return }
        // the screen stays on: a locked phone would stop the download
        UIApplication.shared.isIdleTimerDisabled = true
        worker = Task { @MainActor in
            var failuresInRow = 0
            while !pending.isEmpty, !Task.isCancelled {
                let next = pending.removeFirst()
                publish(next.ncode)
                do {
                    let text = try await SyosetuClient.episode(next.ncode, next.number,
                                                               shortStory: novel(next.ncode)?.shortStory ?? false)
                    keep(text, next.ncode, next.number)
                    done += 1
                    failuresInRow = 0
                } catch {
                    if Task.isCancelled { break }
                    failed += 1
                    failuresInRow += 1
                    if failuresInRow >= 3 {
                        message = "Загрузка остановлена: Syosetu не отвечает. Проверьте интернет."
                        pending.removeAll()
                        break
                    }
                }
                publish(next.ncode)
                // as a reader would: one page about every second
                try? await Task.sleep(nanoseconds: 1_100_000_000)
            }
            if failed > 0, message.isEmpty {
                message = "Не скачалось глав: " + String(failed)
            }
            worker = nil
            job = nil
            done = 0
            total = 0
            failed = 0
            UIApplication.shared.isIdleTimerDisabled = false
            if !pending.isEmpty {
                start()
            }
        }
    }
}

/// The reading tab.
struct ReaderTabView: View {
    var body: some View {
        if #available(iOS 16.0, *) {
            NavigationView {
                NovelLibraryView()
            }
            .navigationViewStyle(.stack)
        } else {
            Text("Чтение требует iOS 16 или новее.")
                .foregroundColor(.secondary)
                .padding()
        }
    }
}

/// The saved novels.
@available(iOS 16.0, *)
struct NovelLibraryView: View {
    @ObservedObject private var store = NovelStore.shared
    @State private var showAdd = false
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
    }

    private func row(_ novel: NovelInfo) -> some View {
        let count = novel.episodes.count
        let saved = store.downloaded[novel.ncode]?.count ?? 0
        let read = novel.read.count
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
            if count > 0, read > 0 {
                ProgressView(value: Double(min(read, count)), total: Double(count))
                    .tint(.accentColor)
            }
        }
        .padding(.vertical, 2)
    }
}

/// The download in progress, with a stop button.
@available(iOS 16.0, *)
struct NovelJobRow: View {
    let job: NovelStore.Job

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text("Скачиваю: " + String(job.done) + " из " + String(job.total))
                Spacer()
                Button("Остановить", role: .destructive) {
                    NovelStore.shared.cancel()
                }
                .buttonStyle(.borderless)
            }
            ProgressView(value: Double(job.done), total: Double(max(job.total, 1)))
                .tint(.accentColor)
            let left = max(0, job.total - job.done)
            Text("Осталось около " + String(max(1, Int((Double(left) * 1.6 / 60).rounded(.up)))) + " мин. Экран не гаснет, пока идёт загрузка.")
                .font(.caption)
                .foregroundColor(.secondary)
        }
    }
}

/// Search on Syosetu, or a link / code.
@available(iOS 16.0, *)
struct NovelAddSheet: View {
    @Environment(\.dismiss) private var dismiss
    @ObservedObject private var store = NovelStore.shared
    @State private var query = ""
    @State private var results: [SyosetuHit] = []
    @State private var searching = false
    @State private var message = ""
    @State private var adding: String? = nil

    var body: some View {
        NavigationView {
            List {
                Section {
                    TextField("Название, автор или ссылка", text: $query)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                    PasteButton(payloadType: String.self) { strings in
                        if let first = strings.first {
                            query = first
                        }
                    }
                } footer: {
                    Text("Ищет на syosetu.com (小説家になろう). Можно вставить ссылку вида ncode.syosetu.com/n1234ab/ или код n1234ab.")
                }
                if let code = SyosetuClient.ncode(from: query) {
                    Section {
                        addButton(code, title: "Добавить " + code)
                    }
                }
                Section {
                    if searching {
                        HStack(spacing: 10) {
                            ProgressView()
                            Text("Ищу…")
                        }
                    } else if !message.isEmpty {
                        Text(message).foregroundColor(.secondary)
                    }
                    ForEach(results) { hit in
                        Button {
                            add(hit.ncode)
                        } label: {
                            HStack {
                                VStack(alignment: .leading, spacing: 4) {
                                    Text(hit.title)
                                        .foregroundColor(.primary)
                                        .lineLimit(2)
                                    Text(details(hit))
                                        .font(.caption)
                                        .foregroundColor(.secondary)
                                        .lineLimit(1)
                                }
                                Spacer()
                                status(hit.ncode)
                            }
                        }
                        .disabled(adding != nil)
                    }
                }
            }
            .navigationTitle("Syosetu")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Готово") { dismiss() }
                }
            }
            .task(id: query) {
                await search()
            }
        }
    }

    private func details(_ hit: SyosetuHit) -> String {
        var parts = [hit.writer]
        parts.append(hit.shortStory ? "рассказ" : String(hit.episodes) + " гл.")
        parts.append(hit.finished ? "завершена" : "выходит")
        return parts.filter { !$0.isEmpty }.joined(separator: " · ")
    }

    @ViewBuilder
    private func status(_ ncode: String) -> some View {
        if adding == ncode {
            ProgressView()
        } else if store.novel(ncode) != nil {
            Image(systemName: "checkmark.circle.fill").foregroundColor(.green)
        } else {
            Image(systemName: "plus.circle").foregroundColor(.accentColor)
        }
    }

    private func addButton(_ code: String, title: String) -> some View {
        Button {
            add(code)
        } label: {
            HStack {
                Text(title)
                Spacer()
                status(code)
            }
        }
        .disabled(adding != nil)
    }

    private func add(_ code: String) {
        guard adding == nil, store.novel(code) == nil else { return }
        adding = code
        message = "Загружаю оглавление…"
        Task { @MainActor in
            defer { adding = nil }
            do {
                try await store.add(code)
                message = ""
                dismiss()
            } catch SyosetuError.notFound {
                message = "Новелла не найдена (новеллы 18+ не поддерживаются)."
            } catch {
                message = "Не удалось загрузить новеллу. Проверьте интернет."
            }
        }
    }

    private func search() async {
        let text = query.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty, SyosetuClient.ncode(from: text) == nil else {
            results = []
            return
        }
        try? await Task.sleep(nanoseconds: 500_000_000)
        guard !Task.isCancelled else { return }
        searching = true
        defer { searching = false }
        do {
            let found = try await SyosetuClient.search(text)
            guard !Task.isCancelled else { return }
            results = found
            message = found.isEmpty ? "Ничего не найдено" : ""
        } catch {
            if !Task.isCancelled {
                message = "Нет связи с Syosetu"
            }
        }
    }
}

/// A novel: the synopsis, downloads and the table of contents by volumes.
@available(iOS 16.0, *)
struct NovelDetailView: View {
    let ncode: String
    @ObservedObject private var store = NovelStore.shared
    @State private var showStory = false
    @State private var refreshing = false
    @State private var note = ""

    private struct Volume: Identifiable {
        let id: Int
        let title: String
        let episodes: [NovelEpisode]
    }

    /// Episodes in order, grouped by their volume headings.
    private func volumes(_ novel: NovelInfo) -> [Volume] {
        var result: [Volume] = []
        for episode in novel.episodes {
            if let last = result.last, last.title == episode.volume {
                result[result.count - 1] = Volume(id: last.id, title: last.title, episodes: last.episodes + [episode])
            } else {
                result.append(Volume(id: result.count, title: episode.volume, episodes: [episode]))
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

    private func content(_ novel: NovelInfo) -> some View {
        let saved = store.downloaded[ncode] ?? []
        let missing = novel.episodes.map { $0.number }.filter { !saved.contains($0) }
        let next = novel.lastRead ?? novel.episodes.first?.number
        return List {
            Section {
                VStack(alignment: .leading, spacing: 6) {
                    Text(novel.title).font(.headline)
                    Text(novel.writer + " · " + (novel.finished ? "завершена" : "выходит") + " · "
                         + String(novel.episodes.count) + " гл.")
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
                        Label((novel.lastRead == nil ? "Начать: " : "Продолжить: ") + episode.title, systemImage: "book")
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
            ForEach(volumes(novel)) { volume in
                Section {
                    ForEach(volume.episodes) { episode in
                        NavigationLink(destination: NovelReaderView(ncode: ncode, number: episode.number)) {
                            episodeRow(episode, saved: saved.contains(episode.number), read: novel.read.contains(episode.number))
                        }
                        .swipeActions(edge: .trailing, allowsFullSwipe: true) {
                            if !saved.contains(episode.number) {
                                Button {
                                    store.download(ncode, [episode.number])
                                } label: {
                                    Label("Скачать", systemImage: "arrow.down.circle")
                                }
                                .tint(.accentColor)
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
    }

    private func volumeHeader(_ volume: Volume, saved: Set<Int>) -> some View {
        let missing = volume.episodes.map { $0.number }.filter { !saved.contains($0) }
        return HStack {
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
        .textCase(nil)
    }

    private func episodeRow(_ episode: NovelEpisode, saved: Bool, read: Bool) -> some View {
        HStack(spacing: 10) {
            Text(episode.title)
                .foregroundColor(read ? .secondary : .primary)
                .lineLimit(2)
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

/// A word tapped in the text: its sentence for the dictionary and where the word starts in it.
struct ReaderLookup: Identifiable {
    let id = UUID()
    let text: String
    let charAt: Int

    static func make(_ tokens: [LookupToken], at index: Int) -> ReaderLookup {
        let ends: Set<Character> = ["。", "！", "？", "!", "?"]
        let closers: Set<String> = ["」", "』", "）", ")", "】"]
        func ending(_ i: Int) -> Bool {
            tokens[i].text.contains { ends.contains($0) }
        }
        var start = index
        while start > 0, !ending(start - 1) {
            start -= 1
        }
        var end = index
        while end < tokens.count - 1, !ending(end) {
            end += 1
        }
        while end + 1 < tokens.count, closers.contains(tokens[end + 1].text) {
            end += 1
        }
        var sentence = ""
        var offset = 0
        for i in start ... end {
            if i == index {
                offset = sentence.unicodeScalars.count
            }
            sentence += tokens[i].text
        }
        // a closing bracket of the previous sentence and the indent are not part of this one
        let lead = sentence.prefix { $0 == "　" || $0 == " " || closers.contains(String($0)) }
        let leadCount = String(lead).unicodeScalars.count
        return ReaderLookup(text: String(sentence.dropFirst(lead.count)), charAt: max(0, offset - leadCount))
    }
}

/// One paragraph: its words can be tapped and are highlighted like the subtitles.
@available(iOS 16.0, *)
struct ReaderParagraph: View {
    let text: String
    let fontSize: Double
    var secondary = false
    let onTap: (ReaderLookup) -> Void
    @State private var tokens: [LookupToken] = []
    @State private var colors: [Int: Color] = [:]
    @State private var ready = false

    private var baseColor: Color {
        secondary ? .secondary : .primary
    }

    var body: some View {
        Group {
            if text.trimmingCharacters(in: .whitespaces).isEmpty {
                Color.clear.frame(height: fontSize * 0.6)
            } else if tokens.isEmpty {
                Text(text)
                    .font(.system(size: fontSize))
                    .foregroundColor(baseColor)
                    .lineSpacing(fontSize * 0.35)
                    .onTapGesture {
                        if ready {
                            onTap(ReaderLookup(text: text.trimmingCharacters(in: .whitespaces), charAt: 0))
                        }
                    }
            } else {
                FlowLayout(spacing: 0) {
                    ForEach(tokens) { token in
                        Text(token.text)
                            .font(.system(size: fontSize))
                            .foregroundColor(colors[token.id] ?? baseColor)
                            .padding(.vertical, fontSize * 0.17)
                            .contentShape(Rectangle())
                            .onTapGesture {
                                onTap(ReaderLookup.make(tokens, at: token.id))
                            }
                    }
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .onAppear(perform: prepare)
    }

    private func prepare() {
        guard !ready, !text.isEmpty else { return }
        ready = true
        var result = SubtitleTokenCache.shared.tokens(text)
        let covered = result.map { $0.text }.joined()
        if covered != text {
            if text.hasPrefix(covered), !covered.isEmpty {
                result.append(LookupToken(id: result.count, text: String(text.dropFirst(covered.count)), start: covered.count))
            } else if let leading = text.first, leading == "　", text.dropFirst().hasPrefix(covered), !covered.isEmpty {
                // the indent the tokenizer skips stays in front
                var shifted = [LookupToken(id: 0, text: "　", start: 0)]
                for token in result {
                    var moved = LookupToken(id: token.id + 1, text: token.text, start: token.start + 1, base: token.base,
                                            reading: token.reading, pos: token.pos, pos2: token.pos2)
                    moved.parts = token.parts
                    shifted.append(moved)
                }
                let rest = String(text.dropFirst(1 + covered.count))
                if !rest.isEmpty {
                    shifted.append(LookupToken(id: shifted.count, text: rest, start: covered.count + 1))
                }
                result = shifted
            } else {
                result = []
            }
        }
        tokens = result
        colors = result.isEmpty ? [:] : HighlightData.colors(for: result)
    }
}

/// The reader: one episode, word lookup and mining, the place kept, the next episode.
@available(iOS 16.0, *)
struct NovelReaderView: View {
    let ncode: String
    @State private var number: Int
    @ObservedObject private var store = NovelStore.shared
    @AppStorage("ykReaderFontSize") private var fontSize: Double = 19
    @State private var text: NovelText? = nil
    @State private var failed = false
    @State private var lookup: ReaderLookup? = nil
    @State private var furthest = 0
    @State private var lastActivity = CACurrentMediaTime()
    @State private var lastTick = CACurrentMediaTime()
    @State private var pendingSeconds: Double = 0
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
                    Color.clear.frame(height: 1).id("top")
                    if let text {
                        if !text.chapter.isEmpty {
                            Text(text.chapter)
                                .font(.footnote)
                                .foregroundColor(.secondary)
                        }
                        Text(text.title)
                            .font(.system(size: fontSize * 1.2, weight: .bold))
                            .padding(.bottom, fontSize * 0.6)
                        ForEach(Array(text.preface.enumerated()), id: \.offset) { _, paragraph in
                            ReaderParagraph(text: paragraph, fontSize: fontSize * 0.88, secondary: true, onTap: open)
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
                        ForEach(Array(text.afterword.enumerated()), id: \.offset) { _, paragraph in
                            ReaderParagraph(text: paragraph, fontSize: fontSize * 0.88, secondary: true, onTap: open)
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
                .padding(.horizontal, 18)
                .padding(.vertical, 12)
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
        .onDisappear {
            savePosition()
            flushTime(force: true)
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

    private func open(_ item: ReaderLookup) {
        lastActivity = CACurrentMediaTime()
        lookup = item
    }

    private func go(_ next: Int, _ proxy: ScrollViewProxy) {
        savePosition()
        text = nil
        furthest = 0
        number = next
        proxy.scrollTo("top", anchor: .top)
    }

    private func load(_ proxy: ScrollViewProxy) async {
        failed = false
        do {
            let loaded = try await store.text(ncode, number)
            text = loaded
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

    /// The deepest paragraph seen; the last one marks the episode as read (and counts it in the statistics once).
    private func reached(_ index: Int, of text: NovelText) {
        lastActivity = CACurrentMediaTime()
        furthest = max(furthest, index)
        guard index == text.body.count - 1, novel?.read.contains(number) == false else { return }
        store.update(ncode) { $0.read.insert(number) }
        let paragraphs = text.body
        Task.detached(priority: .utility) {
            var characters = 0
            var sentences = 0
            var words = 0
            for paragraph in paragraphs where !paragraph.isEmpty {
                characters += paragraph.filter { !$0.isWhitespace }.count
                sentences += max(1, paragraph.filter { "。！？!?".contains($0) }.count)
                words += SubtitleTokenCache.shared.tokens(paragraph).filter { token in
                    token.text.unicodeScalars.contains { CharacterSet.letters.contains($0) } && !token.pos.contains("記号")
                }.count
            }
            ReadingStats.add(characters: characters, sentences: sentences, words: words)
        }
    }

    private func savePosition() {
        // the paragraphs above the deepest one seen are about a screen
        let top = max(0, furthest - 8)
        let current = number
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
        flushTime(force: false)
    }

    private func flushTime(force: Bool) {
        guard pendingSeconds >= (force ? 1 : 60) else { return }
        ReadingStats.add(seconds: Int(pendingSeconds.rounded()))
        pendingSeconds = 0
    }
}

/// A label with its icon after the title ("Следующая ›").
@available(iOS 16.0, *)
struct TrailingIconLabelStyle: LabelStyle {
    func makeBody(configuration: Configuration) -> some View {
        HStack(spacing: 6) {
            configuration.title
            configuration.icon
        }
    }
}
