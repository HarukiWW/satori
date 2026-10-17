# v1.95: the folder of the backups can be chosen. Satori declared the decks of Anki (.apkg, .colpkg) as its document
# types (for "Поделиться → Satori", 1.77); the system picker adds the document types of the app to the folder it is
# asked for, and with a file type mixed in it does not give a folder at all: «Открыть» did nothing in every picker.
# The declaration goes: decks are no longer offered to Satori in "Поделиться"; they are imported from the settings
# (a file, a backup, or the folder of the backups).
import pathlib
import plistlib


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


app = pathlib.Path("src/safari/iOS (App)")
plist = app / "Info.plist"
info = plistlib.loads(plist.read_bytes())
assert "CFBundleDocumentTypes" in info, "document types of 1.77 not found"
del info["CFBundleDocumentTypes"]
plist.write_bytes(plistlib.dumps(info))

hv = app / "HelpView.swift"
s = hv.read_text(encoding="utf-8")
# a folder first, should a picker ever give files too
s = once(s, '''        func documentPicker(_ controller: UIDocumentPickerViewController, didPickDocumentsAt urls: [URL]) {
            if let url = urls.first {
                onPick(url)
            }
            FolderPick.delegate = nil
        }
''', '''        func documentPicker(_ controller: UIDocumentPickerViewController, didPickDocumentsAt urls: [URL]) {
            let folder = urls.first { (try? $0.resourceValues(forKeys: [.isDirectoryKey]))?.isDirectory == true }
            if let url = folder ?? urls.first {
                onPick(url)
            }
            FolderPick.delegate = nil
        }
''', "folder first")
hv.write_text(s, encoding="utf-8")

page = pathlib.Path("src/main/src/components/options/groups/GroupAnkiImport.svelte")
t = page.read_text(encoding="utf-8")
t = once(t, '''    В AnkiMobile экспортируйте колоду (.colpkg или .apkg с расписанием) и в «Поделиться» выберите Satori. В покрытии
    учитываются зрелые карточки (интервал от 21 дня).
''', '''    Колода (.colpkg или .apkg с расписанием) или бэкап AnkiMobile. Без экспорта — папка бэкапов в Настройках → Anki:
    тогда слова обновляются сами. В покрытии учитываются зрелые карточки (интервал от 21 дня).
''', "import note")
page.write_text(t, encoding="utf-8")
print("v1.95 folder applied")
