# v1.66: the rest of the code review.
# - The settings of a video (position, watched, subtitle choice and delay, coverage, cover, its mining queue) are kept
#   by its path inside the Videos folder, not by the file name: two "01.mkv" in two folders shared them. A file at the
#   top keeps its name as before; the settings saved under the bare name are copied once; a move takes them along;
#   deleting a folder removes the settings of its videos.
# - Safari: when the app could not be asked for the statistics, the extension used its own old copy and then wrote it
#   back into the app (words added in the app were lost). Such a copy is not written to the app any more, and the
#   one-time move of the old statistics into the app happens only once.
# - The mining queue keeps the frames of its notes in files (Library/mining-frames), not inside the saved queue.
# - Jimaku: "BD" / "WEB" releases by whole words only.
# - Unused code removed: the old web player (PlayerWebView, PlayerHTML), YomikiriVideoLibrary, watchText.
import pathlib


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


def times(text, old, new, count, label):
    assert text.count(old) == count, "pattern not found " + str(count) + " times: " + label
    return text.replace(old, new)


def cut(text, start, end, label):
    assert text.count(start) == 1, "start not found exactly once: " + label
    a = text.index(start)
    b = text.index(end, a)
    return text[:a] + text[b:]


hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")

# ---------- the key of a video: its path inside the Videos folder ----------
s = once(s, "/// Where a video was stopped and whether it was watched to the end (kept per file name).\n",
         '''/// The key of a video's settings: its path inside the Videos folder ("Show/01.mkv"). A file at the top keeps its
/// name, as before 1.66; the settings saved under the bare name are copied to the path once.
enum VideoKey {
    static let prefixes = ["resume.", "duration.", "watched.", "subchoice.", "subdelay.", "coverage."]
    private static var migrated = Set<String>()

    /// The path, without copying old settings.
    static func path(_ url: URL) -> String {
        let name = url.lastPathComponent
        guard let root = YomikiriMediaSchemeHandler.videosDirectory()?.standardizedFileURL.path else { return name }
        let full = url.standardizedFileURL.path
        guard full.hasPrefix(root + "/") else { return name }
        return String(full.dropFirst(root.count + 1))
    }

    static func of(_ url: URL) -> String {
        let key = path(url)
        let name = url.lastPathComponent
        if key != name, !migrated.contains(key) {
            migrated.insert(key)
            let defaults = UserDefaults.standard
            if !prefixes.contains(where: { defaults.object(forKey: $0 + key) != nil }) {
                for prefix in prefixes {
                    if let value = defaults.object(forKey: prefix + name) {
                        defaults.set(value, forKey: prefix + key)
                    }
                }
                VideoThumbnails.copy(from: name, to: key)
            }
        }
        return key
    }

    /// A moved file takes its settings along.
    static func move(from old: String, to new: String) {
        guard old != new else { return }
        let defaults = UserDefaults.standard
        for prefix in prefixes {
            if let value = defaults.object(forKey: prefix + old) {
                defaults.set(value, forKey: prefix + new)
                defaults.removeObject(forKey: prefix + old)
            }
        }
        migrated.insert(new)
        VideoThumbnails.move(from: old, to: new)
    }

    static func remove(_ key: String) {
        for prefix in prefixes {
            UserDefaults.standard.removeObject(forKey: prefix + key)
        }
        VideoThumbnails.remove(key)
    }

    /// The settings of every video inside a folder (before the folder is deleted).
    static func removeAll(inside folder: URL) {
        guard let files = FileManager.default.enumerator(at: folder, includingPropertiesForKeys: nil) else { return }
        // the same extensions as VideoLibraryStore.isVideo (that store is main-actor and iOS 16 only)
        let videos: Set<String> = ["mkv", "mp4", "mov", "m4v", "webm", "avi"]
        for case let file as URL in files where videos.contains(file.pathExtension.lowercased()) {
            remove(path(file))
        }
    }
}

/// Where a video was stopped and whether it was watched to the end (kept per VideoKey).
''', "video key")

