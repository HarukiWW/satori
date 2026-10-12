# v1.42 (player): clear title bars in the player sheets, delete in the video list, subtitle files hidden
# in the video list, Jimaku search right on import.
import pathlib

p = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = p.read_text(encoding="utf-8")


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


# 1) the title bars of the "Субтитры" and "Настройки" sheets: no black bar, the sheet background shows through
for title in ("Субтитры", "Настройки"):
    s = once(s,
             f'            .navigationTitle("{title}")\n            .navigationBarTitleDisplayMode(.inline)\n',
             f'            .navigationTitle("{title}")\n            .navigationBarTitleDisplayMode(.inline)\n'
             '            .toolbarBackground(.hidden, for: .navigationBar)\n',
             "title bar " + title)

# 2) subtitle files: recognised, hidden from the list, deleted together with their video
s = once(s, '''    static func isVideo(_ name: String) -> Bool {
        videoExtensions.contains((name as NSString).pathExtension.lowercased())
    }
''', '''    static func isVideo(_ name: String) -> Bool {
        videoExtensions.contains((name as NSString).pathExtension.lowercased())
    }

    static func isSubtitle(_ name: String) -> Bool {
        ["srt", "ass", "ssa", "vtt"].contains((name as NSString).pathExtension.lowercased())
    }

    /// A subtitle file made for this video: "<video name>.srt" or "<video name>.<tag>.srt" (ja, jimaku ...).
    static func subtitle(_ file: URL, belongsTo video: URL) -> Bool {
        guard isSubtitle(file.lastPathComponent) else { return false }
        let base = video.deletingPathExtension().lastPathComponent
        let stem = file.deletingPathExtension().lastPathComponent
        if stem == base { return true }
        let tag = (stem as NSString).pathExtension
        return !tag.isEmpty && !tag.contains(" ") && (stem as NSString).deletingPathExtension == base
    }
''', "isSubtitle")

s = once(s, '''        items = urls.map { url -> Item in
            let isDir = (try? url.resourceValues(forKeys: [.isDirectoryKey]).isDirectory) ?? false
            return Item(url: url, isFolder: isDir)
        }
        .sorted { a, b in
''', '''        items = urls.map { url -> Item in
            let isDir = (try? url.resourceValues(forKeys: [.isDirectoryKey]).isDirectory) ?? false
            return Item(url: url, isFolder: isDir)
        }
        // subtitle files stay next to their video, but the list shows only videos and folders
        .filter { $0.isFolder || !VideoLibraryStore.isSubtitle($0.url.lastPathComponent) }
        .sorted { a, b in
''', "reload filter")

s = once(s, '''    func createFolder(named name: String) {
''', '''    /// Deletes a folder with everything in it, or a video with its own subtitle files and saved progress.
    func delete(_ item: Item) {
        let fm = FileManager.default
        let name = item.url.lastPathComponent
        if !item.isFolder, VideoLibraryStore.isVideo(name) {
            let siblings = (try? fm.contentsOfDirectory(at: folder, includingPropertiesForKeys: nil)) ?? []
            for file in siblings where VideoLibraryStore.subtitle(file, belongsTo: item.url) {
                try? fm.removeItem(at: file)
            }
            for key in ["resume.", "watched.", "subchoice.", "subdelay."] {
                UserDefaults.standard.removeObject(forKey: key + name)
            }
        }
        try? fm.removeItem(at: item.url)
        status[name] = nil
        progress[name] = nil
        reload()
    }

    func createFolder(named name: String) {
''', "delete")

# 3) Jimaku right on import (with a key): subtitles found there need no recognition
s = once(s, '''        status[name] = "проверяю дорожки…"
        Task { @MainActor in
            let needsOCR = await Task.detached(priority: .utility) { () -> Bool in
''', '''        status[name] = "проверяю дорожки…"
        Task { @MainActor in
            if JimakuKeychain.read() != nil {
                let found = await JimakuFinder.run(video, report: { message in self.status[name] = message })
                if found != nil {
                    reload()
                    return
                }
            }
            let needsOCR = await Task.detached(priority: .utility) { () -> Bool in
''', "jimaku on import")

# 4) delete in the video list: swipe or long press, always with a confirmation
s = once(s, '''    @State private var showKey = false
''', '''    @State private var showKey = false
    @State private var pendingDelete: VideoLibraryStore.Item? = nil
''', "delete state")

s = once(s, '''            ForEach(library.items) { item in
                row(item)
            }
        }
        .navigationTitle(title)
''', '''            ForEach(library.items) { item in
                row(item)
                    .swipeActions(edge: .trailing, allowsFullSwipe: false) {
                        Button(role: .destructive) {
                            pendingDelete = item
                        } label: {
                            Label("Удалить", systemImage: "trash")
                        }
                    }
                    .contextMenu {
                        Button(role: .destructive) {
                            pendingDelete = item
                        } label: {
                            Label("Удалить", systemImage: "trash")
                        }
                    }
            }
        }
        // the confirmation sits on its own view, apart from the other dialogs of the list
        .background(
            Color.clear.confirmationDialog(
                pendingDelete.map { "Удалить «\\($0.url.lastPathComponent)»?" } ?? "Удалить?",
                isPresented: Binding(get: { pendingDelete != nil },
                                     set: { if !$0 { pendingDelete = nil } }),
                titleVisibility: .visible
            ) {
                Button("Удалить", role: .destructive) {
                    if let item = pendingDelete {
                        library.delete(item)
                    }
                    pendingDelete = nil
                }
                Button("Отмена", role: .cancel) {
                    pendingDelete = nil
                }
            } message: {
                Text(pendingDelete?.isFolder == true
                     ? "Папка будет удалена вместе со всем содержимым."
                     : "Видео будет удалено вместе со своими субтитрами.")
            }
        )
        .navigationTitle(title)
''', "list delete")

p.write_text(s, encoding="utf-8")
print("v1.42 player patch applied")
