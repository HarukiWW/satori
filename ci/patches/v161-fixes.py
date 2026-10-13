# v1.61: moving videos into folders (drag by file name, "Переместить в…" in the long-press menu; subtitles go along);
# the video opens at the saved position instead of a paused seek (the picture stayed black); the next episode starts
# when the player reports the end; the mining queue of all videos from the video list; the Safari extension counts the
# words imported from Anki as added; diagnostics on their own page at the bottom of the settings.
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

# ---------- moving into folders ----------
s = once(s, """/// A file row can be dragged (long press), a folder row takes the dropped files.
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
""", """/// A file row can be dragged (long press), a folder row takes the dropped files. The file name is dragged, not its
/// URL: a file URL reaches the drop as a copy, or not at all.
@available(iOS 16.0, *)
private struct VideoRowDrag: ViewModifier {
    let item: VideoLibraryStore.Item
    let onDrop: ([String]) -> Bool

    func body(content: Content) -> some View {
        if item.isFolder {
            content.dropDestination(for: String.self) { names, _ in
                onDrop(names)
            }
        } else {
            content.draggable(item.url.lastPathComponent)
        }
    }
}

/// A folder a video can be moved to.
struct VideoMoveTarget: Identifiable {
    let title: String
    let url: URL
    var id: URL { url }
}
""", "drag by name")
s = once(s, """                    .modifier(VideoRowDrag(item: item) { urls in library.move(urls, into: item.url) })
""", """                    .modifier(VideoRowDrag(item: item) { names in
                        let urls = names.filter { !$0.contains("/") }.map { library.folder.appendingPathComponent($0) }
                        return library.move(urls, into: item.url)
                    })
""", "drop call")
s = once(s, """                    .contextMenu {
                        Button(role: .destructive) {
                            pendingDelete = item
                        } label: {
                            Label("Удалить", systemImage: "trash")
                        }
                    }
""", """                    .contextMenu {
                        if !item.isFolder && !moveTargets.isEmpty {
                            Menu {
                                ForEach(moveTargets) { target in
                                    Button(target.title) {
                                        _ = library.move([item.url], into: target.url)
                                    }
                                }
                            } label: {
                                Label("Переместить в…", systemImage: "folder")
                            }
                        }
                        Button(role: .destructive) {
                            pendingDelete = item
                        } label: {
                            Label("Удалить", systemImage: "trash")
                        }
                    }
""", "move menu")
s = once(s, """    @ViewBuilder
    private var nextDestination: some View {
""", """    /// The folders here and, inside a folder, the folder above.
    private var moveTargets: [VideoMoveTarget] {
        var result: [VideoMoveTarget] = []
        if let root = YomikiriMediaSchemeHandler.videosDirectory()?.standardizedFileURL,
           library.folder.standardizedFileURL != root {
            let parent = library.folder.deletingLastPathComponent()
            let name = parent.standardizedFileURL == root ? "Видео" : parent.lastPathComponent
            result.append(VideoMoveTarget(title: "↑ " + name, url: parent))
        }
        for folder in library.items where folder.isFolder {
            result.append(VideoMoveTarget(title: folder.url.lastPathComponent, url: folder.url))
        }
        return result
    }

    @ViewBuilder
    private var nextDestination: some View {
""", "move targets")

# ---------- open at the saved position ----------
s = once(s, "    @State private var options = NativeVideoPlayerScreen.makeOptions()\n",
         "    @State private var options: KSOptions\n", "options state")
s = once(s, """struct NativeVideoPlayerScreen: View {
    let url: URL
""", """struct NativeVideoPlayerScreen: View {
    let url: URL

    /// The player opens the file at the saved position: a seek right after the start ran while the player was not
    /// playing yet, stayed paused and showed no picture until play or another seek.
    init(url: URL) {
        self.url = url
        let options = NativeVideoPlayerScreen.makeOptions()
        options.startPlayTime = NativeVideoPlayerScreen.startTime(for: url)
        _options = State(initialValue: options)
    }

    /// Where the video was stopped last time; 0 near the start or the end.
    static func startTime(for url: URL) -> Double {
        let name = url.lastPathComponent
        let saved = VideoProgress.position(name)
        let length = UserDefaults.standard.double(forKey: "duration." + name)
        guard saved > 10, length <= 0 || saved < length - 30 else { return 0 }
        return saved
    }
""", "player init")
s = once(s, """            if !resumeHandled, duration > 0 {
                // start where the video was stopped last time
                resumeHandled = true
                let saved = VideoProgress.position(url.lastPathComponent)
                if saved > 10, saved < duration - 30 {
                    seek(to: saved)
                }
            }
""", """            if !resumeHandled, duration > 0 {
                // the video opened where it was stopped last time (options.startPlayTime)
                resumeHandled = true
            }
""", "resume")

# ---------- the next episode ----------
s = once(s, """        guard !endHandled, duration > 30, position >= duration - 0.6, !playing, swipeStart == nil else { return }
""", """        // the player stops on its last frame, which can be a second or more before the length of the file
        let ended = coordinator.playerLayer?.state == .playedToTheEnd || (position >= duration - 0.6 && !playing)
        guard !endHandled, duration > 30, ended, swipeStart == nil else { return }
""", "end check")

# ---------- the mining queue of all videos ----------
s = once(s, "    @State private var showKey = false\n",
         "    @State private var showKey = false\n    @State private var showQueue = false\n", "queue state")
