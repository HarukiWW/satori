# v2.03: «Подпись приложения» in Настройки → Anki.
# - The check of 2.01 showed that the picker does not take even Satori's own folder, so the cause is the install, not
#   AnkiMobile: Satori is signed by GBox, and GBox/ESign are known to rewrite the entitlements of the apps they sign,
#   which breaks the system pickers (the same was reported for iDevice ToolKit; Sideloadly and AltStore were fine).
#   The new screen shows what this install really carries: the entitlements of the code signature, the provisioning
#   profile and the libraries the app loads, to copy and send.
import pathlib


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


here = pathlib.Path(__file__).resolve().parent
hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")

s = once(s, '''struct AnkiBackupRow: View {
    @ObservedObject private var sync = AnkiBackupSync.shared
    @State private var pickingFile = false
''', '''struct AnkiBackupRow: View {
    @ObservedObject private var sync = AnkiBackupSync.shared
    @State private var pickingFile = false
    @State private var showingSignature = false
''', "row state")
s = once(s, '''                DocumentPicker(onPick: { url in
                    pickingFile = false
                    sync.read(url)
                }, onCancel: {
                    pickingFile = false
                })
                .ignoresSafeArea()
            }
''', '''                DocumentPicker(onPick: { url in
                    pickingFile = false
                    sync.read(url)
                }, onCancel: {
                    pickingFile = false
                })
                .ignoresSafeArea()
            }
            Button("Подпись приложения (для разбора)") {
                showingSignature = true
            }
            .sheet(isPresented: $showingSignature) {
                SignatureReportView()
            }
''', "row signature button")
s = once(s, '''                    sync.say("✗ Даже папка самого Satori не выбралась: окно выбора папок не работает в этой установке "
                        + "Satori. Пришлите этот текст.")
''', '''                    sync.say("✗ Даже папка самого Satori не выбралась: окно выбора папок не работает в этой установке "
                        + "Satori. Откройте «Подпись приложения» ниже и пришлите её текст.")
''', "check failure text")

s = s.rstrip("\n") + "\n" + (here / "v203-signature.swift").read_text(encoding="utf-8")
hv.write_text(s, encoding="utf-8")
print("v2.03 signature applied")
