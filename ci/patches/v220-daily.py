# v2.20: the analyses once a day in the background; the package finds the note type.
# - The coverage and difficulty of the videos, the novels and the titles of the catalog were counted again after
#   nearly every launch: they depended on the exact known words, which change with every mined word and every read
#   backup. Now a result stays for a day with any known words (the level, the vocabulary, the file and the rules
#   still count). Once a day, while the app is open, Satori counts again in the background every video with
#   subtitles and every downloaded novel, without opening «Видео» or «Чтение» (the catalog counts what is on screen,
#   as before: Jiten gives about ten word lists a minute).
# - The package of the queue: the note types of a backup were all lost when the query of its decks failed (the index
#   of their names needs the collation "unicase", which sql.js does not have); the decks are read on their own now.
#   A note type the read backup does not have makes the newest backup read again before the package; when it is still
#   missing, the message says the date of the backup and how many note types it had.
import pathlib


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")

# --- videos: a result stays for a day
s = once(s, '''    /// TextAnalysis.algorithm (nil before 1.74)
    var algorithm: Int? = nil
}

struct EpisodeAnalysis {''', '''    /// TextAnalysis.algorithm (nil before 1.74)
    var algorithm: Int? = nil
    /// when it was counted (nil before 2.20): it stays for a day with other known words
    var made: Date? = nil
}

struct EpisodeAnalysis {''', "coverage made")
s = once(s, '''               saved.level == level, saved.vocabulary == vocabulary, saved.knownWords == knownWords, saved.size == size,
               saved.algorithm == TextAnalysis.textVersion {''', '''               saved.level == level, saved.vocabulary == vocabulary, saved.size == size,
               saved.knownWords == knownWords || AnalysisAge.fresh(saved.made),
               saved.algorithm == TextAnalysis.textVersion {''', "coverage fresh")
s = once(s, '''                                          knownShare: result.knownShare, clearShare: result.clearShare,
                                          algorithm: TextAnalysis.textVersion)''', '''                                          knownShare: result.knownShare, clearShare: result.clearShare,
                                          algorithm: TextAnalysis.textVersion, made: Date())''', "coverage save")

# --- novels
s = once(s, '''    var episodes: [Int: NovelEpisodeAnalysis]
    /// TextAnalysis.algorithm (nil before 1.74)
    var algorithm: Int? = nil
}''', '''    var episodes: [Int: NovelEpisodeAnalysis]
    /// TextAnalysis.algorithm (nil before 1.74)
    var algorithm: Int? = nil
    /// when it was started (nil before 2.20): it stays for a day with other known words
    var made: Date? = nil
}''', "novel made")
s = once(s, '''        if let loaded = NovelAnalyzer.load(ncode), loaded.knownWords == index.fingerprint, loaded.level == level,
           loaded.vocabulary == vocabulary, loaded.algorithm == TextAnalysis.textVersion {
            current = loaded
        } else {
            current = NovelAnalysisFile(knownWords: index.fingerprint, level: level, vocabulary: vocabulary, episodes: [:],
                                        algorithm: TextAnalysis.textVersion)
        }''', '''        if let loaded = NovelAnalyzer.load(ncode), loaded.knownWords == index.fingerprint || AnalysisAge.fresh(loaded.made),
           loaded.level == level, loaded.vocabulary == vocabulary, loaded.algorithm == TextAnalysis.textVersion {
            current = loaded
        } else {
            current = NovelAnalysisFile(knownWords: index.fingerprint, level: level, vocabulary: vocabulary, episodes: [:],
                                        algorithm: TextAnalysis.textVersion, made: Date())
        }''', "novel fresh")

# --- the catalog
s = once(s, '''    /// false: counted in the background, the numbers only (thousands of titles would take hundreds of MB)
    var full: Bool? = nil
''', '''    /// false: counted in the background, the numbers only (thousands of titles would take hundreds of MB)
    var full: Bool? = nil
    /// when it was counted (nil before 2.20): it stays for a day with other known words
    var made: Date? = nil
''', "catalog made")
s = once(s, '''                        uniqueKnown: uniqueKnown, words: words, unknown: [], algorithm: algorithm, full: false)''',
         '''                        uniqueKnown: uniqueKnown, words: words, unknown: [], algorithm: algorithm, full: false, made: made)''',
         "catalog summary")
s = once(s, '''                               uniqueKnown: uniqueKnown, words: distinct, unknown: unknown,
                               algorithm: TextAnalysis.algorithm)''', '''                               uniqueKnown: uniqueKnown, words: distinct, unknown: unknown,
                               algorithm: TextAnalysis.algorithm, made: Date())''', "catalog counted")
