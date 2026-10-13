# v1.51: several files at once in the video import (handled one after another, the recognition questions queued);
# a crash trail: key steps after closing a video are written to disk right away, and a crash signal adds a mark,
# shown in Settings > Диагностика.
import pathlib

hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


# ---------- the picker: several files in the video list ----------
s = once(s, """struct DocumentPicker: UIViewControllerRepresentable {
    let onPick: (URL) -> Void
    let onCancel: () -> Void
""", """struct DocumentPicker: UIViewControllerRepresentable {
    let onPick: (URL) -> Void
    let onCancel: () -> Void
    /// several files at once (the video list); every file goes to onPick
    var multiple = false
""", "picker property")
s = once(s, """        let picker = UIDocumentPickerViewController(forOpeningContentTypes: [.item], asCopy: true)
        picker.delegate = context.coordinator
""", """        let picker = UIDocumentPickerViewController(forOpeningContentTypes: [.item], asCopy: true)
        picker.allowsMultipleSelection = multiple
        picker.delegate = context.coordinator
""", "picker multiple")
s = once(s, "            if let url = urls.first { onPick(url) }\n",
         "            for url in urls {\n                onPick(url)\n            }\n", "every picked file")
s = once(s, """            DocumentPicker(onPick: { picked in
                showImporter = false
                library.importVideo(picked)
            }, onCancel: {
                showImporter = false
            })
""", """            DocumentPicker(onPick: { picked in
                showImporter = false
                library.importVideo(picked)
            }, onCancel: {
                showImporter = false
            }, multiple: true)
""", "list picker")

# ---------- imported videos are handled one after another ----------
s = once(s, """        if VideoLibraryStore.isVideo(dest.lastPathComponent) {
            askOrConvert(dest)
        }
""", """        if VideoLibraryStore.isVideo(dest.lastPathComponent) {
            importQueue.append(dest)
            runImportQueue()
        }
""", "enqueue")

a = s.index("    private func askOrConvert(_ video: URL) {")
b = s.index("    func startPending(accurate: Bool) {", a)
lines = s[a:b].split("\n")
assert lines[0] == "    private func askOrConvert(_ video: URL) {"
ti = lines.index("        Task { @MainActor in")
end = max(i for i, l in enumerate(lines) if l == "    }")
assert lines[end - 1] == "        }", "Task end"
body = [l[4:] if l.startswith("            ") else l for l in lines[ti + 1:end - 1]]
func = ["    private func askOrConvert(_ video: URL) async {"] + lines[1:ti] + body + lines[end:]
text = "\n".join(func)
text = once(text, "            pendingChoice = video\n", """            // one question at a time: the others wait
            if pendingChoice == nil {
                pendingChoice = video
            } else {
                choiceQueue.append(video)
            }
""", "choice queue")
s = s[:a] + """    private var importQueue: [URL] = []
    private var importRunning = false
    private var choiceQueue: [URL] = []

    /// Imported videos one after another: Jimaku search and the track check of several files do not run at once.
    private func runImportQueue() {
        guard !importRunning, !importQueue.isEmpty else { return }
        importRunning = true
        Task { @MainActor in
            while !importQueue.isEmpty {
                let next = importQueue.removeFirst()
                await askOrConvert(next)
            }
            importRunning = false
        }
    }

    func skipPending() {
        guard pendingChoice != nil else { return }
        pendingChoice = nil
        showNextChoice()
    }

    private func showNextChoice() {
        guard !choiceQueue.isEmpty else { return }
        let next = choiceQueue.removeFirst()
        // the previous dialog has to close first
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
            self.pendingChoice = next
        }
    }

""" + text + s[b:]

s = once(s, """    func startPending(accurate: Bool) {
        guard let video = pendingChoice else { return }
        pendingChoice = nil
        convertSubtitles(video, accurate: accurate)
    }
""", """    func startPending(accurate: Bool) {
        guard let video = pendingChoice else { return }
        pendingChoice = nil
        convertSubtitles(video, accurate: accurate)
        showNextChoice()
    }
""", "next after start")
s = once(s, "set: { if !$0 { library.pendingChoice = nil } }),", "set: { if !$0 { library.skipPending() } }),", "dialog binding")
s = once(s, 'Button("Не распознавать", role: .cancel) { library.pendingChoice = nil }',
         'Button("Не распознавать", role: .cancel) { library.skipPending() }', "dialog cancel")

