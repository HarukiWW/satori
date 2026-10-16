# v1.87:
# - Known words follow AnkiMobile without an export: the folder of its backups (На iPhone → Anki → Backups) is chosen
#   once in Настройки → Anki; when Satori opens and a backup is newer than the one read last, the hidden import page
#   reads it and its mature cards replace the mature list.
# - The list of unknown words of a series opens the dictionary on the clearest line of the series with the word; ⊕
#   queues a full note: that line, its sound and its frame from the video (FFmpeg, without the player).
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
app = pathlib.Path("src/safari/iOS (App)")
hv = app / "HelpView.swift"
s = hv.read_text(encoding="utf-8")

s = once(s, "import Libavutil\n", "import Libavutil\nimport Libswscale\n", "swscale import")

# ---------- the deck inbox: a backup, and the result of its import ----------
s = once(s, '''enum DeckInbox {
''', '''enum DeckInbox {
    /// the deck waiting is a backup of AnkiMobile (AnkiBackupSync): its mature cards replace the mature list
    static var fromBackup = false

''', "inbox backup flag")
s = once(s, '''            let info: [String: Any] = ["name": file.lastPathComponent, "size": size]
''', '''            let info: [String: Any] = ["name": file.lastPathComponent, "size": size, "full": fromBackup]
''', "inbox full flag")
s = once(s, '''        case "pendingDeckDone":
            try? FileManager.default.removeItem(at: folder)
            return .some("true")
''', '''        case "pendingDeckDone":
            try? FileManager.default.removeItem(at: folder)
            if fromBackup {
                var ok = false
                var message = ""
                if let text = request as? String, let body = text.data(using: .utf8),
                   let result = (try? JSONSerialization.jsonObject(with: body)) as? [String: Any] {
                    ok = result["ok"] as? Bool ?? false
                    message = result["status"] as? String ?? ""
                }
                Task { @MainActor in
                    AnkiBackupSync.shared.finished(ok: ok, message: message)
                }
            }
            return .some("true")
''', "inbox done")

# ---------- Настройки → Anki ----------
s = once(s, '''                NavigationLink(destination: AnkiImportPage()) {
                    Text("Импорт колоды Anki")
                }
''', '''                NavigationLink(destination: AnkiImportPage()) {
                    Text("Импорт колоды Anki")
                }
                AnkiBackupRow()
''', "backup row")

# ---------- lists: the frame and the sound go with the note ----------
s = once(s, '''                    guard MiningFrame.isAddNote(link) else { return link }
                    MiningQueue.shared.add(link, video: name)
''', '''                    guard MiningFrame.isAddNote(link) else { return link }
                    MiningQueue.shared.add(MiningFrame.attach(to: link), video: name)
''', "list hooks attach")

# ---------- the unknown words of a series: a full note ----------
region = "struct UnknownWordsView: View {"
s = within(s, region, "\nstruct ", '''    @State private var lookup: UnknownWord? = nil
''', '''    @State private var lookup: UnknownWord? = nil
    @State private var lineLookup: LineLookup? = nil
    /// the word whose line, frame and sound are being found
    @State private var preparing: String? = nil
''', "series list state")
s = within(s, region, "\nstruct ", '''                            Button {
                                lookup = word
                            } label: {
''', '''                            Button {
                                open(word)
                            } label: {
''', "series list tap")
s = within(s, region, "\nstruct ", '''                                    Spacer()
                                    Text("×" + String(word.count))
''', '''                                    Spacer()
                                    if preparing == word.word {
                                        ProgressView()
                                            .padding(.trailing, 6)
                                    }
                                    Text("×" + String(word.count))
''', "series list progress")
s = within(s, region, "\nstruct ",
           '''                        Text("Слово открывает словарь, ⊕ — в очередь майнинга. Свайп вправо — «Знаю», влево — «Игнор».")''',
           '''                        Text("Слово открывает словарь на самой понятной реплике серии; ⊕ кладёт в очередь заметку с её звуком и кадром. Свайп вправо — «Знаю», влево — «Игнор».")''',
           "series list footer")
