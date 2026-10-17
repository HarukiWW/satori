# v1.94: subtitles.
# - A video without subtitles of its own (a raw release) gets the best Japanese file of Jimaku as it is: there is
#   nothing to check its timing against (before, every file was refused: "совпадений мало"). The delay can be set by
#   hand as before.
# - The subtitles of the video are read once for the check, not once for every file of Jimaku (up to five passes over
#   a large file).
# - Dramas and films: when nothing is found among the anime of Jimaku, the other entries are searched too.
# - Videos put into the folder through Files (or saved there by another app) get their subtitles looked for once,
#   like imported ones.
import pathlib


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")

# ---------- Jimaku: films and dramas ----------
s = once(s, '''    static func search(_ title: String, key: String) async throws -> [Entry] {
        try await get("/api/entries/search",
                      query: [URLQueryItem(name: "anime", value: "true"),
                              URLQueryItem(name: "query", value: title)],
                      key: key)
    }
''', '''    static func search(_ title: String, key: String) async throws -> [Entry] {
        let anime: [Entry] = try await get("/api/entries/search",
                                           query: [URLQueryItem(name: "anime", value: "true"),
                                                   URLQueryItem(name: "query", value: title)],
                                           key: key)
        if !anime.isEmpty {
            return anime
        }
        // dramas and films are the entries without the anime flag
        return try await get("/api/entries/search",
                             query: [URLQueryItem(name: "anime", value: "false"),
                                     URLQueryItem(name: "query", value: title)],
                             key: key)
    }
''', "jimaku search")

# ---------- Jimaku: one reading of the video, raw videos ----------
s = once(s, '''            let files = try await JimakuService.files(entry: entry.id, episode: episode, key: key)
            for file in JimakuService.pickFiles(files, release: JimakuName.release(name)) {
                let temp = try await JimakuService.download(file, key: key)
                let ext = (file.name as NSString).pathExtension.lowercased()
                let dest = video.deletingPathExtension().appendingPathExtension("jimaku." + ext)
                let check = await Task.detached(priority: .utility) { () -> (matches: Int, total: Int, delay: Double)? in
                    let reference = EmbeddedSubtitles.referenceStarts(url: video)
                    guard reference.count >= 8 else { return nil }
                    let external = EmbeddedSubtitles.cues(fromFile: temp).map { $0.start }
''', '''            let files = try await JimakuService.files(entry: entry.id, episode: episode, key: key)
            // the lines of the video's own subtitles, read once for every file
            let reference = await Task.detached(priority: .utility) {
                EmbeddedSubtitles.referenceStarts(url: video)
            }.value
            for file in JimakuService.pickFiles(files, release: JimakuName.release(name)) {
                let temp = try await JimakuService.download(file, key: key)
                let ext = (file.name as NSString).pathExtension.lowercased()
                let dest = video.deletingPathExtension().appendingPathExtension("jimaku." + ext)
                if reference.count < 8 {
                    // nothing to check the timing against: the first (the best) Japanese file is taken as it is
                    guard !EmbeddedSubtitles.cues(fromFile: temp).isEmpty else { continue }
                    try? FileManager.default.removeItem(at: dest)
                    try FileManager.default.moveItem(at: temp, to: dest)
                    UserDefaults.standard.set("file:" + dest.lastPathComponent, forKey: "subchoice." + VideoKey.of(video))
                    report("Jimaku: найдены, тайминг не проверен (у видео нет своих субтитров)")
                    return dest
                }
                let check = await Task.detached(priority: .utility) { () -> (matches: Int, total: Int, delay: Double)? in
                    let external = EmbeddedSubtitles.cues(fromFile: temp).map { $0.start }
''', "jimaku reference once")

# ---------- videos that came in through Files ----------
s = once(s, '''        reload()
        if VideoLibraryStore.isVideo(dest.lastPathComponent) {
            importQueue.append(dest)
            runImportQueue()
        }
    }
''', '''        VideoLibraryStore.markLooked(dest)
        reload()
        if VideoLibraryStore.isVideo(dest.lastPathComponent) {
            importQueue.append(dest)
            runImportQueue()
        }
    }

    private static let lookedKey = "ykSubtitlesLooked"

    /// The video's subtitles were looked for (or are being looked for): it is not queued again.
    static func markLooked(_ video: URL) {
        var looked = Set(UserDefaults.standard.stringArray(forKey: lookedKey) ?? [])
        if looked.insert(VideoKey.of(video)).inserted {
            UserDefaults.standard.set(Array(looked), forKey: lookedKey)
        }
    }

    /// Videos put into the folder outside the import (Files, a download): their subtitles are looked for once.
    /// A video with subtitle files next to it (imported before 1.94) is only marked.
    private func queueUnlooked() {
        var looked = Set(UserDefaults.standard.stringArray(forKey: VideoLibraryStore.lookedKey) ?? [])
        var changed = false
        for item in items where !item.isFolder && VideoLibraryStore.isVideo(item.url.lastPathComponent) {
            guard looked.insert(VideoKey.of(item.url)).inserted else { continue }
            changed = true
            let base = item.url.deletingPathExtension()
            let hasSubtitles = VideoLibraryStore.jimakuFile(for: item.url) != nil
                || VideoLibraryStore.sidecarSubtitle(for: item.url) != nil
                || FileManager.default.fileExists(atPath: base.appendingPathExtension("ja.srt").path)
            if !hasSubtitles {
                findSubtitles(item.url)
            }
        }
        if changed {
            UserDefaults.standard.set(Array(looked), forKey: VideoLibraryStore.lookedKey)
        }
    }
''', "looked videos")
s = once(s, '''        // subtitle files stay next to their video, but the list shows only videos and folders
        .filter { $0.isFolder || !VideoLibraryStore.isSubtitle($0.url.lastPathComponent) }
        .sorted { a, b in
            if a.isFolder != b.isFolder {
                return a.isFolder
            }
            return a.url.lastPathComponent.localizedStandardCompare(b.url.lastPathComponent) == .orderedAscending
        }
    }
''', '''        // subtitle files stay next to their video, but the list shows only videos and folders
        .filter { $0.isFolder || !VideoLibraryStore.isSubtitle($0.url.lastPathComponent) }
        .sorted { a, b in
            if a.isFolder != b.isFolder {
                return a.isFolder
            }
            return a.url.lastPathComponent.localizedStandardCompare(b.url.lastPathComponent) == .orderedAscending
        }
        queueUnlooked()
    }
''', "reload queues")
hv.write_text(s, encoding="utf-8")
print("v1.94 subtitles applied")