s = once(s, """            ToolbarItem(placement: .navigationBarLeading) {
                Button {
                    showKey = true
                } label: {
                    Image(systemName: "key")
                }
            }
        }
        .sheet(isPresented: $showKey) {
            JimakuKeySheet()
        }
""", """            ToolbarItem(placement: .navigationBarLeading) {
                Button {
                    showKey = true
                } label: {
                    Image(systemName: "key")
                }
            }
            ToolbarItem(placement: .navigationBarLeading) {
                Button {
                    showQueue = true
                } label: {
                    Image(systemName: "tray.full")
                }
            }
        }
        .sheet(isPresented: $showKey) {
            JimakuKeySheet()
        }
        .sheet(isPresented: $showQueue) {
            MiningQueueView(video: nil)
        }
""", "queue button")
s = once(s, """    func sendAll(video: String) {
        sending = entries.filter { $0.video == video }
""", """    /// nil: the notes of all videos
    func sendAll(video: String?) {
        sending = entries.filter { video == nil || $0.video == video }
""", "send all")
s = once(s, """struct MiningQueueView: View {
    let video: String
""", """struct MiningQueueView: View {
    /// nil: the queue of all videos
    let video: String?
""", "queue view video")
s = once(s, """                let entries = queue.entries.filter { $0.video == video }
""", """                let entries = queue.entries.filter { video == nil || $0.video == video }
""", "queue view filter")
s = once(s, """                        if !entry.sentence.isEmpty {
                            Text(entry.sentence)
                                .font(.footnote)
                                .foregroundColor(.secondary)
                                .lineLimit(2)
                        }
""", """                        if !entry.sentence.isEmpty {
                            Text(entry.sentence)
                                .font(.footnote)
                                .foregroundColor(.secondary)
                                .lineLimit(2)
                        }
                        if video == nil {
                            Text((entry.video as NSString).deletingPathExtension)
                                .font(.caption2)
                                .foregroundColor(.secondary)
                                .lineLimit(1)
                        }
""", "queue view video name")
s = once(s, """                    .disabled(!queue.sending.isEmpty || !queue.entries.contains { $0.video == video })
""", """                    .disabled(!queue.sending.isEmpty || !queue.entries.contains { video == nil || $0.video == video })
""", "queue view disabled")

# ---------- diagnostics on their own page ----------
s = between(s, """                Button {
                    diag = sharedStorageReport()
                } label: {""", """                Button {
                    showMined = true
                } label: {""", "", "stats diagnostics")
s = once(s, '    @State private var diag = ""\n', "", "stats diag state")
s = between(s, """            Section {
                Text(trail.isEmpty ? "пусто" : trail)""", """            Section {
                NavigationLink(destination: webPage("about", "О программе")) {""", "", "settings diagnostics")
s = once(s, """                NavigationLink(destination: webPage("about", "О программе")) {
                    Text("О программе и лицензии")
                }
            }
        }
        .onAppear {
            config.reload()
            trail = CrashTrail.text()
        }
    }
}
""", """                NavigationLink(destination: webPage("about", "О программе")) {
                    Text("О программе и лицензии")
                }
            }

            Section {
                NavigationLink(destination: DiagnosticsView()) {
                    Text("Диагностика")
                }
            }
        }
        .onAppear {
            config.reload()
        }
    }
}

/// Reports for finding problems: the crash trail and the storage shared with the Safari extension.
struct DiagnosticsView: View {
    @State private var trail = ""
    @State private var storage = ""

    var body: some View {
        List {
            Section {
                Text(trail.isEmpty ? "пусто" : trail)
                    .font(.system(.caption2, design: .monospaced))
                    .textSelection(.enabled)
                Button("Обновить") {
                    trail = CrashTrail.text()
                }
                Button("Скопировать") {
                    UIPasteboard.general.string = trail
                }
                Button("Очистить журнал", role: .destructive) {
                    CrashTrail.clear()
                    trail = ""
                }
            } header: {
                Text("Журнал")
            } footer: {
                Text("Последние шаги приложения. «!!! вылет» — приложение упало; если журнал просто обрывается, iOS закрыла его сама (обычно из-за памяти).")
            }

            Section {
                if !storage.isEmpty {
                    Text(storage)
                        .font(.system(size: 11, design: .monospaced))
                        .textSelection(.enabled)
                    Button("Скопировать") {
                        UIPasteboard.general.string = storage
                    }
                }
                Button("Проверить синхронизацию") {
                    storage = sharedStorageReport()
                }
            } header: {
                Text("Синхронизация с расширением")
            }
        }
        .navigationTitle("Диагностика")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            trail = CrashTrail.text()
        }
    }
}
""", "diagnostics page")
s = once(s, '    @State private var trail = ""\n    @AppStorage("ykUserLevel")', '    @AppStorage("ykUserLevel")', "settings trail state")
hv.write_text(s, encoding="utf-8")

# ---------- Safari: the words imported from Anki are added words too ----------
st = pathlib.Path("src/main/src/extension/stats.ts")
t = st.read_text(encoding="utf-8")
t = once(t, """  /** changed when the statistics are reset (also from the app) */
  resetToken?: string;
}
""", """  /** changed when the statistics are reset (also from the app) */
  resetToken?: string;
  /** words imported from an Anki collection (kept by the app) */
  known?: string[];
}
""", "known field")
t = once(t, """  for (const d of Object.values(data.days)) {
    d.mined.forEach((w) => set.add(w));
  }
  minedCache = { at: now, words: Array.from(set) };
""", """  for (const d of Object.values(data.days)) {
    d.mined.forEach((w) => set.add(w));
  }
  // the app counts them as added too; a deck word can carry HTML and furigana in brackets
  for (const w of data.known ?? []) {
    const word = w
      .replace(/<[^>]*>/g, "")
      .replace(/\\[[^\\]]*\\]/g, "")
      .replace(/\\s+/g, "");
    if (word !== "") set.add(word);
  }
  minedCache = { at: now, words: Array.from(set) };
""", "known words")
st.write_text(t, encoding="utf-8")
print("v1.61 fixes applied")
