# v1.97: fixes.
# - The check mark after ⊕ comes for the entry that was tapped, whatever form the fields of the note keep (the word of
#   the note could be 忠告する for the entry 忠告, or another form of the template): every form of the entry counts
#   as added once the note is added or queued.
# - The lists of unknown words follow the mining queue: a word queued from the dictionary over the list leaves the
#   list at once, with an animation (it stayed until another word was opened, then vanished at once).
# - The backups of AnkiMobile through Shortcuts: the action «Обновить знакомые слова из бэкапа Anki» takes a backup
#   file (an automation can hand it the newest file of Anki/Backups whenever AnkiMobile closes); Satori reads it when
#   it is open. The picker's «Открыть» does nothing for a folder one went into (iOS 26 seems to take only a folder
#   marked in "Выбрать" mode): the settings say how to mark it. The two ways the picker closes without a folder now
#   say which one it was.
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


here = pathlib.Path(__file__).resolve().parent

# ---------- web: the check mark of the tapped entry ----------
web = pathlib.Path("src/main/src/components")
p = web / "anki/addNoteNow.ts"
t = p.read_text(encoding="utf-8")
t = once(t, '''/** Words of the notes added (or put in a queue) in this session, as the statistics keep them. */
export const addedWords = writable(new Set<string>());
''', '''/** Words of the notes added (or put in a queue) in this session, as the statistics keep them. */
export const addedWords = writable(new Set<string>());

/** whether the last add ended with the note added or queued (not with an error) */
export const lastAddOk = writable(false);
''', "last add store")
t = once(t, '''  if (adding) return;
  adding = true;
  addingNote.set(true);
''', '''  if (adding) return;
  adding = true;
  lastAddOk.set(false);
  addingNote.set(true);
''', "last add reset")
t = once(t, '''    const added = await AnkiApi.addNote(note as AnkiNote);
    const word = wordFromNoteLite(note as AnkiNote);
''', '''    const added = await AnkiApi.addNote(note as AnkiNote);
    lastAddOk.set(true);
    const word = wordFromNoteLite(note as AnkiNote);
''', "last add ok")
p.write_text(t, encoding="utf-8")

p = web / "dictionary/DicEntryView.svelte"
t = p.read_text(encoding="utf-8")
t = once(t, '''  import { addedWords, addingNote } from "components/anki/addNoteNow";
''', '''  import { addedWords, addingNote, lastAddOk } from "components/anki/addNoteNow";
''', "entry imports")
t = once(t, '''  $: added = mined && isAdded(entry, $addedWords);
  // the add has finished (added, queued or failed): the check mark or ⊕ again
  $: if (pressed && !$addingNote) pressed = false;
''', '''  $: added = mined && isAdded(entry, $addedWords);
  // the add has finished (added, queued or failed): the check mark or ⊕ again; an added note marks every form of
  // the tapped entry, whatever form its fields keep
  $: if (pressed && !$addingNote) {
    pressed = false;
    if ($lastAddOk && entry.type === "word") {
      const forms = entry.kanjis.map((k) => k.kanji);
      if (forms.length === 0) forms.push(...entry.readings.map((r) => r.reading));
      forms.push(getMainForm(entry));
      addedWords.update((words) => new Set([...words, ...forms]));
    }
  }
''', "entry marks forms")
p.write_text(t, encoding="utf-8")

# ---------- the lists follow the queue ----------
hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")
s = within(s, "struct UnknownWordsView: View {", "\nstruct ", '''    /// changed by a swipe: the list is read again
    @State private var marks = 0
''', '''    /// changed by a swipe: the list is read again
    @State private var marks = 0
    /// a word queued from the dictionary over the list leaves it at once
    @ObservedObject private var queue = MiningQueue.shared
''', "series list queue")
s = within(s, "struct UnknownWordsView: View {", "\nstruct ", '''            .navigationTitle(video.deletingPathExtension().lastPathComponent)
''', '''            .navigationTitle(video.deletingPathExtension().lastPathComponent)
            .animation(.default, value: queue.entries.count)
            .animation(.default, value: marks)
''', "series list animation")
s = within(s, "struct CatalogUnknownView: View {", "\nstruct ", '''    /// changed by a swipe: the list is read again
    @State private var marks = 0
''', '''    /// changed by a swipe: the list is read again
    @State private var marks = 0
    /// a word queued from the dictionary over the list leaves it at once
    @ObservedObject private var queue = MiningQueue.shared
''', "catalog list queue")
s = within(s, "struct CatalogUnknownView: View {", "\nstruct ", '''        .navigationTitle("Незнакомые слова: " + String(words.count))
''', '''        .navigationTitle("Незнакомые слова: " + String(words.count))
        .animation(.default, value: queue.entries.count)
        .animation(.default, value: marks)
''', "catalog list animation")

