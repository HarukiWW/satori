# v1.77: the catalog counts two titles at a time and keeps counting after the catalog is closed (also while a video
# plays). Jiten's limit (about ten word lists a minute) is kept by one shared pace: a download every 6.5 s at most,
# a minute's wait after "slow down". A title that came on screen stays in the queue when it leaves it; the rows on
# screen go first.
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

s = between(s, "/// Our coverage of the titles, counted in the background one at a time: the rows on screen first, then the rest of a\n",
            "/// The badge of our coverage: the share in the colour of the difficulty.", r'''/// Our coverage of the titles, counted in the background two at a time: the rows on screen first, then every title
/// that was on screen or in a list sorted by coverage (also after the catalog is closed). Jiten gives about ten word
/// lists a minute: one shared pace for the downloads, a minute's wait when it asks to slow down, none at all while a
/// title page downloads its own list.
@available(iOS 16.0, *)
@MainActor
final class CatalogCoverageQueue: ObservableObject {
    static let shared = CatalogCoverageQueue()
    private static let parallel = 2
    /// seconds between two downloads (about nine a minute)
    private static let pace: CFTimeInterval = 6.5

    @Published private(set) var results: [Int: CatalogCoverage] = [:]
    @Published private(set) var working: Set<Int> = []
    @Published private(set) var waiting: [Int] = []
    /// Jiten asked to slow down
    @Published private(set) var pausedByJiten = false
    private var failed = Set<Int>()
    private var workers = 0
    /// the earliest time of the next download
    private var nextDownload: CFTimeInterval = 0
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
        let fresh = (time: now, knownWords: KnownWordsIndex.fingerprint(HighlightData.analysisWords()), level: level,
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
                waiting.append(id)
            }
        }
        start()
    }

    /// A title page downloads its own list: the background waits.
    func hold(_ on: Bool) {
        held = max(0, held + (on ? 1 : -1))
    }

    private func start() {
        while workers < CatalogCoverageQueue.parallel, !waiting.isEmpty {
            workers += 1
            Task { @MainActor in
                await run()
                workers -= 1
            }
        }
    }

    /// Waits for the turn of a download: the turns of both workers are a pace apart.
    private func waitForTurn() async {
        let now = CACurrentMediaTime()
        let turn = max(now, nextDownload)
        nextDownload = turn + CatalogCoverageQueue.pace
        if turn > now {
            try? await Task.sleep(nanoseconds: UInt64((turn - now) * 1_000_000_000))
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
            if !FileManager.default.fileExists(atPath: JitenAPI.wordsFile(id).path) {
                await waitForTurn()
            }
            do {
                let words = try await JitenAPI.words(id)
                pausedByJiten = false
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
                // Jiten asks to slow down: this title goes first, the next download in a minute
                waiting.insert(id, at: 0)
                pausedByJiten = true
                nextDownload = max(nextDownload, CACurrentMediaTime() + 60)
            } catch {
                failed.insert(id)
            }
            working.remove(id)
        }
    }
}

''', "catalog queue")
s = once(s, '''                    .onAppear {
                        queue.request(deck.deckId)
                    }
                    .onDisappear {
                        queue.forget(deck.deckId)
                    }
''', '''                    .onAppear {
                        queue.request(deck.deckId)
                    }
''', "rows stay queued")
s = once(s, "Jiten отдаёт около десяти словарей в минуту, поэтому тайтлы считаются по одному. Листайте ниже, чтобы добавить следующие.",
         "Jiten отдаёт около десяти словарей в минуту: тайтлы считаются по два, в фоне, даже когда каталог закрыт. Листайте ниже, чтобы добавить следующие.",
         "count row note")
s = once(s, "Покрытие считается само, по одному тайтлу: сначала \"\n"
            "                     + \"тайтлы на экране, при сортировке «Моё покрытие» — весь загруженный список.",
         "Покрытие считается само, по два тайтла, и в фоне: \"\n"
         "                     + \"сначала тайтлы на экране, потом все пролистанные, при сортировке «Моё покрытие» — весь загруженный список.",
         "catalog footer")
hv.write_text(s, encoding="utf-8")
print("v1.77 catalog applied")
