# v1.92: the folder of the backups.
# - The folder picker is shown by UIKit itself over the app (both a SwiftUI file importer and a picker inside a
#   SwiftUI sheet, from a row of the settings form, ignored «Открыть»).
# - «Выбрать бэкап файлом»: one backup chosen as a file (the picker the video import uses) is read the same way, as a
#   whole collection: its mature cards replace the mature list.
import pathlib


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")

s = once(s, '''    @ObservedObject private var sync = AnkiBackupSync.shared
    @State private var picking = false
''', '''    @ObservedObject private var sync = AnkiBackupSync.shared
    @State private var pickingFile = false
''', "row state")
s = once(s, '''            Button(sync.connected ? "Папка бэкапов AnkiMobile: выбрана" : "Папка бэкапов AnkiMobile…") {
                picking = true
            }
            .sheet(isPresented: $picking) {
                FolderPicker(onPick: { url in
                    picking = false
                    sync.choose(url)
                }, onCancel: {
                    picking = false
                })
                .ignoresSafeArea()
            }
''', '''            Button(sync.connected ? "Папка бэкапов AnkiMobile: выбрана" : "Папка бэкапов AnkiMobile…") {
                FolderPick.present { url in
                    sync.choose(url)
                }
            }
            Button("Выбрать бэкап файлом") {
                pickingFile = true
            }
            .disabled(sync.importing)
            .sheet(isPresented: $pickingFile) {
                DocumentPicker(onPick: { url in
                    pickingFile = false
                    sync.read(url)
                }, onCancel: {
                    pickingFile = false
                })
                .ignoresSafeArea()
            }
''', "row buttons")
s = once(s, '''    /// The import page is done with the backup.
    func finished(ok: Bool, message: String) {
''', '''    /// One backup chosen as a file (a copy): read once like the newest one of the folder.
    func read(_ file: URL) {
        guard !importing else { return }
        guard DeckInbox.accepts(file), DeckInbox.receive(file) else {
            status = "Это не бэкап Anki (.colpkg)"
            return
        }
        DeckInbox.fromBackup = true
        pendingDate = nil
        importing = true
        status = "Читаю бэкап «" + file.lastPathComponent + "»…"
    }

    /// The import page is done with the backup.
    func finished(ok: Bool, message: String) {
''', "read one backup")

# the folder picker of 1.90 goes; the one shown by UIKit takes its place
start = s.index("\n/// The system picker of a folder: the folder stays where it is (its URL is security-scoped).\nstruct FolderPicker")
# it is the last thing of the file (1.90 appended it)
assert s[start:].count("\nstruct ") == 1 and "\nenum " not in s[start:] and "\nextension " not in s[start:]
s = s[:start] + "\n"
s = s.rstrip("\n") + '''

/// The system picker of a folder, shown by UIKit over the app: the folder stays where it is (a security-scoped URL).
enum FolderPick {
    /// the picker does not keep its delegate
    private static var delegate: Delegate?

    @MainActor
    static func present(_ onPick: @escaping (URL) -> Void) {
        let windows = UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }.flatMap { $0.windows }
        guard var top = (windows.first { $0.isKeyWindow } ?? windows.first)?.rootViewController else { return }
        while let shown = top.presentedViewController {
            top = shown
        }
        let picker = UIDocumentPickerViewController(forOpeningContentTypes: [.folder], asCopy: false)
        picker.allowsMultipleSelection = false
        let handler = Delegate(onPick)
        delegate = handler
        picker.delegate = handler
        top.present(picker, animated: true)
    }

    final class Delegate: NSObject, UIDocumentPickerDelegate {
        let onPick: (URL) -> Void

        init(_ onPick: @escaping (URL) -> Void) {
            self.onPick = onPick
        }

        func documentPicker(_ controller: UIDocumentPickerViewController, didPickDocumentsAt urls: [URL]) {
            if let url = urls.first {
                onPick(url)
            }
            FolderPick.delegate = nil
        }

        func documentPickerWasCancelled(_ controller: UIDocumentPickerViewController) {
            FolderPick.delegate = nil
        }
    }
}
'''
hv.write_text(s, encoding="utf-8")
print("v1.92 backups applied")
