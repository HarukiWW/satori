# v1.79: the catalog.
# - A title page shows the genres, the description (in Russian from Shikimori for anime, Jiten's otherwise), the
#   ratings (Shikimori, AniList or TMDB) and links to MyAnimeList, AniList, Shikimori, TMDB, IMDb.
# - No "Посчитано" row and no explanation under the list.
# - Switching between anime, dramas and films is instant: the first pages stay for 15 minutes, the other two types
#   load in the background after the first, and only typing waits before asking Jiten.
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

# ---------- what Jiten tells about a title ----------
s = once(s, '''    let speechSpeed: Double?

    var title: String {
''', '''    let speechSpeed: Double?
    /// English, from Jiten
    let description: String?
    let genres: [Int]?
    /// AniList for anime, TMDB for dramas and films, out of 100
    let externalRating: Double?
    let links: [JitenLink]?

    var title: String {
''', "deck fields")
s = once(s, "/// One title (or one episode) of the Jiten library.\n", r'''/// A page of a title elsewhere: 3 TMDB, 4 AniList, 5 MyAnimeList, 7 IMDb.
struct JitenLink: Decodable {
    let linkType: Int
    let url: String
}

/// Shikimori: the Russian description and the score of an anime, by its MyAnimeList id (kept 30 days).
@available(iOS 16.0, *)
enum ShikimoriAPI {
    static let site = "https://shikimori.io"

    struct Anime: Codable {
        let score: String?
        let description: String?
    }

    static func malId(_ links: [JitenLink]?) -> Int? {
        guard let link = links?.first(where: { $0.linkType == 5 }), let url = URL(string: link.url) else { return nil }
        return Int(url.lastPathComponent)
    }

    static func anime(_ malId: Int) async -> Anime? {
        let file = CatalogStore.folder.appendingPathComponent("shikimori-" + String(malId) + ".json")
        if let attributes = try? FileManager.default.attributesOfItem(atPath: file.path),
           let date = attributes[.modificationDate] as? Date, Date().timeIntervalSince(date) < 30 * 86400,
           let data = try? Data(contentsOf: file), let saved = try? JSONDecoder().decode(Anime.self, from: data) {
            return saved
        }
        guard let url = URL(string: site + "/api/animes/" + String(malId)) else { return nil }
        var request = URLRequest(url: url, timeoutInterval: 20)
        request.setValue("Satori", forHTTPHeaderField: "User-Agent")
        guard let loaded = try? await URLSession.shared.data(for: request),
              (loaded.1 as? HTTPURLResponse)?.statusCode == 200,
              let anime = try? JSONDecoder().decode(Anime.self, from: loaded.0) else { return nil }
        try? loaded.0.write(to: file)
        return anime
    }

    /// [character=123]Name[/character], [i]…[/i]: the text only.
    static func plain(_ text: String) -> String {
        text.replacingOccurrences(of: "\\[[^\\]]*\\]", with: "", options: .regularExpression)
            .trimmingCharacters(in: .whitespacesAndNewlines)
    }
}

/// The first pages of the catalog already loaded (for 15 minutes): anime, dramas and films switch at once.
@available(iOS 16.0, *)
@MainActor
enum CatalogPages {
    private static var pages: [String: (decks: [JitenDeck], total: Int, time: Date)] = [:]

    static func get(_ key: String) -> (decks: [JitenDeck], total: Int)? {
        guard let page = pages[key], Date().timeIntervalSince(page.time) < 900 else { return nil }
        return (page.decks, page.total)
    }

    static func put(_ key: String, _ decks: [JitenDeck], _ total: Int) {
        pages[key] = (decks: decks, total: total, time: Date())
    }
}

/// One title (or one episode) of the Jiten library.
''', "shikimori and pages")

