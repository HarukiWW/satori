# v1.85: fixes.
# - Video import: the Jimaku search of many imported videos runs one after another (it ran all at once and Jimaku
#   refused them); a 429 answer waits and asks again. "Найти субтитры" in the menu of a video file.
# - Mining queue: the clip server is started anew when Satori comes back (iOS takes its socket away in the
#   background: "не удалось подключиться к серверу" for every next note); the frame goes to AnkiMobile as a link to
#   a .jpg like the sound, not as base64 inside the note (smaller links, a smaller collection); AnkiMobile gets 5 s
#   to call back; notes can be chosen and sent one by one.
# - Highlight: a word is "in Anki" in any of its forms (the card's 先ほど, the dictionary form 先程); the frequency
#   rank is the one of the written word (the dictionary shows the same); prefixes (聖) count as words. The lists of
#   unknown words leave out words that are in Anki.
# - Deck import: sentences are no words (the saved list stayed small); every failure says at which step; broken
#   saved statistics stop the import instead of being written over.
# - Appearance: the font of the Japanese text is chosen from a list and also sets the subtitles of the player; the
#   size of the subtitles; the text size field is gone (the − / + buttons of the dictionary set it); the height
#   field says it is for Safari. The dictionary tab is black under the tab bar like the other tabs.
import pathlib


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


def within(text, start, end, old, new, label):
    """Replace every `old` between the first `start` and the next `end` after it."""
    a = text.index(start)
    b = text.index(end, a + len(start))
    part = text[a:b]
    assert old in part, "pattern not found in region: " + label
    return text[:a] + part.replace(old, new) + text[b:]


app = pathlib.Path("src/safari/iOS (App)")
hv = app / "HelpView.swift"
s = hv.read_text(encoding="utf-8")

# ---------- Jimaku: one search at a time, 429 waits ----------
s = once(s, r'''        request.setValue("Satori/1.69", forHTTPHeaderField: "User-Agent")
        let (data, response) = try await URLSession.shared.data(for: request)
        let status = (response as? HTTPURLResponse)?.statusCode ?? 0
        guard status == 200 else { throw Failure.status(status) }
        return try JSONDecoder().decode(T.self, from: data)
''', r'''        request.setValue("Satori/1.69", forHTTPHeaderField: "User-Agent")
        // "too many requests": wait as long as Jimaku asks (at most 30 s) and ask again, three times
        for attempt in 1 ... 4 {
            let (data, response) = try await URLSession.shared.data(for: request)
            let http = response as? HTTPURLResponse
            let status = http?.statusCode ?? 0
            if status == 429, attempt < 4 {
                let wait = min(30, max(2, Double(http?.value(forHTTPHeaderField: "Retry-After") ?? "") ?? 5))
                try await Task.sleep(nanoseconds: UInt64(wait * 1_000_000_000))
                continue
            }
            guard status == 200 else { throw Failure.status(status) }
            return try JSONDecoder().decode(T.self, from: data)
        }
        throw Failure.status(429)
''', "jimaku get")

s = once(s, r'''    private func runImportQueue() {
        guard !importRunning, !importQueue.isEmpty else { return }
        importRunning = true
        let batch = importQueue
        importQueue.removeAll()
        importRunning = false
        for video in batch {
            Task { @MainActor in
                await askOrConvert(video)
            }
        }
    }
''', r'''    private func runImportQueue() {
        guard !importRunning, !importQueue.isEmpty else { return }
        importRunning = true
        Task { @MainActor in
            while !importQueue.isEmpty {
                let video = importQueue.removeFirst()
                await askOrConvert(video)
            }
            importRunning = false
        }
    }

    /// Jimaku and the Japanese track again for one video (the menu of the file).
    func findSubtitles(_ video: URL) {
        guard !importQueue.contains(video) else { return }
        status[video.lastPathComponent] = "в очереди…"
        importQueue.append(video)
        runImportQueue()
    }
''', "import queue")

