# v1.98: the folder of the backups.
# - AnkiMobile keeps its backups per profile now («Backups for ユーザー 1»; the old «Backups» is not filled any more):
#   the newest backup of the chosen folder and of all its folders named «Backups…» is read.
# - «Другой способ выбора папки»: the same system picker made by the older API (documentTypes "public.folder", mode
#   .open), in case iOS 26 gives the folder only through that path.
# - The live background stops while the picker is open (its frames ran under the picker all the time).
# - The settings say how the folder is chosen without the wrong hint of 1.97 (the picker has no «Выбрать» mode).
import pathlib


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")

# ---------- the newest backup of all «Backups…» folders ----------
s = once(s, '''        // the folder «Anki» itself: its backups are in Backups
        var files = list(folder.appendingPathComponent("Backups", isDirectory: true)).files
        var problem: String? = nil
        if !files.contains(where: { $0.pathExtension.lowercased() == "colpkg" }) {
            let outer = list(folder)
            files = outer.files
            problem = outer.problem
        }
''', '''        // the chosen folder and its folders of backups: «Backups», «Backups for <profile>» (AnkiMobile keeps one per
        // profile); the newest backup of them all is read
        let outer = list(folder)
        var files = outer.files
        let problem: String? = outer.problem
        for sub in outer.files where sub.lastPathComponent.lowercased().hasPrefix("backups") {
            files += list(sub).files
        }
''', "backup folders")

# ---------- the older picker, the background stops ----------
s = once(s, '''    static func present(_ onPick: @escaping (URL) -> Void, onCancel: @escaping (Bool) -> Void = { _ in }) {
''', '''    static func present(_ onPick: @escaping (URL) -> Void, onCancel: @escaping (Bool) -> Void = { _ in },
                        legacy: Bool = false) {
''', "present legacy")
s = once(s, '''        let picker = UIDocumentPickerViewController(forOpeningContentTypes: [.folder], asCopy: false)
        picker.allowsMultipleSelection = false
        let handler = Delegate(onPick, onCancel)
''', '''        // the older API: the same picker made another way (deprecated, still there)
        let picker = legacy
            ? UIDocumentPickerViewController(documentTypes: ["public.folder"], in: .open)
            : UIDocumentPickerViewController(forOpeningContentTypes: [.folder], asCopy: false)
        picker.allowsMultipleSelection = false
        BackdropPause.shared.active = true
        let handler = Delegate(onPick, onCancel)
''', "picker legacy")
s = once(s, '''        func presentationControllerDidDismiss(_ presentationController: UIPresentationController) {
            onCancel(true)
            FolderPick.delegate = nil
        }
''', '''        func presentationControllerDidDismiss(_ presentationController: UIPresentationController) {
            BackdropPause.shared.active = false
            onCancel(true)
            FolderPick.delegate = nil
        }
''', "dismiss resumes")
s = once(s, '''        func documentPicker(_ controller: UIDocumentPickerViewController, didPickDocumentsAt urls: [URL]) {
            let folder = urls.first { (try? $0.resourceValues(forKeys: [.isDirectoryKey]))?.isDirectory == true }
''', '''        func documentPicker(_ controller: UIDocumentPickerViewController, didPickDocumentsAt urls: [URL]) {
            BackdropPause.shared.active = false
            let folder = urls.first { (try? $0.resourceValues(forKeys: [.isDirectoryKey]))?.isDirectory == true }
''', "pick resumes")
s = once(s, '''        func documentPickerWasCancelled(_ controller: UIDocumentPickerViewController) {
            onCancel(false)
            FolderPick.delegate = nil
        }
''', '''        func documentPickerWasCancelled(_ controller: UIDocumentPickerViewController) {
            BackdropPause.shared.active = false
            onCancel(false)
            FolderPick.delegate = nil
        }
''', "cancel resumes")
s = once(s, '''    @State private var motion = BackdropMotion()
''', '''    @State private var motion = BackdropMotion()
    /// stopped while a system picker is open over the app
    @ObservedObject private var pause = BackdropPause.shared
''', "backdrop pause state")
s = once(s, '''                TimelineView(.animation(minimumInterval: 1.0 / 30, paused: reduceMotion || !visible)) { context in
''', '''                TimelineView(.animation(minimumInterval: 1.0 / 30, paused: reduceMotion || !visible || pause.active)) { context in
''', "backdrop paused")

# ---------- the row ----------
s = once(s, '''                sync.say("Откройте папку Backups (или «Anki») и нажмите «Открыть»…")
                FolderPick.present({ url in
                    sync.choose(url)
                }, onCancel: { swiped in
                    sync.say(swiped ? "Окно смахнули: папка не выбрана" : "Окно закрыто кнопкой «Отмена»: папка не выбрана")
                })
            }
''', '''                sync.say("Зайдите в папку «Anki» (или в папку с бэкапами) и нажмите «Открыть»…")
                FolderPick.present({ url in
                    sync.choose(url)
                }, onCancel: { swiped in
                    sync.say(swiped ? "Окно смахнули: папка не выбрана" : "Окно закрыто кнопкой «Отмена»: папка не выбрана")
                })
            }
            Button("Другой способ выбора папки") {
                sync.say("Другой способ: зайдите в папку «Anki» и нажмите «Открыть»…")
                FolderPick.present({ url in
                    sync.choose(url)
                }, onCancel: { swiped in
                    sync.say(swiped ? "Окно смахнули: папка не выбрана" : "Окно закрыто кнопкой «Отмена»: папка не выбрана")
                }, legacy: true)
            }
''', "row legacy button")
s = once(s, '''        var text = "В окне выбора на уровне «Anki» нажмите «…» → «Выбрать», отметьте Backups и нажмите «Открыть» "
            + "(в iOS 26 «Открыть» берёт отмеченную папку, а не ту, в которую вы зашли). Если не выходит: в «Командах» "
            + "автоматизация «Приложение AnkiMobile закрыто» → «Получить содержимое папки» (Anki/Backups) → «Сортировать» "
            + "по дате создания, сначала новые → «Получить объект из списка» → действие Satori «Обновить знакомые слова из "
            + "бэкапа Anki». Тогда слова обновляются сами."
''', '''        var text = "Выберите папку «Anki» (или папку с бэкапами в ней): Satori читает самый свежий бэкап из «Backups» и "
            + "«Backups for …», а потом новые — сам, при открытии. Для проверки можно выбрать «На iPhone → Satori»: если и "
            + "она не выбирается, iOS не даёт Satori папки вообще."
''', "row footer")

s = s.rstrip("\n") + '''

/// The live background stops while a system picker is open over the app.
final class BackdropPause: ObservableObject {
    static let shared = BackdropPause()
    @Published var active = false
}
'''
hv.write_text(s, encoding="utf-8")
print("v1.98 backups applied")
