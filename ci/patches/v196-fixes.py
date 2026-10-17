# v1.96: fixes.
# - The check mark after ⊕ and the "Anki" badge: a word whose first written form is rare goes into the note and the
#   queue in its main form, in kana (ありがとう); the dictionary looked for its kanji forms only (有難う), so the mark
#   did not come. The main form counts too.
# - The lists of unknown words (a series, a title, a novel) color the words of the frequency highlight band, as the
#   subtitles and the reader do.
# - The folder of the backups: every step says what happened (the picker gave a folder or was closed without one,
#   access, the number of files, the error), the bookmark is made as in Apple's sample (.minimalBookmark), and the
#   folder is read right away with the access the picker gave.
import pathlib


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


def within(text, start, end, old, new, label):
    """Replace `old` (exactly once) between the first `start` and the next `end` after it."""
    a = text.index(start)
    b = text.index(end, a + len(start))
    part = text[a:b]
    assert part.count(old) == 1, "pattern not found once in region: " + label
    return text[:a] + part.replace(old, new) + text[b:]


# ---------- web: the main form counts ----------
web = pathlib.Path("src/main/src/components/dictionary")
p = web / "DicEntryView.svelte"
t = p.read_text(encoding="utf-8")
t = once(t, '''    if (mined.exact.length > 0 || (mined.queued ?? []).length > 0) return true;
    const forms = entry.kanjis.map((k) => k.kanji);
    if (forms.length === 0) forms.push(...entry.readings.map((r) => r.reading));
    return forms.some((form) => words.has(form));
''', '''    if (mined.exact.length > 0 || (mined.queued ?? []).length > 0) return true;
    const forms = entry.kanjis.map((k) => k.kanji);
    if (forms.length === 0) forms.push(...entry.readings.map((r) => r.reading));
    // the note keeps the main form: in kana when the first written form is rare (ありがとう)
    forms.push(getMainForm(entry));
    return forms.some((form) => words.has(form));
''', "added main form")
p.write_text(t, encoding="utf-8")

p = web / "Badges.svelte"
t = p.read_text(encoding="utf-8")
t = once(t, '''    const forms = entry.kanjis.map((k) => k.kanji);
    if (forms.length === 0) forms.push(...entry.readings.map((r) => r.reading));
    const id = ++minedRequestId;
''', '''    const forms = entry.kanjis.map((k) => k.kanji);
    if (forms.length === 0) forms.push(...entry.readings.map((r) => r.reading));
    // the note keeps the main form: in kana when the first written form is rare (ありがとう)
    const main = getMainForm(entry);
    if (!forms.includes(main)) forms.push(main);
    const id = ++minedRequestId;
''', "badges main form")
p.write_text(t, encoding="utf-8")

hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")

# ---------- the lists: the highlight band ----------
s = once(s, '''    /// Lists of unknown words without the words that are in Anki already''', '''    /// The highlight color of a word of a list (the band of the subtitles); nil out of the band or with the highlight off.
    static func listColor(_ word: String, reading: String) -> Color? {
        let (settings, _) = cachedSettings()
        guard settings.enabled, settings.freq else { return nil }
        let kana = hiragana(reading)
        guard let found = rank(base: word, reading: kana, dict: settings.dict, text: word)
                ?? rank(base: word, reading: "", dict: settings.dict, text: word),
              found >= settings.lo, found <= settings.hi else { return nil }
        return color(hex: settings.color)
    }

    /// Lists of unknown words without the words that are in Anki already''', "list color")
s = within(s, "struct UnknownWordsView: View {", "\nstruct ", '''                                        Text(word.word)
                                            .font(.system(size: 20))
                                            .foregroundColor(.primary)
''', '''                                        Text(word.word)
                                            .font(.system(size: 20))
                                            .foregroundColor(HighlightData.listColor(word.word, reading: word.reading) ?? .primary)
''', "series list color")
s = within(s, "struct CatalogUnknownView: View {", "\nstruct ", '''                                Text(word.word)
                                    .font(.system(size: 20))
                                    .foregroundColor(.primary)
''', '''                                Text(word.word)
                                    .font(.system(size: 20))
                                    .foregroundColor(HighlightData.listColor(word.word, reading: word.kana) ?? .primary)
''', "catalog list color")