# ---------- the title page ----------
s = once(s, '''struct CatalogDetailView: View {
    let deck: JitenDeck
    @State private var detail: JitenDeck? = nil
''', '''struct CatalogDetailView: View {
    let deck: JitenDeck
    @State private var detail: JitenDeck? = nil
    @State private var shikimori: ShikimoriAPI.Anime? = nil
    @State private var fullDescription = false
''', "detail state")
s = once(s, '''                    VStack(alignment: .leading, spacing: 6) {
                        Text(shown.title).font(.headline)
                        if !shown.subtitle.isEmpty {
                            Text(shown.subtitle).font(.subheadline).foregroundColor(.secondary)
                        }
                    }
                }
                .padding(.vertical, 4)
            }
''', '''                    VStack(alignment: .leading, spacing: 6) {
                        Text(shown.title).font(.headline)
                        if !shown.subtitle.isEmpty {
                            Text(shown.subtitle).font(.subheadline).foregroundColor(.secondary)
                        }
                    }
                }
                .padding(.vertical, 4)
            }
            about
''', "about section")
s = once(s, '''    /// The grade by the known words and Jiten's speech speed.
    private func grade(_ coverage: CatalogCoverage) -> Int {
''', '''    private struct Rating {
        let name: String
        let value: String
        let url: URL?
    }

    private var genreNames: [String] {
        (shown.genres ?? []).compactMap { id in
            CatalogFilter.genreNames.first { $0.id == id }?.name
        }
    }

    /// Russian from Shikimori for anime, Jiten's English otherwise.
    private var descriptionText: String {
        if let russian = shikimori?.description, !russian.isEmpty {
            return ShikimoriAPI.plain(russian)
        }
        return (shown.description ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
    }

    private var ratings: [Rating] {
        let links = shown.links ?? []
        func link(_ type: Int) -> URL? {
            links.first { $0.linkType == type }.flatMap { URL(string: $0.url) }
        }
        var result: [Rating] = []
        if let mal = ShikimoriAPI.malId(links), let score = shikimori?.score, let value = Double(score), value > 0 {
            result.append(Rating(name: "Shikimori", value: String(format: "%.2f", value),
                                 url: URL(string: ShikimoriAPI.site + "/animes/" + String(mal))))
        }
        if let rating = shown.externalRating, rating > 0 {
            if let url = link(4) {
                result.append(Rating(name: "AniList", value: String(Int(rating.rounded())) + "%", url: url))
            } else if let url = link(3) {
                result.append(Rating(name: "TMDB", value: String(format: "%.1f", rating / 10), url: url))
            }
        }
        if let url = link(5) {
            result.append(Rating(name: "MyAnimeList", value: "↗", url: url))
        }
        if let url = link(7) {
            result.append(Rating(name: "IMDb", value: "↗", url: url))
        }
        return result
    }

    private func ratingRow(_ rating: Rating) -> some View {
        HStack {
            Text(rating.name).foregroundColor(.primary)
            Spacer()
            Text(rating.value).foregroundColor(.secondary)
        }
    }

    /// The genres, the description and the ratings.
    @ViewBuilder
    private var about: some View {
        let names = genreNames
        let text = descriptionText
        let marks = ratings
        if !names.isEmpty || !text.isEmpty || !marks.isEmpty {
            Section {
                if !names.isEmpty {
                    FlowLayout(spacing: 6) {
                        ForEach(names, id: \\.self) { name in
                            Text(name)
                                .font(.caption)
                                .padding(.horizontal, 8)
                                .padding(.vertical, 3)
                                .background(Color(.tertiarySystemFill))
                                .cornerRadius(6)
                        }
                    }
                    .padding(.vertical, 2)
                }
                if !text.isEmpty {
                    Text(text)
                        .font(.subheadline)
                        .lineLimit(fullDescription ? nil : 4)
                        .onTapGesture {
                            withAnimation {
                                fullDescription.toggle()
                            }
                        }
                }
                ForEach(marks, id: \\.name) { rating in
                    if let url = rating.url {
                        Link(destination: url) {
                            ratingRow(rating)
                        }
                    } else {
                        ratingRow(rating)
                    }
                }
            } header: {
                Text("О тайтле")
            } footer: {
                if shikimori?.description != nil {
                    Text("Описание: Shikimori.")
                }
            }
        }
    }

    /// The grade by the known words and Jiten's speech speed.
    private func grade(_ coverage: CatalogCoverage) -> Int {
''', "about view")
s = once(s, '''        .navigationTitle(shown.title)
        .navigationBarTitleDisplayMode(.inline)
        .task {
            await load()
        }
''', '''        .navigationTitle(shown.title)
        .navigationBarTitleDisplayMode(.inline)
        .task {
            await load()
        }
        .task {
            if shikimori == nil, let mal = ShikimoriAPI.malId(deck.links) {
                shikimori = await ShikimoriAPI.anime(mal)
            }
        }
''', "shikimori task")

