# v1.86:
# - Subtitles without the service text for the deaf (SDH): speakers （ルンゲ）, sounds ［銃声］ （笑い声）, ♪, the arrows of
#   a line that goes on, the marks of a voice ≪ ≫. It goes from the screen, the cards, the coverage and the speech
#   speed (the analysis counts again: algorithm 5). Thoughts in （ ） stay. A switch in the player menu.
# - Smart furigana in the player: the reading over the unknown words of the line, the same judge as in the reader.
# - "Знаю" and "Игнор" for single words: buttons in the dictionary of the app, swipes in the lists of unknown words.
#   The marks are kept apart from the words of Anki (stats.v1: manualKnown, ignored) and can be reset; marked words
#   are not highlighted, not listed as unknown and count as known in the coverage and the furigana.
# - The live background of the main screens: words and kanji of your cards in a dim grid, shown inside soft patches
#   that drift slowly (Настройки → Внешний вид → «Живой фон»).
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

# ---------- SDH ----------
s = once(s, r'''        out = out.replacingOccurrences(of: "<[^>]+>", with: "", options: .regularExpression)
        return out.trimmingCharacters(in: .whitespacesAndNewlines)
''', r'''        out = out.replacingOccurrences(of: "<[^>]+>", with: "", options: .regularExpression)
        if UserDefaults.standard.object(forKey: "ykStripSDH") as? Bool ?? true {
            out = SDHText.strip(out)
        }
        return out.trimmingCharacters(in: .whitespacesAndNewlines)
''', "sdh in clean")
s = once(s, "    static let algorithm = 4\n", "    static let algorithm = 5\n", "analysis version")

# ---------- the player: furigana and SDH switches ----------
s = once(s, '''              @AppStorage("ykSubsTop") private var subsTop = false
''', '''              @AppStorage("ykSubsTop") private var subsTop = false
              @AppStorage("ykSubtitleFurigana") private var subtitleFurigana = true
              @AppStorage("ykStripSDH") private var stripSDH = true
''', "player switches state")
s = once(s, '''                              Picker("Положение субтитров", selection: $subsTop) {
                                  Text("Внизу").tag(false)
                                  Text("Вверху").tag(true)
                              }
''', '''                              Picker("Положение субтитров", selection: $subsTop) {
                                  Text("Внизу").tag(false)
                                  Text("Вверху").tag(true)
                              }
                              Toggle("Фуригана над незнакомыми", isOn: $subtitleFurigana)
                              Toggle("Без служебного текста", isOn: $stripSDH)
                              Text("Служебный текст — имена говорящих, звуки, ♪. Применяется при следующем открытии видео.")
                                  .font(.caption)
                                  .foregroundColor(.secondary)
''', "player switches")

# ---------- the subtitle line: furigana ----------
s = once(s, '''    static func font() -> Font {
        var size: CGFloat = 22
''', '''    static func font(scale: CGFloat = 1) -> Font {
        var size: CGFloat = 22
''', "subtitle font scale")
s = once(s, '''        size = min(max(size, 12), 40)
        if let name = names[family], UIFont(name: name, size: size) != nil {
''', '''        size = min(max(size, 12), 40) * scale
        if let name = names[family], UIFont(name: name, size: size) != nil {
''', "subtitle font size")
s = once(s, '''    @State private var font = SubtitleStyle.font()

    var body: some View {
''', '''    @State private var font = SubtitleStyle.font()
    @State private var small = SubtitleStyle.font(scale: 0.5)
    @State private var rubies: [Int: ReaderFurigana.Ruby] = [:]
    @AppStorage("ykSubtitleFurigana") private var furigana = true

    /// A word; over an unknown one its reading (the other words keep the room for it, so the line stays even).
    @ViewBuilder
    private func word(_ token: LookupToken) -> some View {
        let color = tokenColors[token.id] ?? .white
        if rubies.isEmpty {
            Text(token.text)
                .font(font)
                .foregroundColor(color)
        } else if let ruby = rubies[token.id] {
            HStack(alignment: .bottom, spacing: 0) {
                Text(ruby.head)
                VStack(spacing: 0) {
                    Text(ruby.reading)
                        .font(small)
                        .foregroundColor(.white.opacity(0.8))
                        .lineLimit(1)
                        .fixedSize()
                    Text(ruby.core)
                }
                Text(ruby.tail)
            }
            .font(font)
            .foregroundColor(color)
        } else {
            VStack(spacing: 0) {
                Text(" ")
                    .font(small)
                Text(token.text)
                    .font(font)
                    .foregroundColor(color)
            }
        }
    }

    var body: some View {
''', "subtitle word view")
s = once(s, '''                    ForEach(tokens) { token in
                        Text(token.text)
                            .font(font)
                            .foregroundColor(tokenColors[token.id] ?? .white)
                            .padding(.vertical, 4)
''', '''                    ForEach(tokens) { token in
                        word(token)
                            .padding(.vertical, 4)
''', "subtitle tokens")
s = once(s, '''        .onAppear { refresh(line) }
        .onChange(of: line) { newValue in refresh(newValue) }
    }

    private func refresh(_ text: String) {
        // line breaks inside a cue become spaces; text the tokenizer does not return is shown as a plain tail
''', '''        .onAppear { refresh(line) }
        .onChange(of: line) { newValue in refresh(newValue) }
        .onChange(of: furigana) { _ in refresh(line) }
        .task {
            // the judge of the known words (cached; built again when the cards or the level change)
            await ReaderFurigana.shared.prepare()
            refresh(line)
        }
    }

    private func refresh(_ text: String) {
        // line breaks inside a cue become spaces; text the tokenizer does not return is shown as a plain tail
''', "subtitle refresh hooks")
s = within(s, "struct SubtitleLookupBar: View {", "\nstruct ", '''        tokens = result
        tokenColors = HighlightData.colors(for: result)
''', '''        tokens = result
        tokenColors = HighlightData.colors(for: result)
        rubies = furigana ? ReaderFurigana.shared.rubies(for: result) : [:]
''', "subtitle rubies")

