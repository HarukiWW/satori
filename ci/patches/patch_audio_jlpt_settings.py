# Moved out of build-ios-v141-player.yml, step "Patch audio button, JLPT highlighting, settings notes" (GitHub limits workflow files to 500 KB).
import base64, csv, glob, json, pathlib, re, struct

web = pathlib.Path("src/main/src")


def replace_once(text, old, new, label, count=1):
    assert text.count(old) == count, "pattern not found %d times: %s (%d)" % (count, label, text.count(old))
    return text.replace(old, new)


def edit(path, pairs):
    p = pathlib.Path(path)
    s = p.read_text()
    for old, new in pairs:
        s = replace_once(s, old, new, str(path) + " :: " + old[:40])
    p.write_text(s)


def fnv(s):
    h = 0x811C9DC5
    b = s.encode("utf-16-le")
    for i in range(0, len(b), 2):
        h ^= b[i] | (b[i + 1] << 8)
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h


def to_hira(s):
    return "".join(chr(ord(c) - 0x60) if 0x30A1 <= ord(c) <= 0x30F6 else c for c in s)


# ======================= 1. audio button (left of "add to Anki") =======================
(web / "components/dictionary/speech.ts").write_text('''function pickJapaneseVoice(synth: SpeechSynthesis): SpeechSynthesisVoice | undefined {
  const voices = synth
    .getVoices()
    .filter((v) => v.lang.replace("_", "-").toLowerCase().startsWith("ja"));
  const good = voices.find((v) => /premium|enhanced|siri/i.test(v.name));
  return good ?? voices[0];
}

/** Reads the text aloud with the Japanese voice of the device. */
export function speakJapanese(text: string, onEnd: () => void): void {
  if (
    typeof window === "undefined" ||
    window.speechSynthesis === undefined ||
    typeof SpeechSynthesisUtterance === "undefined"
  ) {
    onEnd();
    return;
  }
  try {
    const synth = window.speechSynthesis;
    synth.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "ja-JP";
    utterance.rate = 0.9;
    const voice = pickJapaneseVoice(synth);
    if (voice !== undefined) utterance.voice = voice;
    utterance.onend = onEnd;
    utterance.onerror = onEnd;
    synth.speak(utterance);
    window.setTimeout(onEnd, 10000);
  } catch (_e) {
    onEnd();
  }
}
''')

(web / "components/dictionary/AudioButton.svelte").write_text('''<script lang="ts">
  import { type Entry, getMainForm, getReadingForForm } from "lib/dicEntry";
  import IconVolume from "@icons/volume-high-outline.svg";
  import IconedButton from "components/IconedButton.svelte";
  import { speakJapanese } from "./speech";

  export let entry: Entry;

  let playing = false;

  function play(): void {
    if (entry.type !== "word") return;
    const term = getMainForm(entry);
    const reading = getReadingForForm(entry, term, false).reading;
    playing = true;
    speakJapanese(reading !== "" ? reading : term, () => {
      playing = false;
    });
  }
</script>

<IconedButton size="2rem" highlight={playing} on:click={play}>
  <IconVolume />
</IconedButton>
''')

edit(web / "components/dictionary/DicEntryView.svelte", [
    ('  import PitchAccent from "./PitchAccent.svelte";\n',
     '  import PitchAccent from "./PitchAccent.svelte";\n  import AudioButton from "./AudioButton.svelte";\n'),
    ('    <div class="icons">\n      {#if $ankiEnabledConfig && entry.type === "word"}\n',
     '    <div class="icons">\n      {#if entry.type === "word"}\n        <AudioButton {entry} />\n      {/if}\n      {#if $ankiEnabledConfig && entry.type === "word"}\n'),
])

# the app (dictionary tab, share sheet) answers messages locally: teach it the pitch lookup too
edit(web / "platform/iosapp/runtimeShim.ts", [
    ('import { lookupFrequency } from "lib/frequencyLookup";\n',
     'import { lookupFrequency } from "lib/frequencyLookup";\nimport { lookupPitch } from "lib/pitchLookup";\n'),
    ('  if (msg.key === "minedLookup") {\n',
     '  if (msg.key === "pitch") {\n    return lookupPitch(msg.request as { term: string; reading: string });\n  }\n  if (msg.key === "minedLookup") {\n'),
])