s = within(s, region, "\nstruct ", '''            .sheet(item: $lookup) { word in
                WordLookupSheet(text: word.word)
            }
''', '''            .sheet(item: $lookup) { word in
                WordLookupSheet(text: word.word)
            }
            .sheet(item: $lineLookup) { item in
                WordLookupSheet(text: item.text, charAt: item.charAt)
            }
''', "series list line sheet")
s = within(s, region, "\nstruct ", '''    private func load() async {
''', '''    /// The dictionary on the clearest line with the word, its frame and sound ready for ⊕; the word alone when the
    /// series has no line with it.
    private func open(_ word: UnknownWord) {
        guard preparing == nil else { return }
        guard let file = VideoLibraryStore.jimakuFile(for: video) else {
            MiningFrame.jpegBase64 = nil
            lookup = word
            return
        }
        preparing = word.word
        Task { @MainActor in
            let index = await library.knownWordsIndex()
            let level = VideoLibraryStore.userLevel
            let judge = WordKnowledge(index: index, level: level, vocabulary: VideoLibraryStore.vocabulary(level: level))
            let target = word.word
            let line = await Task.detached(priority: .userInitiated) {
                ListMining.bestLine(for: target, file: file, judge: judge)
            }.value
            if let line {
                await ListMining.prepare(video: video, line: line)
                lineLookup = LineLookup(text: line.text, charAt: line.charAt)
            } else {
                MiningFrame.jpegBase64 = nil
                lookup = word
            }
            preparing = nil
        }
    }

    private func load() async {
''', "series list open")

s = s.rstrip("\n") + "\n" + (here / "v187-anki.swift").read_text(encoding="utf-8")
hv.write_text(s, encoding="utf-8")

# ---------- the app: the hidden import page and the checks ----------
mv = app / "MainView.swift"
t = mv.read_text(encoding="utf-8")
t = once(t, '''    @AppStorage(AppAccent.key) private var accent = AppAccent.standard
''', '''    @AppStorage(AppAccent.key) private var accent = AppAccent.standard
    @ObservedObject private var backups = AnkiBackupSync.shared
''', "main backups state")
t = once(t, '''        .preferredColorScheme(.dark)
''', '''        .preferredColorScheme(.dark)
        .background {
            // the newest backup of AnkiMobile is read by the import page, out of sight
            if backups.importing {
                AnkiImportPage()
                    .frame(width: 2, height: 2)
                    .opacity(0.01)
                    .allowsHitTesting(false)
            }
        }
        .onAppear {
            AnkiBackupSync.shared.check()
        }
        .onReceive(NotificationCenter.default.publisher(for: UIApplication.didBecomeActiveNotification)) { _ in
            AnkiBackupSync.shared.check()
        }
''', "main backups")
mv.write_text(t, encoding="utf-8")

# ---------- web: a backup replaces the mature list ----------
web = pathlib.Path("src/main/src")
p = web / "lib/ankiImport.ts"
t = p.read_text(encoding="utf-8")
t = once(t, '''export async function importDeck(deck: { words: string[]; mature: string[] }): Promise<{ added: number }> {
''', '''export async function importDeck(
  deck: { words: string[]; mature: string[] },
  replaceMature = false,
): Promise<{ added: number }> {
''', "import deck signature")
t = once(t, '''  const mature = new Set<string>(Array.isArray(data.mature) ? data.mature : []);
''', '''  // a whole collection (a backup of AnkiMobile) says which cards are mature now: lapsed ones drop out
  const mature = new Set<string>(!replaceMature && Array.isArray(data.mature) ? data.mature : []);
''', "import deck replace")
p.write_text(t, encoding="utf-8")

p = web / "components/options/groups/GroupAnkiImport.svelte"
t = p.read_text(encoding="utf-8")
t = once(t, "  async function importBuffer(buf: ArrayBuffer) {\n",
         "  async function importBuffer(buf: ArrayBuffer, full = false) {\n", "import buffer signature")
t = once(t, "    const result = await importDeck(deck);\n", "    const result = await importDeck(deck, full);\n",
         "import buffer full")
t = once(t, "    let pending: { name: string; size: number } | null = null;\n",
         "    let pending: { name: string; size: number; full?: boolean } | null = null;\n", "pending type")
t = once(t, '''    busy = true;
    try {
      const bytes = new Uint8Array(pending.size);
''', '''    busy = true;
    let ok = false;
    try {
      const bytes = new Uint8Array(pending.size);
''', "pending ok")
t = once(t, "      await importBuffer(bytes.buffer);\n", "      await importBuffer(bytes.buffer, pending.full === true);\n      ok = true;\n",
         "pending import")
t = once(t, '''      await app.messageWebview("pendingDeckDone", null).catch(() => undefined);
''', '''      await app.messageWebview("pendingDeckDone", { ok, status }).catch(() => undefined);
''', "pending done")
p.write_text(t, encoding="utf-8")
print("v1.87 anki applied")