s = once(s, '''              saved.knownWords == knownWords, saved.level == level, saved.vocabulary == vocabulary,
              saved.algorithm == TextAnalysis.algorithm else { return nil }''', '''              saved.knownWords == knownWords || AnalysisAge.fresh(saved.made), saved.level == level,
              saved.vocabulary == vocabulary, saved.algorithm == TextAnalysis.algorithm else { return nil }''',
         "catalog fresh")
s = once(s, '''        if let old = stamp, old.knownWords != fresh.knownWords || old.level != fresh.level || old.vocabulary != fresh.vocabulary {''',
         '''        // other known words keep the results of the day (AnalysisAge); another level or vocabulary does not
        if let old = stamp, old.level != fresh.level || old.vocabulary != fresh.vocabulary {''', "catalog reset")

# --- the package: the newest backup again when a note type is missing
s = once(s, '''            guard let notetype = models.notetypes.first(where: { $0.name == type }) else {
                throw Failure.reason("В бэкапе AnkiMobile нет типа заметок «" + type + "». Сделайте свежий бэкап в "
                    + "AnkiMobile: Satori прочитает его сам.")
            }''', '''            guard let notetype = models.notetypes.first(where: { $0.name == type }) else {
                throw Failure.reason(missing(type, in: models))
            }''', "missing reason")
s = once(s, '''    /// The front of a card type shows a field that is not empty: Anki makes that card of the note.''', '''    /// The note type of a queued note (its "type" in the link to AnkiMobile).
    static func type(of entry: MiningQueue.Entry) -> String {
        let items = URLComponents(string: entry.url)?.percentEncodedQueryItems ?? []
        let value = items.first { $0.name == "type" }?.value ?? ""
        return value.removingPercentEncoding ?? value
    }

    /// Why a note type is not in the package: the date of the backup read and how many note types it had.
    @MainActor
    private static func missing(_ type: String, in models: Models) -> String {
        var text = "В бэкапе AnkiMobile нет типа заметок «" + type + "»"
        if let date = AnkiBackupSync.shared.lastRead {
            let format = DateFormatter()
            format.locale = Locale(identifier: "ru_RU")
            format.dateFormat = "d MMMM"
            text += " (бэкап от " + format.string(from: date) + ", типов в нём: " + String(models.notetypes.count) + ")"
            // AnkiMobile keeps its new backups in «Backups for <profile>»: the old «Backups» is not filled any more
            if Date().timeIntervalSince(date) > 3 * 86_400 {
                return text + ". Бэкап старый: в Настройках → Anki → «Папка бэкапов AnkiMobile» выберите папку «Anki» "
                    + "целиком, а не «Backups»."
            }
        }
        return text + ". Сделайте свежий бэкап в AnkiMobile: Satori прочитает его сам."
    }

    /// The front of a card type shows a field that is not empty: Anki makes that card of the note.''', "type helper")
s = once(s, '''            let backups = AnkiBackupSync.shared
            if !MiningBatch.known, backups.connected {''', '''            let backups = AnkiBackupSync.shared
            // a note type the read backup does not have (or no backup read yet): the newest backup is read again now
            let have = Set((MiningBatch.models()?.notetypes ?? []).map { $0.name })
            let need = Set(batch.map { MiningBatch.type(of: $0) })
            if !need.isSubset(of: have), backups.connected {''', "reread on missing")