# ---------- the folder of the backups ----------
s = once(s, '''        guard let data = try? folder.bookmarkData() else {
            status = "Папку не удалось запомнить"
            return
        }
        UserDefaults.standard.set(data, forKey: bookmarkKey)
        UserDefaults.standard.removeObject(forKey: doneKey)
        status = "Папка «" + folder.lastPathComponent + "» выбрана"
        objectWillChange.send()
        check()
    }
''', '''        let data: Data
        do {
            // as in Apple's sample "Providing access to directories"
            data = try folder.bookmarkData(options: .minimalBookmark, includingResourceValuesForKeys: nil, relativeTo: nil)
        } catch {
            status = "Папка «" + folder.lastPathComponent + "» получена, но не запомнилась: " + error.localizedDescription
            return
        }
        UserDefaults.standard.set(data, forKey: bookmarkKey)
        UserDefaults.standard.removeObject(forKey: doneKey)
        status = "Папка «" + folder.lastPathComponent + "» выбрана" + (access ? "" : " (без доступа)")
        objectWillChange.send()
        // read now, with the access the picker gave
        check(force: true, chosen: folder)
    }

    /// A step of the choice the row shows (the picker opened, closed without a folder).
    func say(_ text: String) {
        status = text
    }
''', "choose folder")
s = once(s, '''    func check(force: Bool = false) {
        guard !importing, let folder = folder() else { return }
''', '''    func check(force: Bool = false, chosen: URL? = nil) {
        guard !importing, let folder = chosen ?? folder() else { return }
''', "check chosen")
s = once(s, '''        let keys: [URLResourceKey] = [.contentModificationDateKey]
        // the folder «Anki» itself: its backups are in Backups
        var files = (try? FileManager.default.contentsOfDirectory(at: folder.appendingPathComponent("Backups", isDirectory: true),
                                                                  includingPropertiesForKeys: keys)) ?? []
        if !files.contains(where: { $0.pathExtension.lowercased() == "colpkg" }) {
            files = (try? FileManager.default.contentsOfDirectory(at: folder, includingPropertiesForKeys: keys)) ?? []
        }
        func date(_ file: URL) -> Date {
            (try? file.resourceValues(forKeys: [.contentModificationDateKey]))?.contentModificationDate ?? .distantPast
        }
        guard let newest = files.filter({ $0.pathExtension.lowercased() == "colpkg" }).max(by: { date($0) < date($1) }) else {
            status = access ? "В папке нет бэкапов (.colpkg)" : "Нет доступа к папке: выберите её снова"
            return
        }
''', '''        let keys: [URLResourceKey] = [.contentModificationDateKey]
        func list(_ dir: URL) -> (files: [URL], problem: String?) {
            do {
                return (try FileManager.default.contentsOfDirectory(at: dir, includingPropertiesForKeys: keys), nil)
            } catch {
                return ([], error.localizedDescription)
            }
        }
        // the folder «Anki» itself: its backups are in Backups
        var files = list(folder.appendingPathComponent("Backups", isDirectory: true)).files
        var problem: String? = nil
        if !files.contains(where: { $0.pathExtension.lowercased() == "colpkg" }) {
            let outer = list(folder)
            files = outer.files
            problem = outer.problem
        }
        func date(_ file: URL) -> Date {
            (try? file.resourceValues(forKeys: [.contentModificationDateKey]))?.contentModificationDate ?? .distantPast
        }
        guard let newest = files.filter({ $0.pathExtension.lowercased() == "colpkg" }).max(by: { date($0) < date($1) }) else {
            let place = "«" + folder.lastPathComponent + "»"
            if let problem {
                status = "Папку " + place + " не прочитать" + (access ? "" : " (нет доступа)") + ": " + problem
            } else {
                status = "В " + place + " нет бэкапов (.colpkg), файлов: " + String(files.count)
            }
            return
        }
''', "check listing")
s = once(s, '''        guard DeckInbox.receive(newest) else {
            status = "Не удалось скопировать бэкап"
            return
        }
''', '''        guard DeckInbox.receive(newest) else {
            status = "Не удалось скопировать бэкап «" + newest.lastPathComponent + "»"
            return
        }
''', "check copy")

s = once(s, '''                FolderPick.present { url in
                    sync.choose(url)
                }
''', '''                sync.say("Откройте папку Backups (или «Anki») и нажмите «Открыть»…")
                FolderPick.present({ url in
                    sync.choose(url)
                }, onCancel: {
                    sync.say("Окно закрылось без выбора папки")
                })
''', "row present")

s = once(s, '''    @MainActor
    static func present(_ onPick: @escaping (URL) -> Void) {
''', '''    @MainActor
    static func present(_ onPick: @escaping (URL) -> Void, onCancel: @escaping () -> Void = {}) {
''', "present cancel")
s = once(s, '''        let handler = Delegate(onPick)
        delegate = handler
        picker.delegate = handler
        top.present(picker, animated: true)
    }

    final class Delegate: NSObject, UIDocumentPickerDelegate {
        let onPick: (URL) -> Void

        init(_ onPick: @escaping (URL) -> Void) {
            self.onPick = onPick
        }
''', '''        let handler = Delegate(onPick, onCancel)
        delegate = handler
        picker.delegate = handler
        top.present(picker, animated: true)
        // closed with a swipe: no callback of the picker comes then
        picker.presentationController?.delegate = handler
    }

    final class Delegate: NSObject, UIDocumentPickerDelegate, UIAdaptivePresentationControllerDelegate {
        let onPick: (URL) -> Void
        let onCancel: () -> Void

        init(_ onPick: @escaping (URL) -> Void, _ onCancel: @escaping () -> Void) {
            self.onPick = onPick
            self.onCancel = onCancel
        }

        func presentationControllerDidDismiss(_ presentationController: UIPresentationController) {
            onCancel()
            FolderPick.delegate = nil
        }
''', "picker delegate")
s = once(s, '''        func documentPickerWasCancelled(_ controller: UIDocumentPickerViewController) {
            FolderPick.delegate = nil
        }
    }
}
''', '''        func documentPickerWasCancelled(_ controller: UIDocumentPickerViewController) {
            onCancel()
            FolderPick.delegate = nil
        }
    }
}
''', "picker cancel")
hv.write_text(s, encoding="utf-8")
print("v1.96 fixes applied")