s = once(s, """    private static func file(_ name: String) -> URL {
        folder.appendingPathComponent(name + ".jpg")
    }
""", """    /// a key can be a path: "/" would be a folder of the cache
    private static func file(_ name: String) -> URL {
        folder.appendingPathComponent(name.replacingOccurrences(of: "/", with: "%2F") + ".jpg")
    }

    static func copy(from old: String, to new: String) {
        guard FileManager.default.fileExists(atPath: file(old).path), !exists(new) else { return }
        try? FileManager.default.copyItem(at: file(old), to: file(new))
    }

    static func move(from old: String, to new: String) {
        memory[new] = memory[old]
        memory[old] = nil
        guard FileManager.default.fileExists(atPath: file(old).path) else { return }
        try? FileManager.default.removeItem(at: file(new))
        try? FileManager.default.moveItem(at: file(old), to: file(new))
    }
""", "cover file")

# the player
s = once(s, """        let name = url.lastPathComponent
        let saved = VideoProgress.position(name)
""", """        let name = VideoKey.of(url)
        let saved = VideoProgress.position(name)
""", "player start time")
s = once(s, """    private var delayKey: String { "subdelay." + url.lastPathComponent }
    private var subChoiceKey: String { "subchoice." + url.lastPathComponent }
""", """    private var delayKey: String { "subdelay." + VideoKey.of(url) }
    private var subChoiceKey: String { "subchoice." + VideoKey.of(url) }
""", "player keys")
s = times(s, "VideoProgress.save(url.lastPathComponent, position: position, duration: duration)",
          "VideoProgress.save(VideoKey.of(url), position: position, duration: duration)", 2, "player progress")
s = once(s, """        let name = url.lastPathComponent
        guard !VideoThumbnails.exists(name) else { return }
""", """        let name = VideoKey.of(url)
        guard !VideoThumbnails.exists(name) else { return }
""", "player cover")
s = once(s, """        let video = url.lastPathComponent
        yomikiriQueuedWordsHook = {
""", """        let video = VideoKey.of(url)
        yomikiriQueuedWordsHook = {
""", "player queue video")

# Jimaku
s = once(s, """                UserDefaults.standard.set(r.delay, forKey: "subdelay." + name)
                UserDefaults.standard.set("file:" + dest.lastPathComponent, forKey: "subchoice." + name)
""", """                let key = VideoKey.of(video)
                UserDefaults.standard.set(r.delay, forKey: "subdelay." + key)
                UserDefaults.standard.set("file:" + dest.lastPathComponent, forKey: "subchoice." + key)
""", "jimaku keys")
s = once(s, """    static func release(_ file: String) -> String? {
        let upper = file.uppercased()
        if upper.contains("BD") { return "BD" }
        if upper.contains("WEB") { return "WEB" }
        return nil
    }
""", """    static func release(_ file: String) -> String? {
        // whole words only: "BD" inside "ABDUCTION" is no release
        let range = NSRange(file.startIndex..., in: file)
        let bd = try? NSRegularExpression(pattern: #"(?i)(?<![a-z])(bd|bdrip|bdremux|blu-?ray)(?![a-z])"#)
        if bd?.firstMatch(in: file, range: range) != nil { return "BD" }
        let web = try? NSRegularExpression(pattern: #"(?i)(?<![a-z])(web|web-?dl|web-?rip)(?![a-z])"#)
        if web?.firstMatch(in: file, range: range) != nil { return "WEB" }
        return nil
    }
""", "jimaku release")

# the library: coverage, covers, delete, move
s = once(s, "        var candidates: [(String, URL)] = []\n", "        var candidates: [(String, URL, String)] = []\n", "candidates type")
s = once(s, "                        candidates.append((video.lastPathComponent, file))\n",
         "                        candidates.append((video.lastPathComponent, file, VideoKey.of(video)))\n", "folder candidate")
s = once(s, "                candidates.append((item.url.lastPathComponent, file))\n",
         "                candidates.append((item.url.lastPathComponent, file, VideoKey.of(item.url)))\n", "candidate")
s = once(s, "        var pending: [(String, URL, Int)] = []\n        for (name, file) in candidates {\n",
         "        var pending: [(String, URL, Int, String)] = []\n        for (name, file, key) in candidates {\n", "pending type")