# ---------- marks: "Знаю" / "Игнор" ----------
s = once(s, '''        for w in (root["known"] as? [String]) ?? [] { words.insert(w) }
        return words
    }
''', '''        for w in (root["known"] as? [String]) ?? [] { words.insert(w) }
        words.formUnion(WordMarks.all(root))
        return words
    }
''', "marks in mined words")
s = once(s, '''        if let mature = root["mature"] as? [String] {
            return Set(mature)
        }
        return root["known"] != nil ? minedWords() : []
''', '''        if let mature = root["mature"] as? [String] {
            return Set(mature).union(WordMarks.all(root))
        }
        return root["known"] != nil ? minedWords() : WordMarks.all(root)
''', "marks in analysis words")
s = once(s, '''struct UnknownWordsView: View {
    let video: URL
    @ObservedObject var library: VideoLibraryStore
    @Environment(\\.dismiss) private var dismiss
''', '''struct UnknownWordsView: View {
    let video: URL
    @ObservedObject var library: VideoLibraryStore
    @Environment(\\.dismiss) private var dismiss
    /// changed by a swipe: the list is read again
    @State private var marks = 0
''', "series list state")
s = once(s, '''                    let unknown = HighlightData.notInAnki(result.unknown) { $0.word }
''', '''                    let unknown = marks >= 0 ? HighlightData.notInAnki(result.unknown) { $0.word } : []
''', "series list marks")
s = once(s, '''                                    Text("×" + String(word.count))
                                        .foregroundColor(.secondary)
                                }
                            }
                        }
                    } header: {
                        Text("Незнакомые слова: " + String(unknown.count))
                    } footer: {
                        Text("Слово открывает словарь, ⊕ — в очередь майнинга.")
''', '''                                    Text("×" + String(word.count))
                                        .foregroundColor(.secondary)
                                }
                            }
                            .modifier(WordMarkSwipes(word: word.word) { marks += 1 })
                        }
                    } header: {
                        Text("Незнакомые слова: " + String(unknown.count))
                    } footer: {
                        Text("Слово открывает словарь, ⊕ — в очередь майнинга. Свайп вправо — «Знаю», влево — «Игнор».")
''', "series list swipes")
s = once(s, '''    let words: [CatalogUnknown]
    @State private var lookup: CatalogUnknown? = nil

    var body: some View {
        let words = HighlightData.notInAnki(self.words) { $0.word }
''', '''    let words: [CatalogUnknown]
    @State private var lookup: CatalogUnknown? = nil
    /// changed by a swipe: the list is read again
    @State private var marks = 0

    var body: some View {
        let words = marks >= 0 ? HighlightData.notInAnki(self.words) { $0.word } : []
''', "catalog list marks")
s = within(s, "struct CatalogUnknownView: View {", "\nstruct ", '''                            Text("×" + String(word.count))
                                .foregroundColor(.secondary)
                        }
                    }
''', '''                            Text("×" + String(word.count))
                                .foregroundColor(.secondary)
                        }
                    }
                    .modifier(WordMarkSwipes(word: word.word) { marks += 1 })
''', "catalog list swipes")
s = within(s, "struct CatalogUnknownView: View {", "\nstruct ",
           '''                Text("Самые частые сверху. Слово открывает словарь, ⊕ — в очередь майнинга.")''',
           '''                Text("Самые частые сверху. Слово открывает словарь, ⊕ — в очередь майнинга. Свайп вправо — «Знаю», влево — «Игнор».")''',
           "catalog list footer")