s = once(s, r'''                    .contextMenu {
                        if !item.isFolder && !moveTargets.isEmpty {
''', r'''                    .contextMenu {
                        if !item.isFolder && VideoLibraryStore.isVideo(item.url.lastPathComponent) {
                            Button {
                                library.findSubtitles(item.url)
                            } label: {
                                Label("Найти субтитры", systemImage: "captions.bubble")
                            }
                        }
                        if !item.isFolder && !moveTargets.isEmpty {
''', "file menu")

# ---------- the clip server: frames too, a new socket after the background ----------
s = once(s, r'''    static func keep(_ data: Data) -> String? {
        let name = UUID().uuidString + ".m4a"
''', r'''    static func keep(_ data: Data, ext: String = "m4a") -> String? {
        let name = UUID().uuidString + "." + ext
''', "clip keep")
s = once(s, r'''            if name.range(of: "^[0-9A-F-]{36}\\.m4a$", options: .regularExpression) != nil {
                body = try? Data(contentsOf: folder.appendingPathComponent(name))
            }
            var header = "HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n"
            if let body {
                header = "HTTP/1.1 200 OK\r\nContent-Type: audio/mp4\r\nContent-Length: " + String(body.count) + "\r\n"
            }
''', r'''            if name.range(of: "^[0-9A-F-]{36}\\.(m4a|jpg)$", options: .regularExpression) != nil {
                body = try? Data(contentsOf: folder.appendingPathComponent(name))
            }
            var header = "HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n"
            if let body {
                let type = name.hasSuffix(".jpg") ? "image/jpeg" : "audio/mp4"
                header = "HTTP/1.1 200 OK\r\nContent-Type: " + type + "\r\nContent-Length: " + String(body.count) + "\r\n"
            }
''', "clip serve")
s = once(s, r'''        created.stateUpdateHandler = { state in
            switch state {
            case .failed, .cancelled:
                Task { @MainActor in
                    ClipServer.shared.listener = nil
                }
            default:
                break
            }
        }
''', r'''        created.stateUpdateHandler = { [weak created] state in
            switch state {
            case .failed, .cancelled:
                Task { @MainActor in
                    // only this listener: a newer one may already be in its place
                    guard let created, ClipServer.shared.listener === created else { return }
                    ClipServer.shared.listener = nil
                    if case .failed = state {
                        // the port of the old socket may still be closing: once more a moment later
                        try? await Task.sleep(nanoseconds: 300_000_000)
                        ClipServer.shared.start()
                    }
                }
            default:
                break
            }
        }
''', "clip server state")
s = once(s, r'''    private func letGo() {
        guard background != .invalid else { return }
        UIApplication.shared.endBackgroundTask(background)
        background = .invalid
    }
''', r'''    private func letGo() {
        // iOS may have taken the socket of a suspended app: a running server starts on a new one
        if let old = listener {
            listener = nil
            old.cancel()
            start()
        }
        guard background != .invalid else { return }
        UIApplication.shared.endBackgroundTask(background)
        background = .invalid
    }
''', "clip server foreground")

s = once(s, r'''        if let frame = jpegBase64, let index = emptyField({ field in pictureNames.contains { field.contains($0) } }) {
            let html = "<img src=\"data:image/jpeg;base64," + frame + "\">"
            items[index].value = html.addingPercentEncoding(withAllowedCharacters: ankiQueryAllowed)
        }
''', r'''        if let frame = jpegBase64, let index = emptyField({ field in pictureNames.contains { field.contains($0) } }) {
            // a link to the picture, as for the sound: AnkiMobile keeps it as a media file, not as text in the note
            if let data = Data(base64Encoded: frame), let name = ClipFiles.keep(data, ext: "jpg") {
                items[index].value = ClipFiles.link(name).addingPercentEncoding(withAllowedCharacters: ankiQueryAllowed)
                Task { @MainActor in
                    ClipServer.shared.start()
                }
            } else {
                let html = "<img src=\"data:image/jpeg;base64," + frame + "\">"
                items[index].value = html.addingPercentEncoding(withAllowedCharacters: ankiQueryAllowed)
            }
        }
''', "frame link")
s = once(s, r'''            if items[index].value == frameMarker {
                html = frame.map { framePrefix + $0.base64EncodedString() + "\">" } ?? ""
''', r'''            if items[index].value == frameMarker {
                // notes queued before 1.85 keep their frame in a file of their own: it goes as a link too
                html = frame.map { data in
                    ClipFiles.keep(data, ext: "jpg").map { ClipFiles.link($0) } ?? framePrefix + data.base64EncodedString() + "\">"
                } ?? ""
''', "queued frame link")