# ---------- crash trail ----------
s = once(s, "        .onDisappear {\n            flushWatching()\n            endNowPlaying()\n",
         "        .onDisappear {\n            CrashTrail.mark(\"плеер: закрытие\")\n            flushWatching()\n            endNowPlaying()\n"
         "            CrashTrail.mark(\"плеер: статистика и медиа-меню сброшены\")\n", "player close marks")
s = once(s, "    func reload() {\n        defer { updateCoverage() }\n",
         "    func reload() {\n        CrashTrail.mark(\"список: обновление\")\n        defer { updateCoverage() }\n", "list mark")
s = once(s, """                index = await Task.detached(priority: .utility) { KnownWordsIndex(known) }.value
                knownIndex = (known.count, index)
""", """                CrashTrail.mark("покрытие: индекс знакомых слов (" + String(known.count) + ")")
                index = await Task.detached(priority: .utility) { KnownWordsIndex(known) }.value
                knownIndex = (known.count, index)
                CrashTrail.mark("покрытие: индекс готов")
""", "index marks")
s = once(s, """            for (name, file, stamp) in pending {
                let value = await Task.detached(priority: .utility) {
                    VideoLibraryStore.coverage(of: file, index: index)
                }.value
""", """            for (name, file, stamp) in pending {
                CrashTrail.mark("покрытие: начало " + name)
                let value = await Task.detached(priority: .utility) {
                    VideoLibraryStore.coverage(of: file, index: index)
                }.value
                CrashTrail.mark("покрытие: готово " + name + " = " + (value.map { String($0) } ?? "—"))
""", "coverage marks")

# the trail in the native settings
s = once(s, "    @StateObject private var config = NativeConfig()\n",
         "    @StateObject private var config = NativeConfig()\n    @State private var trail = \"\"\n", "trail state")
s = once(s, """            Section {
                NavigationLink(destination: webPage("about", "О программе")) {
""", """            Section {
                Text(trail.isEmpty ? "пусто" : trail)
                    .font(.system(.caption2, design: .monospaced))
                    .textSelection(.enabled)
                Button("Обновить") {
                    trail = CrashTrail.text()
                }
                Button("Очистить журнал", role: .destructive) {
                    CrashTrail.clear()
                    trail = ""
                }
            } header: {
                Text("Диагностика")
            } footer: {
                Text("Последние шаги приложения. «!!! вылет» — приложение упало; если журнал просто обрывается, iOS закрыла его сама (обычно из-за памяти).")
            }

            Section {
                NavigationLink(destination: webPage("about", "О программе")) {
""", "trail section")
s = once(s, "        .onAppear {\n            config.reload()\n        }\n",
         "        .onAppear {\n            config.reload()\n            trail = CrashTrail.text()\n        }\n", "trail on appear")

s = s.rstrip("\n") + '''

private var crashTrailFD: Int32 = -1

/// Steps written to disk right away, so they survive a crash; a crash signal adds a mark.
enum CrashTrail {
    private static let url = FileManager.default.urls(for: .libraryDirectory, in: .userDomainMask)[0]
        .appendingPathComponent("crash-trail.txt")
    private static let formatter: DateFormatter = {
        let f = DateFormatter()
        f.dateFormat = "dd.MM HH:mm:ss.SSS"
        return f
    }()
    private static let installed: Bool = {
        // the trail keeps its last part only
        if let data = try? Data(contentsOf: url), data.count > 64_000 {
            try? data.suffix(32_000).write(to: url)
        }
        crashTrailFD = open(url.path, O_WRONLY | O_APPEND | O_CREAT, 0o644)
        for sig in [SIGABRT, SIGSEGV, SIGBUS, SIGILL, SIGTRAP, SIGFPE] {
            signal(sig) { number in
                let mark: StaticString = "!!! вылет (сигнал)\\n"
                _ = write(crashTrailFD, mark.utf8Start, mark.utf8CodeUnitCount)
                signal(number, SIG_DFL)
                raise(number)
            }
        }
        return true
    }()

    static func mark(_ text: String) {
        guard installed, crashTrailFD >= 0 else { return }
        let line = formatter.string(from: Date()) + " " + text + "\\n"
        line.withCString { pointer in
            _ = write(crashTrailFD, pointer, strlen(pointer))
        }
    }

    static func text() -> String {
        guard let content = try? String(contentsOf: url, encoding: .utf8) else { return "" }
        return content.split(separator: "\\n").suffix(40).joined(separator: "\\n")
    }

    static func clear() {
        if crashTrailFD >= 0 {
            ftruncate(crashTrailFD, 0)
        } else {
            try? FileManager.default.removeItem(at: url)
        }
    }
}
'''
hv.write_text(s, encoding="utf-8")
print("v1.51 fixes applied")