s = once(s, '''                if imported.all > 0 {
                    Button("Удалить импортированные слова", role: .destructive) {
                        confirmForget = true
                    }
                }
''', '''                if imported.all > 0 {
                    Button("Удалить импортированные слова", role: .destructive) {
                        confirmForget = true
                    }
                }
                MarksResetRow()
''', "marks reset row")

# ---------- the live background ----------
s = once(s, '''    @AppStorage(AppAccent.key) private var accent = AppAccent.standard
    @AppStorage("ykMiningQueue") private var miningQueue = false
''', '''    @AppStorage(AppAccent.key) private var accent = AppAccent.standard
    @AppStorage("ykMiningQueue") private var miningQueue = false
    @AppStorage("ykBackdrop") private var backdrop = true
''', "backdrop setting state")
s = once(s, '''                Stepper(value: config.int("general.subtitle_size", 22), in: 14 ... 36) {
''', '''                Toggle("Живой фон", isOn: $backdrop)
                Stepper(value: config.int("general.subtitle_size", 22), in: 14 ... 36) {
''', "backdrop toggle")
for name, body in (("NativeVideoListView", "List"), ("NovelLibraryView", "List"), ("NativeSettingsView", "Form")):
    s = within(s, "struct " + name + ": View {", "\nstruct ", '''    var body: some View {
        ''' + body + ''' {
''', '''    var body: some View {
        withBackdrop
            .satoriBackdrop()
    }

    private var withBackdrop: some View {
        ''' + body + ''' {
''', "backdrop " + name)

s = s.rstrip("\n") + "\n" + (here / "v186-ideas.swift").read_text(encoding="utf-8")
hv.write_text(s, encoding="utf-8")

mv = app / "MainView.swift"
t = mv.read_text(encoding="utf-8")
t = once(t, '''            HelpView()
                .tabItem {
''', '''            HelpView()
                .background {
                    if #available(iOS 16.0, *) {
                        SatoriBackdrop()
                    }
                }
                .tabItem {
''', "statistics backdrop")
mv.write_text(t, encoding="utf-8")

# ---------- web: the marks ----------
web = pathlib.Path("src/main/src")
p = web / "lib/statsLite.ts"
t = p.read_text(encoding="utf-8")
t = once(t, '''export interface LiteStats {
  known?: string[];
''', '''export interface LiteStats {
  known?: string[];
  /** marked "Знаю" in the dictionary: known without a card */
  manualKnown?: string[];
  /** marked "Игнор": not a word to learn */
  ignored?: string[];
''', "lite stats marks")
p.write_text(t, encoding="utf-8")

p = web / "extension/stats.ts"
t = p.read_text(encoding="utf-8")
t = once(t, '''  /** words imported from an Anki collection (kept by the app) */
  known?: string[];
}
''', '''  /** words imported from an Anki collection (kept by the app) */
  known?: string[];
  /** marked "Знаю" / "Игнор" in the app: not highlighted either */
  manualKnown?: string[];
  ignored?: string[];
}
''', "stats marks type")
t = once(t, '''  for (const w of data.known ?? []) {
    const word = w
''', '''  for (const w of [...(data.manualKnown ?? []), ...(data.ignored ?? [])]) set.add(w);
  for (const w of data.known ?? []) {
    const word = w
''', "stats marks in mined")
p.write_text(t, encoding="utf-8")

p = web / "platform/iosapp/appStats.ts"
t = p.read_text(encoding="utf-8")
t = once(t, '''export async function lookupMinedApp(
  forms: string[],
): Promise<{ exact: string[]; related: string[]; queued: string[] }> {
  const found = findMinedLite(await loadApp(), forms);
''', '''export async function lookupMinedApp(
  forms: string[],
): Promise<{ exact: string[]; related: string[]; queued: string[]; mark?: string }> {
  const data = await loadApp();
  const found = findMinedLite(data, forms);
  const mark = (data.manualKnown ?? []).some((w) => forms.includes(w))
    ? "known"
    : (data.ignored ?? []).some((w) => forms.includes(w))
      ? "ignored"
      : undefined;
''', "lookup mark")
t = once(t, '''  return { ...found, queued };
}
''', '''  return { ...found, queued, mark };
}

/** "Знаю" / "Игнор" for the forms of an entry; null takes the mark away. */
export async function markWordApp(forms: string[], kind: "known" | "ignored" | null): Promise<void> {
  const data = await loadApp();
  const strip = (list?: string[]) => (list ?? []).filter((w) => !forms.includes(w));
  data.manualKnown = strip(data.manualKnown);
  data.ignored = strip(data.ignored);
  if (kind === "known") data.manualKnown.push(...forms);
  if (kind === "ignored") data.ignored.push(...forms);
  await Platform.messageWebview("saveStats", data);
}
''', "mark word")
p.write_text(t, encoding="utf-8")

