# v1.53: the delete confirmation is a centered alert (the iOS 26 popover was anchored to the top of the list) and the
# row goes away with an animation; Jimaku search of imported videos runs for all of them at once; files can be dragged
# onto a folder in the video list; statistics cards all have the same height.
import pathlib

hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


# 1) delete: a centered alert, an animated removal
s = once(s, "            Color.clear.confirmationDialog(\n", "            Color.clear.alert(\n", "alert")
s = once(s, "                                     set: { if !$0 { pendingDelete = nil } }),\n                titleVisibility: .visible\n            ) {",
         "                                     set: { if !$0 { pendingDelete = nil } })\n            ) {", "alert args")
s = once(s, "                        library.delete(item)\n",
         "                        withAnimation(.easeInOut(duration: 0.35)) {\n                            library.delete(item)\n                        }\n",
         "animated delete")

# 2) Jimaku search and the track check of all imported videos at once
s = once(s, """        Task { @MainActor in
            while !importQueue.isEmpty {
                let next = importQueue.removeFirst()
                await askOrConvert(next)
            }
            importRunning = false
        }
""", """        let batch = importQueue
        importQueue.removeAll()
        importRunning = false
        for video in batch {
            Task { @MainActor in
                await askOrConvert(video)
            }
        }
""", "parallel import")

# 3) drag a file onto a folder
s = once(s, "                row(item)\n                    .swipeActions(edge: .trailing, allowsFullSwipe: false) {",
         "                row(item)\n                    .modifier(VideoRowDrag(item: item) { urls in library.move(urls, into: item.url) })\n"
         "                    .swipeActions(edge: .trailing, allowsFullSwipe: false) {", "row drag")
s = once(s, "    func createFolder(named name: String) {\n", """    /// Files dropped on a folder: a video goes there with its own subtitle files.
    func move(_ urls: [URL], into target: URL) -> Bool {
        let fm = FileManager.default
        var moved = false
        let siblings = (try? fm.contentsOfDirectory(at: folder, includingPropertiesForKeys: nil)) ?? []
        for url in urls where url.isFileURL && url.deletingLastPathComponent().standardizedFileURL != target.standardizedFileURL {
            var isDir: ObjCBool = false
            guard fm.fileExists(atPath: url.path, isDirectory: &isDir), !isDir.boolValue else { continue }
            var files = [url]
            if VideoLibraryStore.isVideo(url.lastPathComponent) {
                files += siblings.filter { VideoLibraryStore.subtitle($0, belongsTo: url) }
            }
            for file in files {
                let dest = target.appendingPathComponent(file.lastPathComponent)
                guard !fm.fileExists(atPath: dest.path) else { continue }
                if (try? fm.moveItem(at: file, to: dest)) != nil {
                    moved = true
                }
            }
        }
        if moved {
            withAnimation(.easeInOut(duration: 0.35)) {
                reload()
            }
        }
        return moved
    }

    func createFolder(named name: String) {
""", "move")
s = s.rstrip("\n") + """

/// A file row can be dragged (long press), a folder row takes the dropped files.
@available(iOS 16.0, *)
private struct VideoRowDrag: ViewModifier {
    let item: VideoLibraryStore.Item
    let onDrop: ([URL]) -> Bool

    func body(content: Content) -> some View {
        if item.isFolder {
            content.dropDestination(for: URL.self) { urls, _ in
                onDrop(urls)
            }
        } else {
            content.draggable(item.url)
        }
    }
}
"""

# 4) statistics cards: the same height, room for a two-line title
s = once(s, """            Text(title)
                .font(.footnote)
                .foregroundColor(.secondary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(14)
""", """            Text(title)
                .font(.footnote)
                .foregroundColor(.secondary)
                .lineLimit(2)
                .minimumScaleFactor(0.85)
        }
        .frame(maxWidth: .infinity, minHeight: 68, maxHeight: 68, alignment: .topLeading)
        .padding(14)
""", "card height")

hv.write_text(s, encoding="utf-8")
print("v1.53 fixes applied")