s = once(s, '            if let data = UserDefaults.standard.data(forKey: "coverage." + name),\n',
         '            if let data = UserDefaults.standard.data(forKey: "coverage." + key),\n', "coverage read")
s = once(s, "            pending.append((name, file, size))\n", "            pending.append((name, file, size, key))\n", "pending append")
s = once(s, "            for (name, file, size) in pending {\n", "            for (name, file, size, key) in pending {\n", "pending loop")
s = once(s, '                    UserDefaults.standard.set(data, forKey: "coverage." + name)\n',
         '                    UserDefaults.standard.set(data, forKey: "coverage." + key)\n', "coverage write")
s = once(s, """    /// A folder: the averages of its analysed episodes.
    /// Covers for the videos here that have none yet: the picture attached to the file.
    private func updateThumbnails() {
        let missing = items.filter { !$0.isFolder && VideoLibraryStore.isVideo($0.url.lastPathComponent)
            && !VideoThumbnails.exists($0.url.lastPathComponent) && !VideoThumbnails.tried.contains($0.url.lastPathComponent) }
        guard !missing.isEmpty else { return }
        for item in missing {
            VideoThumbnails.tried.insert(item.url.lastPathComponent)
        }
""", """    /// Covers for the videos here that have none yet: the picture attached to the file.
    private func updateThumbnails() {
        let missing = items.filter { item in
            guard !item.isFolder, VideoLibraryStore.isVideo(item.url.lastPathComponent) else { return false }
            let key = VideoKey.of(item.url)
            return !VideoThumbnails.exists(key) && !VideoThumbnails.tried.contains(key)
        }
        guard !missing.isEmpty else { return }
        for item in missing {
            VideoThumbnails.tried.insert(VideoKey.of(item.url))
        }
""", "thumbnails")
s = once(s, "                    VideoThumbnails.save(found, for: url.lastPathComponent)\n",
         "                    VideoThumbnails.save(found, for: VideoKey.of(url))\n", "thumbnail save")
s = once(s, """    private func updateFolders(_ folderVideos: [String: [String]]) {
""", """    /// A folder: the averages of its analysed episodes.
    private func updateFolders(_ folderVideos: [String: [String]]) {
""", "folders comment")
s = once(s, """        let name = item.url.lastPathComponent
        if !item.isFolder, VideoLibraryStore.isVideo(name) {
            let siblings = (try? fm.contentsOfDirectory(at: folder, includingPropertiesForKeys: nil)) ?? []
            for file in siblings where VideoLibraryStore.subtitle(file, belongsTo: item.url) {
                try? fm.removeItem(at: file)
            }
            for key in ["resume.", "watched.", "subchoice.", "subdelay.", "duration."] {
                UserDefaults.standard.removeObject(forKey: key + name)
            }
        }
""", """        let name = item.url.lastPathComponent
        if item.isFolder {
            VideoKey.removeAll(inside: item.url)
        }
        if !item.isFolder, VideoLibraryStore.isVideo(name) {
            let siblings = (try? fm.contentsOfDirectory(at: folder, includingPropertiesForKeys: nil)) ?? []
            for file in siblings where VideoLibraryStore.subtitle(file, belongsTo: item.url) {
                try? fm.removeItem(at: file)
            }
            VideoKey.remove(VideoKey.path(item.url))
        }
""", "delete keys")
s = once(s, """            UserDefaults.standard.removeObject(forKey: "coverage." + name)
            VideoThumbnails.remove(name)
""", "", "delete old keys")
s = once(s, """                guard !fm.fileExists(atPath: dest.path) else { continue }
                if (try? fm.moveItem(at: file, to: dest)) != nil {
                    moved = true
                }
""", """                guard !fm.fileExists(atPath: dest.path) else { continue }
                let oldKey = VideoKey.path(file)
                if (try? fm.moveItem(at: file, to: dest)) != nil {
                    moved = true
                    if VideoLibraryStore.isVideo(file.lastPathComponent) {
                        VideoKey.move(from: oldKey, to: VideoKey.path(dest))
                    }
                }
""", "move keys")
s = once(s, "                if !item.isFolder, let thumb = VideoThumbnails.image(for: name) {\n",
         "                if !item.isFolder, let thumb = VideoThumbnails.image(for: VideoKey.of(item.url)) {\n", "row cover")