# ---------- the queue: a longer wait for AnkiMobile, chosen notes ----------
s = once(s, r'''        guard let waiting = awaiting else { return }
        DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
''', r'''        guard let waiting = awaiting else { return }
        DispatchQueue.main.asyncAfter(deadline: .now() + 5) {
''', "queue wait")
s = once(s, r'''    func sendAll(video: String?) {
        sending = entries.filter { video == nil || $0.video == video }
        sendNext()
    }
''', r'''    func sendAll(video: String?) {
        sending = entries.filter { video == nil || $0.video == video }
        sendNext()
    }

    /// The chosen notes only, in the order of the queue.
    func send(_ ids: Set<UUID>) {
        sending = entries.filter { ids.contains($0.id) }
        sendNext()
    }
''', "queue send chosen")

s = once(s, r'''    @ObservedObject private var queue = MiningQueue.shared
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationView {
            List {
                let entries = queue.entries.filter { video == nil || $0.video == video }
''', r'''    @ObservedObject private var queue = MiningQueue.shared
    @Environment(\.dismiss) private var dismiss
    @State private var choosing = false
    @State private var chosen = Set<UUID>()

    var body: some View {
        NavigationView {
            List(selection: $chosen) {
                let entries = queue.entries.filter { video == nil || $0.video == video }
''', "queue view state")
s = once(s, r'''                    .swipeActions {
                        Button(role: .destructive) {
                            queue.remove(entry)
                        } label: {
                            Label("Убрать", systemImage: "trash")
                        }
                    }
                }
            }
            .navigationTitle("Очередь")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Закрыть") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button(queue.sending.isEmpty ? "Добавить все" : "Добавляю… " + String(queue.sending.count)) {
                        queue.sendAll(video: video)
                    }
                    .disabled(!queue.sending.isEmpty || !queue.entries.contains { video == nil || $0.video == video })
                }
            }
''', r'''                    .swipeActions {
                        Button(role: .destructive) {
                            queue.remove(entry)
                        } label: {
                            Label("Убрать", systemImage: "trash")
                        }
                    }
                    .swipeActions(edge: .leading) {
                        Button {
                            queue.send([entry.id])
                        } label: {
                            Label("В Anki", systemImage: "paperplane")
                        }
                        .tint(.blue)
                        .disabled(!queue.sending.isEmpty)
                    }
                    .tag(entry.id)
                }
            }
            .environment(\.editMode, .constant(choosing ? .active : .inactive))
            .navigationTitle("Очередь")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button(choosing ? "Отмена" : "Закрыть") {
                        if choosing {
                            choosing = false
                            chosen = []
                        } else {
                            dismiss()
                        }
                    }
                }
                ToolbarItem(placement: .primaryAction) {
                    if !choosing && queue.sending.isEmpty && queue.entries.contains(where: { video == nil || $0.video == video }) {
                        Button("Выбрать") { choosing = true }
                    }
                }
                ToolbarItem(placement: .confirmationAction) {
                    if choosing {
                        Button("Добавить (" + String(chosen.count) + ")") {
                            queue.send(chosen)
                            choosing = false
                            chosen = []
                        }
                        .disabled(chosen.isEmpty || !queue.sending.isEmpty)
                    } else {
                        Button(queue.sending.isEmpty ? "Добавить все" : "Добавляю… " + String(queue.sending.count)) {
                            queue.sendAll(video: video)
                        }
                        .disabled(!queue.sending.isEmpty || !queue.entries.contains { video == nil || $0.video == video })
                    }
                }
            }
''', "queue view")

