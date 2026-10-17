
// MARK: - Satori v2.10: the voice, the folders of other apps

/// The Japanese voice of Satori (Настройки → Озвучка): "" is the system's Japanese voice, the one chosen in the
/// settings of iOS (Универсальный доступ → Устной контент → Голоса → Японский).
enum SatoriVoice {
    static let key = "ykVoice"

    static var voices: [TTSVoice] {
        japaneseTtsVoices().sorted { a, b in
            a.quality != b.quality ? a.quality > b.quality : a.name < b.name
        }
    }

    static func label(_ voice: TTSVoice) -> String {
        if voice.quality >= 300 {
            return voice.name + " · премиум"
        }
        return voice.quality >= 200 ? voice.name + " · улучшенный" : voice.name
    }

    /// nil: the system's voice
    static var chosen: TTSVoice? {
        let id = UserDefaults.standard.string(forKey: key) ?? ""
        guard !id.isEmpty else { return nil }
        return TTSVoice(id: id, name: "", quality: 0)
    }

    static func speak(_ text: String) {
        guard !text.isEmpty else { return }
        if synthesizer.isSpeaking {
            synthesizer.stopSpeaking(at: .immediate)
        }
        try? ttsSpeak(voice: chosen, text: text)
    }
}

/// Folders of other apps in «Видео» (the downloads of iTorrent), read in place: nothing is copied. The access the
/// picker gave is kept in a bookmark and opened once a launch; in such a folder only its folders and the videos
/// downloaded to the end show.
enum LinkedFolders {
    private static let key = "ykLinkedFolders"
    private static let lock = NSLock()
    private static var opened: [URL]? = nil

    static func all() -> [URL] {
        lock.lock()
        defer { lock.unlock() }
        if let opened {
            return opened
        }
        var urls: [URL] = []
        var kept: [Data] = []
        for data in (UserDefaults.standard.array(forKey: key) as? [Data]) ?? [] {
            var stale = false
            // a folder that is gone (the app deleted) is dropped
            guard let url = try? URL(resolvingBookmarkData: data, bookmarkDataIsStale: &stale) else { continue }
            _ = url.startAccessingSecurityScopedResource()
            if stale, let renewed = try? url.bookmarkData(options: .minimalBookmark, includingResourceValuesForKeys: nil,
                                                         relativeTo: nil) {
                kept.append(renewed)
            } else {
                kept.append(data)
            }
            urls.append(url)
        }
        UserDefaults.standard.set(kept, forKey: key)
        opened = urls
        return urls
    }

    /// A folder chosen in the picker; false when it could not be kept.
    static func add(_ url: URL) -> Bool {
        let list = all()
        if list.contains(where: { $0.standardizedFileURL == url.standardizedFileURL }) {
            return true
        }
        let access = url.startAccessingSecurityScopedResource()
        guard let data = try? url.bookmarkData(options: .minimalBookmark, includingResourceValuesForKeys: nil,
                                               relativeTo: nil) else {
            if access {
                url.stopAccessingSecurityScopedResource()
            }
            return false
        }
        lock.lock()
        var saved = (UserDefaults.standard.array(forKey: key) as? [Data]) ?? []
        saved.append(data)
        UserDefaults.standard.set(saved, forKey: key)
        opened = list + [url]
        lock.unlock()
        return true
    }

    static func remove(_ url: URL) {
        let list = all()
        guard let index = list.firstIndex(where: { $0.standardizedFileURL == url.standardizedFileURL }) else { return }
        lock.lock()
        var saved = (UserDefaults.standard.array(forKey: key) as? [Data]) ?? []
        if index < saved.count {
            saved.remove(at: index)
        }
        UserDefaults.standard.set(saved, forKey: key)
        list[index].stopAccessingSecurityScopedResource()
        var rest = list
        rest.remove(at: index)
        opened = rest
        lock.unlock()
    }

    /// The linked folder a file or folder is in.
    static func root(of file: URL) -> URL? {
        let path = file.standardizedFileURL.path
        return all().first { folder in
            let root = folder.standardizedFileURL.path
            return path == root || path.hasPrefix(root + "/")
        }
    }

    /// The key of a video's settings: "linked:<folder>/<path in it>" (the same names in different folders differ).
    static func key(for file: URL) -> String? {
        guard let root = root(of: file) else { return nil }
        let full = file.standardizedFileURL.path
        let base = root.standardizedFileURL.path
        let inside = full.count > base.count ? String(full.dropFirst(base.count + 1)) : ""
        return "linked:" + root.lastPathComponent + "/" + inside
    }

    /// Downloaded to the end: a torrent client writes the pieces in any order, so until the last one the file has
    /// holes (fewer bytes on disk than its size); and nothing was written into it in the last half minute.
    static func isComplete(_ file: URL) -> Bool {
        let keys: Set<URLResourceKey> = [.fileSizeKey, .totalFileAllocatedSizeKey, .contentModificationDateKey]
        guard let values = try? file.resourceValues(forKeys: keys), let size = values.fileSize, size > 0 else {
            return false
        }
        if let allocated = values.totalFileAllocatedSize, allocated < size {
            return false
        }
        if let changed = values.contentModificationDate, Date().timeIntervalSince(changed) < 30 {
            return false
        }
        return true
    }
}