p = web / "platform/iosapp/runtimeShim.ts"
t = p.read_text(encoding="utf-8")
t = once(t, 'import { lookupMinedApp } from "./appStats";\n',
         'import { lookupMinedApp, markWordApp } from "./appStats";\n', "shim import")
t = once(t, '''  if (msg.key === "minedLookup") {
''', '''  if (msg.key === "markWord") {
    const req = msg.request as { forms: string[]; kind: "known" | "ignored" | null };
    await markWordApp(req.forms, req.kind);
    return true;
  }
  if (msg.key === "minedLookup") {
''', "shim mark")
t = once(t, '''(globalThis as any).yomikiriRuntime = {
  lastError: undefined,
''', '''(globalThis as any).yomikiriRuntime = {
  lastError: undefined,
  /** the dictionary shows the "Знаю" / "Игнор" buttons in the app only */
  isApp: true,
''', "shim app flag")
p.write_text(t, encoding="utf-8")

p = web / "components/dictionary/Badges.svelte"
t = p.read_text(encoding="utf-8")
t = once(t, '''  export let mined: { exact: string[]; related: string[]; queued?: string[] } = {
''', '''  export let mined: { exact: string[]; related: string[]; queued?: string[]; mark?: string } = {
''', "badges type")
t = once(t, '''    mined.exact.length > 0 ||
    mined.related.length > 0;
''', '''    mined.exact.length > 0 ||
    mined.related.length > 0 ||
    mined.mark !== undefined;
''', "badges has")
t = once(t, '''      <div class="badge related">≈ {mined.related.slice(0, 2).join(", ")}</div>
    {/if}
''', '''      <div class="badge related">≈ {mined.related.slice(0, 2).join(", ")}</div>
    {/if}
    {#if mined.mark === "known"}
      <div class="badge mark">Знаю</div>
    {:else if mined.mark === "ignored"}
      <div class="badge mark">Игнор</div>
    {/if}
''', "badges mark")
t = once(t, '''  /** HSL(x, 38%, 75%) */
  .common {
''', '''  .mark {
    --badge-color: #8e8e93;
  }

  /** HSL(x, 38%, 75%) */
  .common {
''', "badges mark style")
p.write_text(t, encoding="utf-8")

p = web / "components/dictionary/DicEntryView.svelte"
t = p.read_text(encoding="utf-8")
t = once(t, '''  let mined: { exact: string[]; related: string[]; queued?: string[] } = {
    exact: [],
    related: [],
  };
''', '''  let mined: { exact: string[]; related: string[]; queued?: string[]; mark?: string } = {
    exact: [],
    related: [],
  };

  // eslint-disable-next-line
  const runtime = (globalThis as any).yomikiriRuntime;
  const isApp = runtime?.isApp === true;

  /** "Знаю" (known without a card) or "Игнор" (not a word to learn) for every form of the entry; null: no mark. */
  function setMark(kind: "known" | "ignored" | null): void {
    if (entry.type !== "word") return;
    const forms = entry.kanjis.map((k) => k.kanji);
    if (forms.length === 0) forms.push(...entry.readings.map((r) => r.reading));
    runtime.sendMessage({ key: "markWord", request: { forms, kind } }, () => undefined);
    mined = { ...mined, mark: kind ?? undefined };
  }
''', "entry marks script")
t = once(t, '''  <Badges {entry} bind:mined />
''', '''  {#if isApp && entry.type === "word" && !added}
    <div class="marks">
      {#if mined.mark !== undefined}
        <button class="mark" on:click={() => setMark(null)}>
          Снять «{mined.mark === "known" ? "Знаю" : "Игнор"}»
        </button>
      {:else}
        <button class="mark" on:click={() => setMark("known")}>Знаю</button>
        <button class="mark" on:click={() => setMark("ignored")}>Игнор</button>
      {/if}
    </div>
  {/if}
  <Badges {entry} bind:mined />
''', "entry marks buttons")
t = once(t, '''  .icons {
    flex: 0 0 auto;
''', '''  .marks {
    margin: 0.4rem var(--edge-horizontal-padding) 0;
    display: flex;
    gap: 0.5rem;
  }
  .mark {
    font-size: 0.75rem;
    padding: 0.2rem 0.7rem;
    border-radius: 999px;
    border: 1px solid #8e8e93;
    color: #c7c7cc;
    background: transparent;
  }

  .icons {
    flex: 0 0 auto;
''', "entry marks style")
p.write_text(t, encoding="utf-8")
print("v1.86 ideas applied")