# ---------- the list: no "Посчитано", no explanation ----------
s = once(s, '''                if filter.sort == "coverage" && total > 0 {
                    countAllRow
                }
''', "", "count row out")
s = between(s, "    private var countedCount: Int {\n", "    private func row(_ deck: JitenDeck) -> some View {", "",
            "count row code")
s = once(s, '''            } footer: {
                Text("Поиск по английскому, японскому и ромадзи названию. Покрытие считается само, по два тайтла, и в фоне: "
                     + "сначала тайтлы на экране, потом все пролистанные, при сортировке «Моё покрытие» — весь загруженный список. Данные: Jiten (jiten.moe), CC BY-SA 4.0.")
            }
''', '''            }
''', "list footer out")

# ---------- quick switching ----------
s = once(s, '''    /// the search the list shows: coming back from a title page does not search again
    @State private var searchedKey: String? = nil
''', '''    /// the search the list shows: coming back from a title page does not search again
    @State private var searchedKey: String? = nil
    /// the text of that search: only typing waits before asking Jiten
    @State private var searchedText: String? = nil
''', "searched text state")
s = between(s, "    private func search() async {\n        let text = query.trimmingCharacters(in: .whitespacesAndNewlines)\n        // back from a title page",
            "    private func loadMore() async {", '''    private func search() async {
        let text = query.trimmingCharacters(in: .whitespacesAndNewlines)
        // back from a title page: the list stays as it was, with its pages and progress
        let key = text + "|" + String(type) + "|" + String(describing: filter)
        if key == searchedKey, !results.isEmpty {
            return
        }
        filter.save()
        if let page = CatalogPages.get(key) {
            show(page.decks, page.total, key: key, text: text)
            return
        }
        if text != searchedText {
            // a new letter cancels this task: Jiten is asked once the typing stops
            try? await Task.sleep(nanoseconds: 450_000_000)
            guard !Task.isCancelled else { return }
        } else {
            // another type or filter: the old list goes at once
            results = []
        }
        loading = true
        defer { loading = false }
        do {
            let page = try await JitenAPI.browse(text, type: type, filter: filter, offset: 0)
            guard !Task.isCancelled else { return }
            CatalogPages.put(key, page.decks, page.total)
            show(page.decks, page.total, key: key, text: text)
            prefetch(text)
        } catch {
            if !Task.isCancelled {
                message = "Нет связи с Jiten"
            }
        }
    }

    private func show(_ decks: [JitenDeck], _ count: Int, key: String, text: String) {
        results = decks
        total = count
        searchedKey = key
        searchedText = text
        message = decks.isEmpty ? "Ничего не найдено" : ""
        if filter.sort == "coverage" {
            queue.requestAll(decks.map { $0.deckId })
        }
    }

    /// The other two types of the same search load in the background.
    private func prefetch(_ text: String) {
        let filter = self.filter
        let current = type
        Task { @MainActor in
            for other in [1, 2, 3] where other != current {
                let key = text + "|" + String(other) + "|" + String(describing: filter)
                guard CatalogPages.get(key) == nil else { continue }
                if let page = try? await JitenAPI.browse(text, type: other, filter: filter, offset: 0) {
                    CatalogPages.put(key, page.decks, page.total)
                }
            }
        }
    }

''', "search")
s = once(s, '''            results += fresh
            if filter.sort == "coverage" {
                queue.requestAll(fresh.map { $0.deckId })
            }
            if fresh.isEmpty {
                total = results.count
            }
''', '''            results += fresh
            if filter.sort == "coverage" {
                queue.requestAll(fresh.map { $0.deckId })
            }
            if fresh.isEmpty {
                total = results.count
            }
            if let key = searchedKey {
                CatalogPages.put(key, results, total)
            }
''', "load more keeps the pages")
hv.write_text(s, encoding="utf-8")
print("v1.79 catalog applied")