# ---------- highlight: every form of a word in Anki, the rank of the written word ----------
s = once(s, r'''    static func colors(for tokens: [LookupToken]) -> [Int: Color] {
        let (settings, mined) = cachedSettings()
        guard settings.enabled else { return [:] }
        // notes waiting in the player's mining queue are added words too
        let queued = Set(yomikiriQueuedWordsHook?() ?? [])
        var result: [Int: Color] = [:]
        let contentPOS: Set<String> = ["名詞", "動詞", "形容詞", "形状詞", "副詞"]
        for token in tokens where !token.base.isEmpty && !mined.contains(token.base) && !queued.contains(token.base)
            && contentPOS.contains(token.pos) {
            let reading = hiragana(token.reading)
            let level = jlptLevel(base: token.base, reading: reading)
            if level > 0, settings.jlpt[level] == true, let hex = jlptColors[level], let c = color(hex: hex) {
                result[token.id] = c
            } else if settings.freq, let r = rank(base: token.base, reading: reading, dict: settings.dict, text: token.text),
                      r >= settings.lo, r <= settings.hi, let c = color(hex: settings.color) {
                result[token.id] = c
            }
        }
        return result
    }
''', r'''    static func colors(for tokens: [LookupToken]) -> [Int: Color] {
        let (settings, mined) = cachedSettings()
        guard settings.enabled else { return [:] }
        // notes waiting in the player's mining queue are added words too
        let added = forms(of: mined).union(yomikiriQueuedWordsHook?() ?? [])
        var result: [Int: Color] = [:]
        let contentPOS: Set<String> = ["名詞", "動詞", "形容詞", "形状詞", "副詞", "接頭辞"]
        for token in tokens where !token.base.isEmpty && !added.contains(token.base) && !added.contains(token.text)
            && contentPOS.contains(token.pos) {
            let reading = hiragana(token.reading)
            let level = jlptLevel(base: token.base, reading: reading)
            // the rank of the word as written (先ほど), as the dictionary shows it; the dictionary form (先程) after it
            let written = rank(base: token.text, reading: reading, dict: settings.dict, text: token.text)
            if level > 0, settings.jlpt[level] == true, let hex = jlptColors[level], let c = color(hex: hex) {
                result[token.id] = c
            } else if settings.freq,
                      let r = written ?? rank(base: token.base, reading: reading, dict: settings.dict, text: token.text),
                      r >= settings.lo, r <= settings.hi, let c = color(hex: settings.color) {
                result[token.id] = c
            }
        }
        return result
    }

    private static var formsCache: (fingerprint: UInt64, forms: Set<String>)?
    private static var formsPending: UInt64?

    /// The words in Anki with their other forms: the card's 先ほど and the dictionary form 先程. Built off the main
    /// thread once per change of the words; until then the words themselves.
    static func forms(of words: Set<String>) -> Set<String> {
        let fingerprint = KnownWordsIndex.fingerprint(words)
        if let cached = formsCache, cached.fingerprint == fingerprint {
            return cached.forms
        }
        if formsPending != fingerprint {
            formsPending = fingerprint
            Task.detached(priority: .utility) {
                let built = KnownWordsIndex(words).forms.union(words)
                await MainActor.run {
                    formsCache = (fingerprint, built)
                }
            }
        }
        return words
    }

    /// Lists of unknown words without the words that are in Anki already (young cards count as unknown in the
    /// coverage, but they are mined).
    static func notInAnki<T>(_ items: [T], word: (T) -> String) -> [T] {
        let added = forms(of: minedWords()).union(yomikiriQueuedWordsHook?() ?? [])
        return items.filter { !added.contains(word($0)) }
    }
''', "highlight colors")

s = once(s, r'''                    Section {
                        ForEach(result.unknown) { word in
''', r'''                    let unknown = HighlightData.notInAnki(result.unknown) { $0.word }
                    Section {
                        ForEach(unknown) { word in
''', "series unknown list")
s = once(s, r'''                        Text("Незнакомые слова: " + String(result.unknown.count))
''', r'''                        Text("Незнакомые слова: " + String(unknown.count))
''', "series unknown count")
s = once(s, r'''    let words: [CatalogUnknown]
    @State private var lookup: CatalogUnknown? = nil

    var body: some View {
        List {
            Section {
                ForEach(words) { word in
''', r'''    let words: [CatalogUnknown]
    @State private var lookup: CatalogUnknown? = nil

    var body: some View {
        let words = HighlightData.notInAnki(self.words) { $0.word }
        List {
            Section {
                ForEach(words) { word in
''', "catalog unknown list")