# ======================= 2. JLPT table from word lists (CSV: expression, reading, ...) =======================
HEADERS = {"expression", "word", "kanji", "term", "単語", "vocab"}


def split_forms(s):
    s = re.sub(r"[（(][^）)]*[）)]", "", s)
    s = s.replace("〜", "").replace("～", "").replace("…", "")
    return [p.strip() for p in re.split(r"[/／、,;；]", s) if p.strip()]


table = {}


def put(key, level):
    # a word that is in several levels gets the easiest one (N5 before N1)
    if level > table.get(key, 0):
        table[key] = level


for n in (5, 4, 3, 2, 1):
    path = pathlib.Path("ours/custom-dict/jlpt_n%d.csv" % n)
    rows = 0
    if path.exists():
        with open(path, encoding="utf-8-sig", newline="") as f:
            for row in csv.reader(f):
                if not row or not row[0].strip() or row[0].strip().lower() in HEADERS:
                    continue
                forms = split_forms(row[0])
                readings = [to_hira(x) for x in split_forms(row[1])] if len(row) > 1 else []
                for form in forms:
                    for r in readings:
                        put(fnv(form + "|" + r), n)
                    if not readings:
                        put(fnv(form), n)
                    put(fnv(form + "|" + to_hira(form)), n)
                rows += 1
    print("JLPT N%d: %d words%s" % (n, rows, "" if rows else "  (no file: this level will not be highlighted)"))

flat = []
for key in sorted(table):
    flat += [key, table[key]]
blob = struct.pack("<%dI" % len(flat), *flat)
(web / "extension/background/jlptData.ts").write_text(
    'export const JLPT_DATA = "' + base64.b64encode(blob).decode("ascii") + '";\n'
)

(web / "lib/jlptLookup.ts").write_text('''import { JLPT_DATA } from "extension/background/jlptData";

let table: Uint32Array | undefined;

function decode(b64: string): Uint32Array {
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return new Uint32Array(bytes.buffer);
}

function hash(s: string): number {
  let h = 0x811c9dc5;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return h >>> 0;
}

/** Index of the record (2 numbers: key, level) */
function find(t: Uint32Array, key: number): number | undefined {
  let lo = 0;
  let hi = t.length / 2 - 1;
  while (lo <= hi) {
    const mid = (lo + hi) >>> 1;
    const k = t[mid * 2];
    if (k === key) return mid * 2;
    if (k < key) lo = mid + 1;
    else hi = mid - 1;
  }
  return undefined;
}

export interface JlptRequest {
  /** dictionary form */
  t: string;
  /** reading in hiragana */
  r: string;
}

/** JLPT level of each word: 5 = N5 (easiest) ... 1 = N1 (hardest), 0 = not in the lists. */
export function lookupJlpt(items: JlptRequest[]): number[] {
  if (table === undefined) table = decode(JLPT_DATA);
  const t = table;
  return items.map((it) => {
    const i = find(t, hash(it.t + "|" + it.r)) ?? (it.r ? undefined : find(t, hash(it.t)));
    return i === undefined ? 0 : t[i + 1];
  });
}
''')

edit(web / "extension/background/highlight.ts", [
    ('import { allMinedWords } from "extension/stats";\n',
     'import { allMinedWords } from "extension/stats";\nimport { lookupJlpt } from "lib/jlptLookup";\n'),
    ('handleMessage("hlMined", () => allMinedWords());\n',
     'handleMessage("hlMined", () => allMinedWords());\nhandleMessage("hlJlpt", (req) => lookupJlpt(req.items));\n'),
])
edit(web / "extension/browserApi.ts", [
    ("  hlMined: [void, string[]];\n",
     "  hlMined: [void, string[]];\n  hlJlpt: [{ items: { t: string; r: string }[] }, number[]];\n"),
])