# ---------- the picker: which way it ended ----------
s = once(s, '''                FolderPick.present({ url in
                    sync.choose(url)
                }, onCancel: {
                    sync.say("Окно закрылось без выбора папки")
                })
''', '''                FolderPick.present({ url in
                    sync.choose(url)
                }, onCancel: { swiped in
                    sync.say(swiped ? "Окно смахнули: папка не выбрана" : "Окно закрыто кнопкой «Отмена»: папка не выбрана")
                })
''', "row cancel kinds")
s = once(s, '''    static func present(_ onPick: @escaping (URL) -> Void, onCancel: @escaping () -> Void = {}) {
''', '''    static func present(_ onPick: @escaping (URL) -> Void, onCancel: @escaping (Bool) -> Void = { _ in }) {
''', "present cancel kind")
s = once(s, '''        let onPick: (URL) -> Void
        let onCancel: () -> Void

        init(_ onPick: @escaping (URL) -> Void, _ onCancel: @escaping () -> Void) {
            self.onPick = onPick
            self.onCancel = onCancel
        }

        func presentationControllerDidDismiss(_ presentationController: UIPresentationController) {
            onCancel()
            FolderPick.delegate = nil
        }
''', '''        let onPick: (URL) -> Void
        /// true: closed with a swipe; false: the picker itself said cancel
        let onCancel: (Bool) -> Void

        init(_ onPick: @escaping (URL) -> Void, _ onCancel: @escaping (Bool) -> Void) {
            self.onPick = onPick
            self.onCancel = onCancel
        }

        func presentationControllerDidDismiss(_ presentationController: UIPresentationController) {
            onCancel(true)
            FolderPick.delegate = nil
        }
''', "delegate cancel kind")
s = once(s, '''        func documentPickerWasCancelled(_ controller: UIDocumentPickerViewController) {
            onCancel()
            FolderPick.delegate = nil
        }
    }
}
''', '''        func documentPickerWasCancelled(_ controller: UIDocumentPickerViewController) {
            onCancel(false)
            FolderPick.delegate = nil
        }
    }
}
''', "picker cancel kind")

# ---------- a backup from Shortcuts ----------
s = once(s, "import Libswscale\n", "import Libswscale\nimport AppIntents\n", "app intents import")
s = once(s, '''    /// The import page is done with the backup.
    func finished(ok: Bool, message: String) {
        importing = false
        DeckInbox.fromBackup = false
''', '''    private let droppedKey = "ykAnkiBackupDropped"
    private let droppedReadKey = "ykAnkiBackupDroppedRead"
    private var droppedName: String? = nil

    /// A backup handed over by a shortcut: kept where the import page reads it; read now when Satori is open, else
    /// when it opens. The same backup again is not read twice.
    func drop(_ data: Data, name: String) -> String {
        guard ["colpkg", "apkg"].contains((name as NSString).pathExtension.lowercased()) else {
            return "Это не бэкап Anki (.colpkg)"
        }
        if name == UserDefaults.standard.string(forKey: droppedReadKey) {
            return "Бэкап «" + name + "» уже прочитан"
        }
        guard !importing else {
            return "Satori читает другой бэкап, передайте этот позже"
        }
        guard DeckInbox.keep(data, name: name) else {
            return "Не удалось сохранить бэкап"
        }
        UserDefaults.standard.set(name, forKey: droppedKey)
        if UIApplication.shared.applicationState == .active {
            readDropped()
        }
        return "Бэкап «" + name + "» передан в Satori"
    }

    /// The backup a shortcut left, when there is one and nothing else is being read.
    private func readDropped() {
        guard !importing, let name = UserDefaults.standard.string(forKey: droppedKey), DeckInbox.pending != nil else { return }
        UserDefaults.standard.removeObject(forKey: droppedKey)
        DeckInbox.fromBackup = true
        droppedName = name
        pendingDate = nil
        importing = true
        status = "Читаю бэкап из команды «" + name + "»…"
    }

    /// The import page is done with the backup.
    func finished(ok: Bool, message: String) {
        if ok, let droppedName {
            UserDefaults.standard.set(droppedName, forKey: droppedReadKey)
        }
        droppedName = nil
        importing = false
        DeckInbox.fromBackup = false
''', "dropped backup")
s = once(s, '''    func check(force: Bool = false, chosen: URL? = nil) {
        guard !importing, let folder = chosen ?? folder() else { return }
''', '''    func check(force: Bool = false, chosen: URL? = nil) {
        // a backup a shortcut left comes first
        if !importing, chosen == nil, UserDefaults.standard.string(forKey: droppedKey) != nil {
            readDropped()
            return
        }
        guard !importing, let folder = chosen ?? folder() else { return }
''', "check dropped first")
s = once(s, '''    static var pending: URL? {
        (try? FileManager.default.contentsOfDirectory(at: folder, includingPropertiesForKeys: nil))?.first
    }
''', '''    static var pending: URL? {
        (try? FileManager.default.contentsOfDirectory(at: folder, includingPropertiesForKeys: nil))?.first
    }

    /// A deck given as data (a shortcut): the one waiting for the import page.
    static func keep(_ data: Data, name: String) -> Bool {
        let manager = FileManager.default
        try? manager.removeItem(at: folder)
        try? manager.createDirectory(at: folder, withIntermediateDirectories: true)
        return (try? data.write(to: folder.appendingPathComponent(name))) != nil
    }
''', "inbox keep")
s = once(s, '''        var text = "Выберите «На iPhone → Anki» или Backups в ней. Когда AnkiMobile сделает новый бэкап (при синхронизации), "
            + "зрелые карточки обновятся сами при открытии Satori."
''', '''        var text = "В окне выбора на уровне «Anki» нажмите «…» → «Выбрать», отметьте Backups и нажмите «Открыть» "
            + "(в iOS 26 «Открыть» берёт отмеченную папку, а не ту, в которую вы зашли). Если не выходит: в «Командах» "
            + "автоматизация «Приложение AnkiMobile закрыто» → «Получить содержимое папки» (Anki/Backups) → «Сортировать» "
            + "по дате создания, сначала новые → «Получить объект из списка» → действие Satori «Обновить знакомые слова из "
            + "бэкапа Anki». Тогда слова обновляются сами."
''', "row footer")
s = s.rstrip("\n") + "\n" + (here / "v197-intent.swift").read_text(encoding="utf-8")
hv.write_text(s, encoding="utf-8")
print("v1.97 fixes applied")