# ---------- subtitles: size and font from Настройки → Внешний вид ----------
s = within(s, "struct SubtitleLookupBar: View {", "\nstruct ", r'''.font(.system(size: 22, weight: .medium))''',
           r'''.font(font)''', "subtitle font")
s = once(s, r'''    @State private var tokens: [LookupToken] = []
    @State private var tokenColors: [Int: Color] = [:]

    var body: some View {
        Group {
            if tokens.isEmpty {
''', r'''    @State private var tokens: [LookupToken] = []
    @State private var tokenColors: [Int: Color] = [:]
    @State private var font = SubtitleStyle.font()

    var body: some View {
        Group {
            if tokens.isEmpty {
''', "subtitle font state")
s = s.rstrip("\n") + r'''

/// Size and font of the subtitle line: "general.subtitle_size" and the Japanese font of Настройки → Внешний вид.
enum SubtitleStyle {
    /// CSS family of the web settings → the font of the subtitles
    private static let names = [
        "Hiragino Sans": "HiraginoSans-W6",
        "Hiragino Mincho ProN": "HiraMinProN-W6",
        "Hiragino Maru Gothic ProN": "HiraMaruProN-W4",
    ]

    static func font() -> Font {
        var size: CGFloat = 22
        var family = ""
        if let json = (try? Storage.config.get())?.data(using: .utf8),
           let root = (try? JSONSerialization.jsonObject(with: json)) as? [String: Any] {
            size = CGFloat((root["general.subtitle_size"] as? NSNumber)?.doubleValue ?? 22)
            family = root["general.font"] as? String ?? ""
        }
        size = min(max(size, 12), 40)
        if let name = names[family], UIFont(name: name, size: size) != nil {
            return .custom(name, size: size)
        }
        return .system(size: size, weight: .medium)
    }
}
'''
hv.write_text(s, encoding="utf-8")

# ---------- the dictionary tab: black under the tab bar ----------
dv = app / "DictionaryView.swift"
t = dv.read_text(encoding="utf-8")
t = once(t, "    static let BACKGROUND_COLOR = Color(red: 0.110, green: 0.110, blue: 0.118)\n",
         "    static let BACKGROUND_COLOR = Color.black\n", "dictionary background")
dv.write_text(t, encoding="utf-8")

# ---------- web: the subtitle size setting, the appearance group ----------
web = pathlib.Path("src/main/src")
cfg = web / "lib/config.ts"
t = cfg.read_text(encoding="utf-8")
t = once(t, '  "general.accent": string;\n',
         '  "general.accent": string;\n  /** subtitle line of the player (pt) */\n  "general.subtitle_size": number;\n',
         "config type")
t = once(t, '  "general.accent": "#0a84ff",\n',
         '  "general.accent": "#0a84ff",\n  "general.subtitle_size": 22,\n', "config default")
cfg.write_text(t, encoding="utf-8")

(web / "components/options/groups/GroupAppearance.svelte").write_text('''<script lang="ts">
  import OptionNumber from "../items/OptionNumber.svelte";
  import OptionSelect from "../items/OptionSelect.svelte";
  import GroupedOptions from "../GroupedOptions.svelte";
  import Config from "lib/config";

  const config = Config.using();
  const japaneseFontConfig = config.store("general.font");
  const subtitleSizeConfig = config.store("general.subtitle_size");
  const maxHeightConfig = config.store("general.tooltip_max_height");

  const fonts: [string, string][] = [
    ["", "Системный"],
    ["Hiragino Sans", "Hiragino Sans"],
    ["Hiragino Mincho ProN", "Минтё (с засечками)"],
    ["Hiragino Maru Gothic ProN", "Скруглённый"],
  ];
  // a font typed in by hand before 1.85 stays selectable
  $: fontOptions = fonts.some(([value]) => value === $japaneseFontConfig)
    ? fonts
    : [...fonts, [$japaneseFontConfig, $japaneseFontConfig] as [string, string]];
</script>

<GroupedOptions title="Внешний вид">
  <OptionSelect bind:selected={$japaneseFontConfig} options={fontOptions} title="Японский шрифт">
    Словарь и субтитры плеера
  </OptionSelect>
  <OptionNumber bind:value={$subtitleSizeConfig} title="Размер субтитров" min={14} max={36}>
    Строка субтитров в плеере (pt)
  </OptionNumber>
  <OptionNumber
    bind:value={$maxHeightConfig}
    title="Высота окна в Safari"
    min={120}
    max={1200}
  >
    Наибольшая высота окна словаря на сайтах в Safari (px)
  </OptionNumber>
</GroupedOptions>
''', encoding="utf-8")

