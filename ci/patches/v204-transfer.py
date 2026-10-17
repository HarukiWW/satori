# v2.04: «Перенос данных между установками» in Настройки → Anki.
# - The report of 2.03 showed the cause of the dead folder picker: GBox and Feather keep the bundle ID
#   com.yoonchae.Yomikiri, while the certificate is for app.uva7695.libra5806; signed with that bundle ID, Satori
#   picks folders. It is a separate install, so the old one gives its data (videos, novels, grammar, the mining queue,
#   the settings) into the shared App Group folder of the certificate, and the new one takes it — renames, no copies.
# - The Anki footer says when the bundle ID differs from the certificate's.
import pathlib


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


here = pathlib.Path(__file__).resolve().parent
hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")

s = once(s, '''    @State private var showingSignature = false
''', '''    @State private var showingSignature = false
    @State private var showingTransfer = false
''', "row state")
s = once(s, '''            text += " Последний прочитанный бэкап: " + date.formatted(date: .abbreviated, time: .shortened) + "."
        }
        return text
''', '''            text += " Последний прочитанный бэкап: " + date.formatted(date: .abbreviated, time: .shortened) + "."
        }
        if !SignatureInfo.mismatchNote.isEmpty {
            text += " " + SignatureInfo.mismatchNote
        }
        return text
''', "row footer")
s = once(s, '''            .sheet(isPresented: $showingSignature) {
                SignatureReportView()
            }
''', '''            .sheet(isPresented: $showingSignature) {
                SignatureReportView()
            }
            Button("Перенос данных между установками") {
                showingTransfer = true
            }
            .sheet(isPresented: $showingTransfer) {
                InstallTransferView()
            }
''', "row transfer button")

s = s.rstrip("\n") + "\n" + (here / "v204-transfer.swift").read_text(encoding="utf-8")
hv.write_text(s, encoding="utf-8")
print("v2.04 transfer applied")