s = once(s, "                } else if !item.isFolder, let watched = VideoProgress.fraction(name) {\n",
         "                } else if !item.isFolder, let watched = VideoProgress.fraction(VideoKey.of(item.url)) {\n", "row progress")
s = once(s, "                                queueVideo = item.url.lastPathComponent\n",
         "                                queueVideo = VideoKey.of(item.url)\n", "row queue")

# ---------- the mining queue: frames in files ----------
s = once(s, """    struct Entry: Codable, Identifiable {
        var id = UUID()
        let video: String
        let word: String
        let sentence: String
        let url: String
    }
""", """    struct Entry: Codable, Identifiable {
        var id = UUID()
        let video: String
        let word: String
        let sentence: String
        var url: String
        /// the frame of the note in Library/mining-frames (its field holds frameMarker)
        var frame: String? = nil
    }

    private static let frameMarker = "yk-frame"
    private static let framePrefix = "<img src=\\"data:image/jpeg;base64,"

    private static var frameFolder: URL {
        let base = FileManager.default.urls(for: .libraryDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("mining-frames")
        try? FileManager.default.createDirectory(at: base, withIntermediateDirectories: true)
        return base
    }

    /// The base64 picture of a note goes to its own file: the saved queue grew by ~80 KB with every note.
    static func detachFrame(_ entry: inout Entry) {
        guard entry.frame == nil, var parts = URLComponents(string: entry.url),
              var items = parts.percentEncodedQueryItems else { return }
        for index in items.indices {
            guard let value = items[index].value?.removingPercentEncoding, value.hasPrefix(framePrefix) else { continue }
            let body = value.dropFirst(framePrefix.count)
            guard let end = body.firstIndex(of: "\\""), let data = Data(base64Encoded: String(body[..<end])) else { continue }
            let name = entry.id.uuidString + ".jpg"
            guard (try? data.write(to: frameFolder.appendingPathComponent(name))) != nil else { return }
            items[index].value = frameMarker
            parts.percentEncodedQueryItems = items
            guard let short = parts.url?.absoluteString else { return }
            entry.url = short
            entry.frame = name
            return
        }
    }

    /// The note as AnkiMobile gets it: the frame back in its field.
    static func fullURL(_ entry: Entry) -> URL? {
        guard let name = entry.frame, var parts = URLComponents(string: entry.url),
              var items = parts.percentEncodedQueryItems else { return URL(string: entry.url) }
        let data = try? Data(contentsOf: frameFolder.appendingPathComponent(name))
        for index in items.indices where items[index].value == frameMarker {
            if let data {
                let html = framePrefix + data.base64EncodedString() + "\\">"
                items[index].value = html.addingPercentEncoding(withAllowedCharacters: ankiQueryAllowed)
            } else {
                items[index].value = ""
            }
        }
        parts.percentEncodedQueryItems = items
        return parts.url
    }

    private static func deleteFrame(_ entry: Entry) {
        guard let name = entry.frame else { return }
        try? FileManager.default.removeItem(at: frameFolder.appendingPathComponent(name))
    }
""", "queue entry")
s = once(s, """        if let data = UserDefaults.standard.data(forKey: key),
           let saved = try? JSONDecoder().decode([Entry].self, from: data) {
            entries = saved
        }
""", """        if let data = UserDefaults.standard.data(forKey: key),
           let saved = try? JSONDecoder().decode([Entry].self, from: data) {
            entries = saved
            // notes saved before 1.66 still carry their frame
            var changed = false
            for index in entries.indices where entries[index].frame == nil {
                MiningQueue.detachFrame(&entries[index])
                changed = changed || entries[index].frame != nil
            }
            if changed {
                save()
            }
        }
""", "queue migrate")
s = once(s, """        entries.append(Entry(video: video, word: field(["word", "expression", "vocab", "слово"]),
                             sentence: field(["sentence", "предложение"]), url: url.absoluteString))
        save()
""", """        var entry = Entry(video: video, word: field(["word", "expression", "vocab", "слово"]),
                          sentence: field(["sentence", "предложение"]), url: url.absoluteString)
        MiningQueue.detachFrame(&entry)
        entries.append(entry)
        save()
""", "queue add")
s = once(s, """    func remove(_ entry: Entry) {
        entries.removeAll { $0.id == entry.id }
        save()
    }
""", """    func remove(_ entry: Entry) {
        MiningQueue.deleteFrame(entry)
        entries.removeAll { $0.id == entry.id }
        save()
    }
""", "queue remove")
s = once(s, """        guard let next = sending.first, let url = URL(string: next.url) else {
""", """        guard let next = sending.first, let url = MiningQueue.fullURL(next) else {
""", "queue send")
s = once(s, """        sending.removeFirst()
        entries.removeAll { $0.id == done.id }
""", """        sending.removeFirst()
        MiningQueue.deleteFrame(done)
        entries.removeAll { $0.id == done.id }
""", "queue sent")