# ---------- web: the deck import ----------
lib = web / "lib/ankiImport.ts"
t = lib.read_text(encoding="utf-8")
t = once(t, '''  const models = JSON.parse(db.exec("select models from col")[0].values[0][0]);
  for (const key of Object.keys(models)) {
''', '''  // newer collections leave col.models empty: the first field is the word then
  let models: any = {};
  try {
    models = JSON.parse(String(db.exec("select models from col")[0].values[0][0] || "{}"));
  } catch (e) {
    models = {};
  }
  for (const key of Object.keys(models)) {
''', "models parse")
t = once(t, '''      const word = wordFromFields(names[String(row[0])] ?? [], values);
      if (!word) continue;
      words.add(word);
      if (Number(row[2]) === 1) mature.add(word);
''', '''      const word = wordFromFields(names[String(row[0])] ?? [], values);
      // a sentence deck gives sentences, not words (and a list of megabytes)
      if (!word || word.length > 24) continue;
      words.add(word);
      if (Number(row[2]) === 1) mature.add(word);
''', "word length")
t = once(t, '''export async function importDeck(deck: { words: string[]; mature: string[] }): Promise<{ added: number }> {
  const raw = (await Platform.messageWebview("loadStats", null)) as any;
  const data: any = raw && raw.days !== undefined ? raw : { days: {} };
  const known = new Set<string>(Array.isArray(data.known) ? data.known : []);
''', '''export async function importDeck(deck: { words: string[]; mature: string[] }): Promise<{ added: number }> {
  let raw: any;
  try {
    raw = (await Platform.messageWebview("loadStats", null)) as any;
  } catch (err) {
    // written over, the statistics would be lost: the import stops
    throw new Error(
      "сохранённая статистика не читается (" + (err instanceof Error ? err.message : String(err)) + "), импорт остановлен",
    );
  }
  const data: any = raw && raw.days !== undefined ? raw : { days: {} };
  const known = new Set<string>(
    (Array.isArray(data.known) ? data.known : []).filter((w: unknown) => typeof w === "string" && w.length <= 24),
  );
''', "import stats load")
lib.write_text(t, encoding="utf-8")

page = web / "components/options/groups/GroupAnkiImport.svelte"
t = page.read_text(encoding="utf-8")
t = once(t, '''    status = "Чтение колоды...";
    const deck = await readAnkiDeck(buf);
    const result = await importDeck(deck);
''', '''    status = "Чтение колоды...";
    let deck: { words: string[]; mature: string[] };
    try {
      deck = await readAnkiDeck(buf);
    } catch (err) {
      throw new Error("чтение колоды: " + (err instanceof Error ? err.message : String(err)));
    }
    status = "Сохраняю слова...";
    const result = await importDeck(deck);
''', "import steps")
t = once(t, '''        const chunk: string = await app.messageWebview("pendingDeckChunk", { offset, length: step });
''', '''        let chunk: string;
        try {
          chunk = await app.messageWebview("pendingDeckChunk", { offset, length: step });
        } catch (err) {
          throw new Error("передача файла: " + (err instanceof Error ? err.message : String(err)));
        }
''', "import transfer")
page.write_text(t, encoding="utf-8")
print("v1.85 fixes applied")