s = s.rstrip("\n") + "\n" + '''
// MARK: - Satori v2.20: the analyses once a day, in the background

/// An analysis counted with other known words stays for a day: the words of a day change its numbers little, and a
/// count after every launch kept the lists busy.
enum AnalysisAge {
    static let day: TimeInterval = 86_400

    static func fresh(_ made: Date?) -> Bool {
        guard let made else { return false }
        return Date().timeIntervalSince(made) < day
    }
}

/// Once a day while the app is open (MainView): the coverage of every video with subtitles and the analysis of every
/// downloaded novel are counted again with the known words of the day, so «Видео» and «Чтение» show them at once.
@available(iOS 16.0, *)
@MainActor
enum DailyAnalysis {
    private static let key = "ykAnalysisDone"
    private static var running = false

    static func runIfDue() async {
        let last = UserDefaults.standard.double(forKey: key)
        guard !running, Date().timeIntervalSince1970 - last >= AnalysisAge.day else { return }
        running = true
        defer {
            running = false
        }
        await videos()
        for ncode in NovelStore.shared.downloaded.keys.sorted() {
            NovelAnalyzer.shared.ensure(ncode)
        }
        UserDefaults.standard.set(Date().timeIntervalSince1970, forKey: key)
    }

    /// The videos of «Видео» and of the linked folders (downloaded to the end), in all their folders.
    private static func allVideos() -> [URL] {
        var roots: [URL] = []
        if let main = YomikiriMediaSchemeHandler.videosDirectory() {
            roots.append(main)
        }
        roots += LinkedFolders.all()
        var files: [URL] = []
        for root in roots {
            let linked = LinkedFolders.root(of: root) != nil
            guard let walker = FileManager.default.enumerator(at: root, includingPropertiesForKeys: nil,
                                                              options: [.skipsHiddenFiles]) else { continue }
            for case let url as URL in walker where VideoLibraryStore.isVideo(url.lastPathComponent) {
                if !linked || LinkedFolders.isComplete(url) {
                    files.append(url)
                }
            }
        }
        return files
    }

    private static func videos() async {
        let files = allVideos()
        guard !files.isEmpty else { return }
        let index = await CatalogStore.knownIndex()
        let level = VideoLibraryStore.userLevel
        let vocabulary = VideoLibraryStore.vocabulary(level: level)
        for video in files {
            guard let subtitles = VideoLibraryStore.jimakuFile(for: video) else { continue }
            let key = VideoKey.of(video)
            let size = ((try? FileManager.default.attributesOfItem(atPath: subtitles.path)[.size]) as? Int) ?? 0
            if let data = UserDefaults.standard.data(forKey: "coverage." + key),
               let saved = try? JSONDecoder().decode(CoverageEntry.self, from: data),
               saved.level == level, saved.vocabulary == vocabulary, saved.size == size,
               saved.knownWords == index.fingerprint || AnalysisAge.fresh(saved.made),
               saved.algorithm == TextAnalysis.textVersion {
                continue
            }
            let result = await Task.detached(priority: .utility) {
                VideoLibraryStore.analyze(of: subtitles, index: index, level: level, vocabulary: vocabulary)
            }.value
            guard let result else { continue }
            let entry = CoverageEntry(level: level, vocabulary: vocabulary, knownWords: index.fingerprint, size: size,
                                      coverage: result.coverage, difficulty: result.difficulty,
                                      knownShare: result.knownShare, clearShare: result.clearShare,
                                      algorithm: TextAnalysis.textVersion, made: Date())
            if let data = try? JSONEncoder().encode(entry) {
                UserDefaults.standard.set(data, forKey: "coverage." + key)
            }
        }
    }
}
'''
hv.write_text(s, encoding="utf-8")

mv = pathlib.Path("src/safari/iOS (App)/MainView.swift")
m = mv.read_text(encoding="utf-8")
m = once(m, '''        .task(id: backupInterval) {''', '''        .task {
            // the coverage of the videos and the analysis of the novels: once a day in the background
            guard #available(iOS 16.0, *) else { return }
            try? await Task.sleep(nanoseconds: 15_000_000_000)
            while !Task.isCancelled {
                if UIApplication.shared.applicationState == .active {
                    await DailyAnalysis.runIfDue()
                }
                try? await Task.sleep(nanoseconds: 1_800_000_000_000)
            }
        }
        .task(id: backupInterval) {''', "daily task")
mv.write_text(m, encoding="utf-8")

# --- the web: the decks of a backup on their own
ai = pathlib.Path("src/main/src/lib/ankiImport.ts")
a = ai.read_text(encoding="utf-8")
a = once(a, '''    for (const row of rowsOf(db.exec("select id, name, config from notetypes"))) {''',
         '''    for (const row of rowsOf(db.exec("select id, name, config from notetypes order by id"))) {''', "notetypes order")
a = once(a, '''    for (const row of rowsOf(db.exec("select id, name from decks"))) {
      models.decks.push({ id: Number(row[0]), name: String(row[1]).replace(/\\x1f/g, "::") });
    }
    if (models.notetypes.length > 0) return models;
  } catch (e) {
    // older collections keep them in col.models and col.decks
  }''', '''    try {
      for (const row of rowsOf(db.exec("select id, name from decks order by id"))) {
        models.decks.push({ id: Number(row[0]), name: String(row[1]).replace(/\\x1f/g, "::") });
      }
    } catch (e) {
      // the decks are matched by their names anyway; a query through the index of their names needs the collation
      // "unicase", which sql.js does not have
    }
    if (models.notetypes.length > 0) return models;
  } catch (e) {
    // older collections keep them in col.models and col.decks
    models.notetypes = [];
    models.decks = [];
  }''', "decks alone")
ai.write_text(a, encoding="utf-8")
print("v2.20 daily analysis applied")