# ======================= 3. settings keys =======================
edit(web / "lib/config.ts", [
    ('  "highlight.color": string;\n',
     '  "highlight.color": string;\n  "highlight.freq": boolean;\n  "highlight.jlpt.n5": boolean;\n  "highlight.jlpt.n4": boolean;\n  "highlight.jlpt.n3": boolean;\n  "highlight.jlpt.n2": boolean;\n  "highlight.jlpt.n1": boolean;\n'),
    ('  "highlight.color": "#ff9f0a",\n',
     '  "highlight.color": "#ff9f0a",\n  "highlight.freq": true,\n  "highlight.jlpt.n5": false,\n  "highlight.jlpt.n4": false,\n  "highlight.jlpt.n3": false,\n  "highlight.jlpt.n2": false,\n  "highlight.jlpt.n1": false,\n'),
])

# ======================= 4. frequency dictionaries are chosen by id (any number of them) =======================
edit(web / "lib/frequencyLookup.ts", [
    ('''  const table =
    dict === "wn"
      ? tables.find((t) => /webnovel/i.test(t.name))
      : tables.find((t) => !/webnovel/i.test(t.name));
''',
     '''  let index = FREQ_DICTS.findIndex((d) => d.id === dict);
  if (index < 0) {
    // values of the old settings: "wn" = WebNovel, anything else = the general list
    index =
      dict === "wn"
        ? FREQ_DICTS.findIndex((d) => /webnovel/i.test(d.name))
        : FREQ_DICTS.findIndex((d) => !/webnovel/i.test(d.name));
  }
  const table = index >= 0 ? tables[index] : undefined;
'''),
])

# ======================= 5. highlighting on the page: JLPT levels =======================
edit(web / "extension/content/freqHighlight.ts", [
    ('const HL_NAME = "yomikiri-freq";\n',
     'const HL_NAME = "yomikiri-freq";\nconst JLPT_COLORS: Record<number, string> = {\n  5: "#34c759",\n  4: "#0a84ff",\n  3: "#d9a400",\n  2: "#ff9500",\n  1: "#ff3b30",\n};\n\ninterface Painter {\n  add(range: Range): unknown;\n  delete(range: Range): unknown;\n}\n'),
    ('interface Mark {\n  range: Range;\n  words: string[];\n}',
     'interface Mark {\n  range: Range;\n  words: string[];\n  hl: Painter;\n}'),
    ('function installStyle(color: string): boolean {\n  const css = "::highlight(" + HL_NAME + ") { color: " + color + "; }";\n',
     'function installStyle(css: string): boolean {\n'),
    ('  const dict = config.get("highlight.dict") === "wn" ? "wn" : "main";\n',
     '''  const freqOn = config.get("highlight.freq");
  const jlptFlags: [number, boolean][] = [
    [5, config.get("highlight.jlpt.n5")],
    [4, config.get("highlight.jlpt.n4")],
    [3, config.get("highlight.jlpt.n3")],
    [2, config.get("highlight.jlpt.n2")],
    [1, config.get("highlight.jlpt.n1")],
  ];
  const jlptLevels = new Set(jlptFlags.filter(([, on]) => on).map(([n]) => n));
  if (!freqOn && jlptLevels.size === 0) return;

  const dict = String(config.get("highlight.dict"));
'''),
    ('  if (!installStyle(color)) return;\n\n  const highlight = new HighlightClass();\n  css.highlights.set(HL_NAME, highlight);\n',
     '''  let styles = "::highlight(" + HL_NAME + ") { color: " + color + "; }";
  for (const n of jlptLevels) {
    styles += " ::highlight(yomikiri-jlpt-" + n + ") { color: " + JLPT_COLORS[n] + "; }";
  }
  if (!installStyle(styles)) return;

  const highlight: Painter = new HighlightClass();
  css.highlights.set(HL_NAME, highlight);
  const jlptHighlights = new Map<number, Painter>();
  for (const n of jlptLevels) {
    const h: Painter = new HighlightClass();
    css.highlights.set("yomikiri-jlpt-" + n, h);
    jlptHighlights.set(n, h);
  }
'''),
    ('        highlight.delete(marks[i].range);\n',
     '        marks[i].hl.delete(marks[i].range);\n'),
    ('      slice.forEach((k, j) => rankCache.set(k, ranks[j] ?? 0));\n    }\n  }\n',
     '''      slice.forEach((k, j) => rankCache.set(k, ranks[j] ?? 0));
    }
  }

  const jlptCache = new Map<string, number>();

  async function fillJlpt(items: RankItem[]): Promise<void> {
    const missing = new Map<string, RankItem>();
    for (const it of items) {
      const key = it.t + "|" + it.r;
      if (!jlptCache.has(key)) missing.set(key, it);
    }
    const keys = Array.from(missing.keys());
    for (let i = 0; i < keys.length; i += 200) {
      const slice = keys.slice(i, i + 200);
      const levels = await sendToBackground<number[]>("hlJlpt", {
        items: slice.map((k) => {
          const it = missing.get(k) as RankItem;
          return { t: it.t, r: it.r };
        }),
      });
      if (!Array.isArray(levels)) continue;
      slice.forEach((k, j) => jlptCache.set(k, levels[j] ?? 0));
    }
  }
'''),
    ('      await fillRanks(found.map((f) => f.item));\n',
     '      if (freqOn) await fillRanks(found.map((f) => f.item));\n      if (jlptLevels.size > 0) await fillJlpt(found.map((f) => f.item));\n'),
    ('''        const rank = rankCache.get(f.item.t + "|" + f.item.r + "|" + (f.item.k ? "1" : "0")) ?? 0;
        if (rank < lo || rank > hi) continue;
        if (mined.has(f.base) || mined.has(f.surface)) continue;
        const range = makeRange(block.parts, f.begin, f.end);
        if (range === null) continue;
        highlight.add(range);
        marks.push({ range, words: [f.base, f.surface] });
''',
     '''        if (mined.has(f.base) || mined.has(f.surface)) continue;
        let target: Painter | undefined;
        const level = jlptCache.get(f.item.t + "|" + f.item.r) ?? 0;
        if (level > 0 && jlptLevels.has(level)) {
          target = jlptHighlights.get(level);
        } else if (freqOn) {
          const rank = rankCache.get(f.item.t + "|" + f.item.r + "|" + (f.item.k ? "1" : "0")) ?? 0;
          if (rank >= lo && rank <= hi) target = highlight;
        }
        if (target === undefined) continue;
        const range = makeRange(block.parts, f.begin, f.end);
        if (range === null) continue;
        target.add(range);
        marks.push({ range, words: [f.base, f.surface], hl: target });
'''),
])