# ---------- unused code ----------
s = cut(s, "enum YomikiriVideoLibrary {\n", "struct VideoTabView: View {\n", "video library")
s = cut(s, "    private func watchText(_ name: String, isFolder: Bool) -> String? {\n",
        "    private func symbol(for name: String) -> String {\n", "watch text")
s = cut(s, "struct PlayerWebView: UIViewRepresentable {\n", "// MARK: - Native settings (iOS 26 look)\n", "web player")
for gone in ["PlayerHTML", "PlayerWebView", "YomikiriVideoLibrary", "watchText("]:
    assert gone not in s, "left over: " + gone
hv.write_text(s, encoding="utf-8")

# ---------- Safari: an old copy of the statistics is not written into the app ----------
st = pathlib.Path("src/main/src/extension/stats.ts")
t = st.read_text(encoding="utf-8")
t = once(t, """/** The statistics are kept by the app, so the extension and the app see the same numbers. */
async function nativeLoad(): Promise<StatsData | null> {
  try {
    // eslint-disable-next-line
    const v = await (Platform as any).requestToApp("loadStats", null);
    if (v !== null && typeof v === "object" && v.days !== undefined) {
      return v as StatsData;
    }
    return null;
  } catch (_e) {
    return null;
  }
}
""", """/**
 * The statistics are kept by the app, so the extension and the app see the same numbers.
 * null: the app has none yet; undefined: the app could not be asked.
 */
async function nativeLoad(): Promise<StatsData | null | undefined> {
  try {
    // eslint-disable-next-line
    const v = await (Platform as any).requestToApp("loadStats", null);
    if (v !== null && typeof v === "object" && v.days !== undefined) {
      return v as StatsData;
    }
    return null;
  } catch (_e) {
    return undefined;
  }
}

/** false after a failed read: the local copy may be old and must not replace the statistics of the app */
let appReachable = true;
const MOVED_KEY = "stats:movedToApp";

function getFlag(key: string): Promise<boolean> {
  return new Promise((resolve) => {
    browserStorage().get(key, (obj) => resolve(obj?.[key] === true));
  });
}
""", "native load")
t = once(t, """export async function loadStats(): Promise<StatsData> {
  let data = await nativeLoad();
  if (data === null) {
    data = await localLoad();
    // first run after an update: move the old statistics to the app
    if (data !== null) await nativeSave(data);
  }
  if (data === null) data = { days: {} };
""", """export async function loadStats(): Promise<StatsData> {
  const fromApp = await nativeLoad();
  appReachable = fromApp !== undefined;
  let data: StatsData | null = fromApp ?? null;
  if (data === null) {
    data = await localLoad();
    // the first run after the update to app statistics: the old statistics move to the app, once
    if (fromApp === null && data !== null && !(await getFlag(MOVED_KEY))) {
      await nativeSave(data);
      browserStorage().set({ [MOVED_KEY]: true }, () => undefined);
    }
  }
  if (data === null) data = { days: {} };
""", "load stats")
t = once(t, """async function saveStats(data: StatsData): Promise<void> {
  await nativeSave(data);
  await localSave(data);
}
""", """async function saveStats(data: StatsData): Promise<void> {
  if (appReachable) await nativeSave(data);
  await localSave(data);
}
""", "save stats")
st.write_text(t, encoding="utf-8")
print("v1.66 fixes applied")