# ======================= 6. settings page with explanations =======================
(web / "components/options/groups/GroupHighlight.svelte").write_text('''<script lang="ts">
  import OptionNumber from "../items/OptionNumber.svelte";
  import OptionSelect from "../items/OptionSelect.svelte";
  import OptionToggle from "../items/OptionToggle.svelte";
  import GroupedOptions from "../GroupedOptions.svelte";
  import Config from "lib/config";
  import { FREQ_DICT_LIST } from "lib/freqDictList";

  const config = Config.using();
  const enabledConfig = config.store("highlight.enabled");
  const freqConfig = config.store("highlight.freq");
  const dictConfig = config.store("highlight.dict");
  const minConfig = config.store("highlight.min");
  const maxConfig = config.store("highlight.max");
  const colorConfig = config.store("highlight.color");
  const n5Config = config.store("highlight.jlpt.n5");
  const n4Config = config.store("highlight.jlpt.n4");
  const n3Config = config.store("highlight.jlpt.n3");
  const n2Config = config.store("highlight.jlpt.n2");
  const n1Config = config.store("highlight.jlpt.n1");

  function resolveDict(value: string): string {
    if (FREQ_DICT_LIST.some((d) => d.id === value)) return value;
    const web = FREQ_DICT_LIST.find((d) => /webnovel/i.test(d.name));
    const general = FREQ_DICT_LIST.find((d) => !/webnovel/i.test(d.name));
    const found = value === "wn" ? web : general;
    return (found ?? FREQ_DICT_LIST[0])?.id ?? value;
  }

  // the old settings stored "main" / "wn": switch them to the id of a dictionary
  $: if (
    FREQ_DICT_LIST.length > 0 &&
    !FREQ_DICT_LIST.some((d) => d.id === $dictConfig)
  ) {
    $dictConfig = resolveDict($dictConfig);
  }

  const dictOptions: [string, string][] = FREQ_DICT_LIST.map((d) => [d.id, d.label]);

  $: from = Math.max(1, Math.min(Number($minConfig), Number($maxConfig)));
  $: to = Math.max(Number($minConfig), Number($maxConfig));
</script>

<GroupedOptions title="Подсветка слов">
  <OptionToggle bind:value={$enabledConfig} title="Подсвечивать слова">
    Меняет цвет слов в тексте на странице в Safari. Слова, которые вы уже
    добавили в Anki, не подсвечиваются. После изменения настроек обновите
    страницу.
  </OptionToggle>
</GroupedOptions>

<GroupedOptions title="Подсветка по частотности">
  <OptionToggle bind:value={$freqConfig} title="Подсвечивать по частотности">
    Частотность — это место слова в списке самых употребимых слов. Место 1 —
    самое частое слово, а чем больше число, тем реже слово встречается.
  </OptionToggle>
  {#if FREQ_DICT_LIST.length > 0}
    <OptionSelect
      bind:selected={$dictConfig}
      options={dictOptions}
      title="Словарь частот"
    >
      По какому списку определяется место слова. Здесь показаны все
      загруженные частотные словари.
    </OptionSelect>
  {/if}
  <OptionNumber bind:value={$minConfig} title="От места" min={1} max={500000}>
    Слова, которые встречаются чаще этого места, подсвечиваться не будут: вы
    их, скорее всего, уже знаете. Например, при значении 3000 первые 3000
    самых частых слов остаются без подсветки.
  </OptionNumber>
  <OptionNumber bind:value={$maxConfig} title="До места" min={1} max={500000}>
    Слова, которые встречаются реже этого места, подсвечиваться не будут:
    они слишком редкие. Например, при значении 8000 слова за пределами первых
    8000 остаются без подсветки.
  </OptionNumber>
  <div class="note">
    Сейчас подсвечиваются слова с места {from} по место {to}. Слова, которых
    нет в выбранном словаре, не подсвечиваются.
  </div>
  <OptionSelect
    bind:selected={$colorConfig}
    options={[
      ["#ff9f0a", "Оранжевый"],
      ["#ffd60a", "Жёлтый"],
      ["#30d158", "Зелёный"],
      ["#64d2ff", "Голубой"],
      ["#bf5af2", "Фиолетовый"],
      ["#ff375f", "Красный"],
      ["#ffffff", "Белый"],
    ]}
    title="Цвет подсветки"
  >
    Цвет текста слов, подсвеченных по частотности.
  </OptionSelect>
</GroupedOptions>

<GroupedOptions title="Подсветка по уровню JLPT">
  <div class="note">
    Отметьте уровни, слова которых нужно подсвечивать. Например, если вы на
    уровне N4: отметьте N4 и N3, чтобы видеть слова, которые стоит выучить, а
    N2 и N1 не отмечайте, чтобы слишком сложные слова не отвлекали. У каждого
    уровня свой цвет. Если слово подходит и под уровень JLPT, и под
    частотность, используется цвет уровня. Списки слов по уровням
    неофициальные, их составило сообщество.
  </div>
  <OptionToggle bind:value={$n5Config} title="N5 🟢">Начальный уровень</OptionToggle>
  <OptionToggle bind:value={$n4Config} title="N4 🔵">Базовый уровень</OptionToggle>
  <OptionToggle bind:value={$n3Config} title="N3 🟡">Средний уровень</OptionToggle>
  <OptionToggle bind:value={$n2Config} title="N2 🟠">Выше среднего</OptionToggle>
  <OptionToggle bind:value={$n1Config} title="N1 🔴">Продвинутый уровень</OptionToggle>
</GroupedOptions>

<style>
  .note {
    margin: 0 8px;
    padding: 8px 0;
    font-size: 1rem;
    color: var(--text-light);
  }
</style>
''')
print("audio / JLPT / settings patch OK")
