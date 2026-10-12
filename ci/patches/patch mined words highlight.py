# Moved out of build-ios-v141-player.yml, step "Patch mined words list, frequency highlighting, short badges, translation" (GitHub limits workflow files to 500 KB).
import pathlib

root = pathlib.Path("src/safari")
web = pathlib.Path("src/main/src")


def replace_once(text, old, new, label, count=1):
    assert text.count(old) == count, "pattern not found %d times: %s (%d)" % (count, label, text.count(old))
    return text.replace(old, new)


def edit(path, pairs):
    p = pathlib.Path(path)
    s = p.read_text()
    for old, new, count in pairs:
        s = replace_once(s, old, new, str(path) + " :: " + old[:40], count)
    p.write_text(s)


MINED_SWIFT = r'''
// MARK: - Mined words list

private func statIsKanji(_ scalar: Unicode.Scalar) -> Bool {
    return (0x3400 ... 0x4DBF).contains(scalar.value) || (0x4E00 ... 0x9FFF).contains(scalar.value)
}

private func statSectionTitle(_ key: String) -> String {
    if key == statKey(daysAgo: 0) {
        return "Сегодня"
    }
    if key == statKey(daysAgo: 1) {
        return "Вчера"
    }
    guard let date = statDateFormatter.date(from: key) else {
        return key
    }
    let formatter = DateFormatter()
    formatter.locale = Locale(identifier: "ru_RU")
    formatter.dateFormat = "d MMMM yyyy"
    return formatter.string(from: date)
}

extension StatsViewModel {
    /// Rewrites the `mined` list of every day, keeps all other statistics untouched.
    fileprivate func rewriteMined(_ transform: (inout [String]) -> Void) {
        guard let json = try? Storage.stats.get(),
              let data = json.data(using: .utf8),
              var root = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any],
              var rawDays = root["days"] as? [String: Any]
        else {
            return
        }
        for (key, value) in rawDays {
            guard var day = value as? [String: Any] else {
                continue
            }
            var mined = (day["mined"] as? [String]) ?? []
            transform(&mined)
            var kanji: [String] = []
            for word in mined {
                for scalar in word.unicodeScalars where statIsKanji(scalar) {
                    let letter = String(scalar)
                    if !kanji.contains(letter) {
                        kanji.append(letter)
                    }
                }
            }
            day["mined"] = mined
            day["kanji"] = kanji
            rawDays[key] = day
        }
        root["days"] = rawDays
        guard let out = try? JSONSerialization.data(withJSONObject: root),
              let text = String(data: out, encoding: .utf8)
        else {
            return
        }
        _ = try? Storage.stats.set(text)
        reload()
    }

    func deleteMined(_ word: String) {
        rewriteMined { mined in
            mined.removeAll { $0 == word }
        }
    }

    func deleteAllMined() {
        rewriteMined { mined in
            mined.removeAll()
        }
    }
}

struct MinedSection: Identifiable {
    let id: String
    let words: [String]
}

struct MinedWordsView: View {
    @ObservedObject var model: StatsViewModel
    @Environment(\.dismiss) private var dismiss
    @State private var query = ""
    @State private var confirmClear = false

    private var sections: [MinedSection] {
        var result: [MinedSection] = []
        for key in model.days.keys.sorted(by: >) {
            guard let day = model.days[key] else {
                continue
            }
            var words: [String] = []
            for word in day.mined.reversed() where query.isEmpty || word.localizedCaseInsensitiveContains(query) {
                words.append(word)
            }
            if !words.isEmpty {
                result.append(MinedSection(id: key, words: words))
            }
        }
        return result
    }

    private var total: Int {
        return model.summary(lastDays: nil).minedWords
    }

    var body: some View {
        NavigationView {
            List {
                ForEach(sections) { section in
                    Section(header: Text(statSectionTitle(section.id))) {
                        ForEach(section.words, id: \.self) { word in
                            Text(word)
                                .font(.system(size: 20))
                                .padding(.vertical, 4)
                                .swipeActions(edge: .trailing, allowsFullSwipe: true) {
                                    Button(role: .destructive) {
                                        model.deleteMined(word)
                                    } label: {
                                        Label("Удалить", systemImage: "trash")
                                    }
                                }
                                .contextMenu {
                                    Button {
                                        UIPasteboard.general.string = word
                                    } label: {
                                        Label("Копировать", systemImage: "doc.on.doc")
                                    }
                                    Button(role: .destructive) {
                                        model.deleteMined(word)
                                    } label: {
                                        Label("Удалить", systemImage: "trash")
                                    }
                                }
                        }
                    }
                }
            }
            .listStyle(.insetGrouped)
            .searchable(text: $query, prompt: "Поиск")
            .overlay(
                Group {
                    if sections.isEmpty {
                        Text(query.isEmpty ? "Пока нет добавленных слов" : "Ничего не найдено")
                            .foregroundColor(.secondary)
                    }
                }
            )
            .navigationTitle("Добавленные слова: " + statNumber(total))
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Готово") {
                        dismiss()
                    }
                }
                ToolbarItem(placement: .navigationBarTrailing) {
                    Menu {
                        Button(role: .destructive) {
                            confirmClear = true
                        } label: {
                            Label("Удалить все слова", systemImage: "trash")
                        }
                    } label: {
                        Image(systemName: "ellipsis.circle")
                    }
                }
            }
            .confirmationDialog("Удалить все добавленные слова?", isPresented: $confirmClear, titleVisibility: .visible) {
                Button("Удалить", role: .destructive) {
                    model.deleteAllMined()
                }
                Button("Отмена", role: .cancel) {}
            }
        }
        .preferredColorScheme(.dark)
    }
}
'''
FREQ_TS = r'''/**
 * Colors words of the page by their frequency rank.
 *
 * - The text of every paragraph is tokenized by the app (dictionary forms).
 * - The rank of each word is looked up in the chosen Jiten dictionary.
 * - Words with rank inside the chosen range get another color.
 *   Words that are already in Anki are not colored.
 *
 * The page is not modified. Colors are applied with the CSS Custom Highlight API.
 */
import { Backend } from "@platform/backend";
import { Config } from "lib/config";

const HAS_JP = /[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff]/;
const KANJI = /[\u3400-\u4dbf\u4e00-\u9fff]/;
const BLOCKS = "p, li, h1, h2, h3, h4, h5, h6, blockquote, dd, dt, td, pre, div";
const SKIP =
  "nav, header, footer, aside, button, a, form, select, label, summary, script, style, noscript, " +
  "[role='navigation'], [role='button'], [role='menu'], [role='menuitem'], [role='tab']";
const SENTENCE_RE = /[^。！？!?\n]*[。！？!?]+[」』）)”]*|[^。！？!?\n]+/g;
const CONTENT_POS = new Set(["名詞", "動詞", "形容詞", "形状詞", "副詞"]);
const CHUNK_MAX = 300;
const HL_NAME = "yomikiri-freq";
const STYLE_ID = "yomikiri-freq-style";
const MINED_REFRESH_MS = 15000;

interface TextPart {
  node: Text;
  start: number;
}

interface Block {
  el: Element;
  parts: TextPart[];
  text: string;
  state: "new" | "queued" | "done";
}

interface Mark {
  range: Range;
  words: string[];
}

interface RankItem {
  t: string;
  r: string;
  k: boolean;
}

function sendToBackground<T>(
  key: string,
  request: unknown,
): Promise<T | undefined> {
  return new Promise((resolve) => {
    try {
      chrome.runtime.sendMessage(
        { key, request },
        (resp: { success?: boolean; resp?: T } | undefined) => {
          void chrome.runtime.lastError;
          resolve(resp?.success === true ? resp.resp : undefined);
        },
      );
    } catch (_e) {
      resolve(undefined);
    }
  });
}

function katakanaToHiragana(s: string): string {
  let out = "";
  for (const ch of s) {
    const c = ch.codePointAt(0) ?? 0;
    out += c >= 0x30a1 && c <= 0x30f6 ? String.fromCodePoint(c - 0x60) : ch;
  }
  return out;
}

function codePointOffsets(s: string): number[] {
  const offsets: number[] = [];
  let i = 0;
  for (const ch of s) {
    offsets.push(i);
    i += ch.length;
  }
  offsets.push(i);
  return offsets;
}

function splitChunks(text: string): { text: string; start: number }[] {
  const chunks: { text: string; start: number }[] = [];
  let begin = -1;
  let end = 0;
  for (const m of text.matchAll(SENTENCE_RE)) {
    const idx = m.index ?? 0;
    if (begin >= 0 && idx + m[0].length - begin > CHUNK_MAX) {
      chunks.push({ text: text.slice(begin, end), start: begin });
      begin = -1;
    }
    if (begin < 0) begin = idx;
    end = idx + m[0].length;
  }
  if (begin >= 0) chunks.push({ text: text.slice(begin, end), start: begin });
  return chunks;
}

function buildBlock(el: Element): Block | null {
  const parts: TextPart[] = [];
  let text = "";
  const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, {
    acceptNode: (n) =>
      n.parentElement?.closest("rt, rp, script, style, noscript") != null
        ? NodeFilter.FILTER_REJECT
        : NodeFilter.FILTER_ACCEPT,
  });
  for (let n = walker.nextNode(); n !== null; n = walker.nextNode()) {
    parts.push({ node: n as Text, start: text.length });
    text += (n as Text).data;
  }
  if (!HAS_JP.test(text)) return null;
  return { el, parts, text, state: "new" };
}

function locate(
  parts: TextPart[],
  pos: number,
  forEnd: boolean,
): { node: Text; offset: number } | null {
  let lo = 0;
  let hi = parts.length - 1;
  let found = -1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    const ok = forEnd ? parts[mid].start < pos : parts[mid].start <= pos;
    if (ok) {
      found = mid;
      lo = mid + 1;
    } else {
      hi = mid - 1;
    }
  }
  if (found < 0) return null;
  const part = parts[found];
  const offset = pos - part.start;
  if (offset > part.node.data.length) return null;
  return { node: part.node, offset };
}

function makeRange(parts: TextPart[], begin: number, end: number): Range | null {
  const a = locate(parts, begin, false);
  const b = locate(parts, end, true);
  if (a === null || b === null) return null;
  try {
    const range = document.createRange();
    range.setStart(a.node, a.offset);
    range.setEnd(b.node, b.offset);
    return range;
  } catch (_e) {
    return null;
  }
}

function installStyle(color: string): boolean {
  const css = "::highlight(" + HL_NAME + ") { color: " + color + "; }";
  let style = document.getElementById(STYLE_ID) as HTMLStyleElement | null;
  if (style === null) {
    style = document.createElement("style");
    style.id = STYLE_ID;
    (document.head ?? document.documentElement).appendChild(style);
  }
  style.textContent = css;
  if (style.sheet !== null) return true;
  try {
    const sheet = new CSSStyleSheet();
    sheet.replaceSync(css);
    document.adoptedStyleSheets = [...document.adoptedStyleSheets, sheet];
    return true;
  } catch (_e) {
    return false;
  }
}

async function start(): Promise<void> {
  if (window.top !== window) return;
  if (
    typeof chrome === "undefined" ||
    typeof chrome.runtime?.sendMessage !== "function"
  ) {
    return;
  }
  // eslint-disable-next-line
  const css: any = typeof CSS !== "undefined" ? CSS : undefined;
  // eslint-disable-next-line
  const HighlightClass: any = (globalThis as any).Highlight;
  if (css?.highlights === undefined || HighlightClass === undefined) return;

  const config = await Config.instance.get();
  if (!config.get("highlight.enabled") || !config.get("state.enabled")) return;

  const dict = config.get("highlight.dict") === "wn" ? "wn" : "main";
  const a = Number(config.get("highlight.min"));
  const b = Number(config.get("highlight.max"));
  const lo = Math.max(1, Math.min(a, b));
  const hi = Math.max(a, b);
  let color = String(config.get("highlight.color"));
  if (!/^#[0-9a-fA-F]{3,8}$/.test(color)) color = "#ff9f0a";
  if (!installStyle(color)) return;

  const highlight = new HighlightClass();
  css.highlights.set(HL_NAME, highlight);
  const marks: Mark[] = [];
  const rankCache = new Map<string, number>();
  let mined = new Set<string>();
  let minedAt = 0;

  async function refreshMined(): Promise<void> {
    const list = await sendToBackground<string[]>("hlMined", undefined);
    if (!Array.isArray(list)) return;
    mined = new Set(list);
    minedAt = Date.now();
    for (let i = marks.length - 1; i >= 0; i--) {
      if (marks[i].words.some((w) => mined.has(w))) {
        highlight.delete(marks[i].range);
        marks.splice(i, 1);
      }
    }
  }

  async function fillRanks(items: RankItem[]): Promise<void> {
    const missing = new Map<string, RankItem>();
    for (const it of items) {
      const key = it.t + "|" + it.r + "|" + (it.k ? "1" : "0");
      if (!rankCache.has(key)) missing.set(key, it);
    }
    const keys = Array.from(missing.keys());
    for (let i = 0; i < keys.length; i += 200) {
      const slice = keys.slice(i, i + 200);
      const ranks = await sendToBackground<number[]>("hlRanks", {
        dict,
        items: slice.map((k) => missing.get(k) as RankItem),
      });
      if (!Array.isArray(ranks)) continue;
      slice.forEach((k, j) => rankCache.set(k, ranks[j] ?? 0));
    }
  }

  async function processBlock(block: Block): Promise<void> {
    if (Date.now() - minedAt > MINED_REFRESH_MS) await refreshMined();
    for (const chunk of splitChunks(block.text)) {
      if (!HAS_JP.test(chunk.text)) continue;
      let tokens;
      try {
        tokens = (await Backend.tokenize({ text: chunk.text, charAt: 0 })).tokens;
      } catch (_e) {
        continue;
      }
      const offsets = codePointOffsets(chunk.text);
      const found: { begin: number; end: number; base: string; surface: string; item: RankItem }[] = [];
      for (const tok of tokens) {
        if (!CONTENT_POS.has(tok.pos)) continue;
        const from = tok.start;
        const to = from + Array.from(tok.text).length;
        if (to >= offsets.length) continue;
        const surface = chunk.text.slice(offsets[from], offsets[to]);
        const base = tok.base !== "" ? tok.base : tok.text;
        found.push({
          begin: chunk.start + offsets[from],
          end: chunk.start + offsets[to],
          base,
          surface,
          item: { t: base, r: katakanaToHiragana(tok.reading), k: !KANJI.test(surface) },
        });
      }
      await fillRanks(found.map((f) => f.item));
      for (const f of found) {
        const rank = rankCache.get(f.item.t + "|" + f.item.r + "|" + (f.item.k ? "1" : "0")) ?? 0;
        if (rank < lo || rank > hi) continue;
        if (mined.has(f.base) || mined.has(f.surface)) continue;
        const range = makeRange(block.parts, f.begin, f.end);
        if (range === null) continue;
        highlight.add(range);
        marks.push({ range, words: [f.base, f.surface] });
      }
    }
    block.state = "done";
  }

  const queue: Block[] = [];
  let running = 0;
  function pump(): void {
    while (running < 2 && queue.length > 0) {
      const block = queue.shift() as Block;
      running++;
      processBlock(block)
        .catch((e) => console.error("Highlight failed", e))
        .finally(() => {
          running--;
          pump();
        });
    }
  }

  const blocks = new WeakMap<Element, Block>();
  const rejected = new WeakSet<Element>();
  const io = new IntersectionObserver(
    (entries) => {
      for (const e of entries) {
        const block = blocks.get(e.target);
        if (block === undefined || !e.isIntersecting || block.state !== "new") continue;
        block.state = "queued";
        queue.push(block);
      }
      pump();
    },
    { rootMargin: "1500px" },
  );

  function scan(): void {
    for (const el of Array.from(document.querySelectorAll(BLOCKS))) {
      if (blocks.has(el) || rejected.has(el)) continue;
      if (el.querySelector(BLOCKS) !== null) continue;
      if (el.closest(SKIP) !== null) {
        rejected.add(el);
        continue;
      }
      const block = buildBlock(el);
      if (block === null) {
        rejected.add(el);
        continue;
      }
      blocks.set(el, block);
      io.observe(el);
    }
  }

  let scanTimer: number | undefined;
  scan();
  new MutationObserver(() => {
    if (scanTimer !== undefined) return;
    scanTimer = window.setTimeout(() => {
      scanTimer = undefined;
      scan();
    }, 2000);
  }).observe(document.documentElement, { childList: true, subtree: true });
}

start().catch((e) => console.error("Frequency highlight could not start", e));
'''
GROUP_SVELTE = r'''<script lang="ts">
  import OptionNumber from "../items/OptionNumber.svelte";
  import OptionSelect from "../items/OptionSelect.svelte";
  import OptionToggle from "../items/OptionToggle.svelte";
  import GroupedOptions from "../GroupedOptions.svelte";
  import Config from "lib/config";

  const config = Config.using();
  const enabledConfig = config.store("highlight.enabled");
  const dictConfig = config.store("highlight.dict");
  const minConfig = config.store("highlight.min");
  const maxConfig = config.store("highlight.max");
  const colorConfig = config.store("highlight.color");
</script>

<GroupedOptions title="Подсветка слов по частотности">
  <OptionToggle bind:value={$enabledConfig} title="Подсвечивать слова">
    Меняет цвет слов на странице в Safari. Слова, уже добавленные в Anki, не
    подсвечиваются. После изменения настроек обновите страницу.
  </OptionToggle>
  <OptionSelect
    bind:selected={$dictConfig}
    options={[
      ["main", "Jiten"],
      ["wn", "Jiten(WN)"],
    ]}
    title="Словарь частот"
  >
    По какому словарю считать место слова
  </OptionSelect>
  <OptionNumber bind:value={$minConfig} title="От места" min={1} max={500000}>
    Чем меньше номер, тем чаще слово
  </OptionNumber>
  <OptionNumber bind:value={$maxConfig} title="До места" min={1} max={500000}>
    Например, от 3000 до 8000
  </OptionNumber>
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
    Цвет текста подсвеченных слов
  </OptionSelect>
</GroupedOptions>
'''

# ======================= Swift: list of mined words under the diagnostics button =======================
p = root / "iOS (App)/HelpView.swift"
s = p.read_text()
s = replace_once(s, '    @State private var diag = ""\n', '    @State private var diag = ""\n    @State private var showMined = false\n', "mined state")
s = replace_once(s, '''                    .buttonStyle(.bordered)
                }
            }
            .padding(16)''', '''                    .buttonStyle(.bordered)
                }

                Button {
                    showMined = true
                } label: {
                    HStack {
                        Text("Добавленные слова")
                        Spacer()
                        Text(statNumber(model.summary(lastDays: nil).minedWords))
                            .foregroundColor(.secondary)
                        Image(systemName: "chevron.right")
                            .font(.footnote.weight(.semibold))
                            .foregroundColor(.secondary)
                    }
                    .padding(14)
                    .frame(maxWidth: .infinity)
                    .background(Color(.secondarySystemBackground))
                    .cornerRadius(14)
                }
                .buttonStyle(.plain)
            }
            .padding(16)''', "mined row")
s = replace_once(s, "        .onAppear {\n            sharedStorageHeartbeat()\n",
                 "        .sheet(isPresented: $showMined, onDismiss: { model.reload() }) {\n            MinedWordsView(model: model)\n        }\n        .onAppear {\n            sharedStorageHeartbeat()\n", "mined sheet")
s = s.rstrip("\n") + "\n" + MINED_SWIFT
p.write_text(s)

# ======================= settings: highlight by frequency =======================
edit(web / "lib/config.ts", [
    ('  "general.tooltip_max_height": number;\n',
     '  "general.tooltip_max_height": number;\n  "highlight.enabled": boolean;\n  /** "main" = Jiten, "wn" = Jiten (WebNovel) */\n  "highlight.dict": string;\n  "highlight.min": number;\n  "highlight.max": number;\n  "highlight.color": string;\n', 1),
    ('  "general.tooltip_max_height": 300,\n',
     '  "general.tooltip_max_height": 300,\n  "highlight.enabled": false,\n  "highlight.dict": "main",\n  "highlight.min": 3000,\n  "highlight.max": 8000,\n  "highlight.color": "#ff9f0a",\n', 1),
])
(web / "components/options/groups/GroupHighlight.svelte").write_text(GROUP_SVELTE)
edit(web / "components/options/MainColumn.svelte", [
    ('  import GroupAppearance from "./groups/GroupAppearance.svelte";\n',
     '  import GroupAppearance from "./groups/GroupAppearance.svelte";\n  import GroupHighlight from "./groups/GroupHighlight.svelte";\n', 1),
    ("  <GroupAppearance />\n", "  <GroupAppearance />\n  <GroupHighlight />\n", 1),
])

# ======================= frequency ranks for many words at once =======================
p = web / "lib/frequencyLookup.ts"
s = p.read_text()
s = s.rstrip("\n") + r'''

export interface RankRequest {
  /** dictionary form */
  t: string;
  /** reading in hiragana */
  r: string;
  /** the word is written in kana in the text */
  k: boolean;
}

/** Rank of each word in one dictionary ("wn" = WebNovel, "main" = the other one). 0 = no rank. */
export function lookupRanks(dict: string, items: RankRequest[]): number[] {
  if (tables === undefined) {
    tables = FREQ_DICTS.map((d) => ({ name: d.name, data: decode(d.data) }));
  }
  const table =
    dict === "wn"
      ? tables.find((t) => /webnovel/i.test(t.name))
      : tables.find((t) => !/webnovel/i.test(t.name));
  if (table === undefined) return items.map(() => 0);
  return items.map((it) => {
    const i =
      find(table.data, hash(it.t + "|" + it.r)) ?? (it.r ? undefined : find(table.data, hash(it.t)));
    if (i === undefined) return 0;
    const kanjiRank = table.data[i + 1];
    const kanaRank = table.data[i + 2];
    if (it.k) return kanaRank > 0 ? kanaRank : kanjiRank;
    return kanjiRank > 0 ? kanjiRank : kanaRank;
  });
}
'''
p.write_text(s)

edit(web / "extension/browserApi.ts", [
    ("  // ios\n  loadConfig: [void, StoredConfiguration];\n",
     '  hlRanks: [\n    { dict: string; items: { t: string; r: string; k: boolean }[] },\n    number[],\n  ];\n  hlMined: [void, string[]];\n  // ios\n  loadConfig: [void, StoredConfiguration];\n', 1),
])
edit(web / "extension/stats.ts", [
    ("async function allMinedWords(): Promise<string[]> {", "export async function allMinedWords(): Promise<string[]> {", 1),
])
(web / "extension/background/highlight.ts").write_text('''import { handleMessage } from "extension/browserApi";
import { lookupRanks } from "lib/frequencyLookup";
import { allMinedWords } from "extension/stats";

handleMessage("hlRanks", (req) => lookupRanks(req.dict, req.items));
handleMessage("hlMined", () => allMinedWords());
''')
edit(web / "extension/background/index.ts", [
    ('import "./statsHandlers";\n', 'import "./statsHandlers";\nimport "./highlight";\n', 1),
])
(web / "extension/content/freqHighlight.ts").write_text(FREQ_TS)
edit(web / "extension/content/index.ts", [
    ('import "./readingStats";\n', 'import "./readingStats";\nimport "./freqHighlight";\n', 1),
])

# ======================= short badges =======================
edit(web / "components/dictionary/Badges.svelte", [
    ('<div class="badge in-anki">в Anki</div>', '<div class="badge in-anki">Anki</div>', 1),
    ('<div class="badge freq">{f.name}: {f.values.join(", ")}</div>', '<div class="badge freq">{shortName(f.name)}: {f.values.join(", ")}</div>', 1),
    ("  $: isCommon = ", '  function shortName(name: string): string {\n    return name.replace(/\\s*\\(WebNovel\\)/i, "(WN)");\n  }\n\n  $: isCommon = ', 1),
])

# ======================= the rest of the translation =======================
c = web / "components"
edit(c / "anki/AddToAnki.svelte", [
    ('label="Back"', 'label="Назад"', 1),
    ('<div class="title-center">Add to Anki</div>', '<div class="title-center">Добавить в Anki</div>', 1),
    ('        label="Add"\n', '        label="Добавить"\n', 1),
])
edit(c / "dictionary/DicEntryOtherForms.svelte", [("Other Forms", "Другие формы", 1)])
edit(c / "options/ankiTemplate/LoadAnkiTemplate.svelte", [("Connecting to Anki...", "Подключение к Anki...", 1)])
edit(c / "options/ankiTemplate/ModalAnkiTemplate.svelte", [('title="Anki Template"', 'title="Шаблон Anki"', 1)])
edit(c / "options/ankiTemplate/AnkiTemplateEdit.svelte", [
    ('<div class="item-title">Deck</div>', '<div class="item-title">Колода</div>', 1),
    ('<div class="item-title">Note Type</div>', '<div class="item-title">Тип заметки</div>', 1),
    ('<div class="tags-label">Tags</div>', '<div class="tags-label">Теги</div>', 1),
    ("(Invalid) {prevDeck}", "(недопустимо) {prevDeck}", 1),
    ("(Invalid) {prevNotetype}", "(недопустимо) {prevNotetype}", 1),
    ('title="Get Anki note types designed to work well with Yomikiri"', 'title="Готовые типы заметок Anki для Yomikiri"', 1),
    (">Get Yomikiri Note Types</a", ">Типы заметок Yomikiri</a", 1),
    ('title="separated by space"', 'title="через пробел"', 1),
])
edit(c / "options/ankiTemplate/AnkiTemplateFieldOptionsEdit.svelte", [
    ("No configurable options", "Нет настраиваемых параметров", 1),
    ('"Form used in sentence"', '"Форма из предложения"', 1),
    ('"Dictionary conjugation form (ーる）"', '"Словарная форма спряжения (ーる）"', 1),
    ('"Main form used in dictionary"', '"Основная форма из словаря"', 1),
    ('title="Form"', 'title="Форма"', 1),
    ("Which form of word to use.", "Какую форму слова использовать.", 1),
    ('title="Selected Word Style"', 'title="Стиль выбранного слова"', 1),
    ("Style selected word within sentence", "Как выделять выбранное слово в предложении", 1),
    ('title="Style"', 'title="Стиль"', 1),
    ("Whether to use furigana, or convert word to kana.", "Использовать фуригану или преобразовать слово в кану.", 1),
    ("'furigana-anki' outputs", "'furigana-anki' выдаёт", 1),
    ("<h4>Full Entry</h4>", "<h4>Вся статья</h4>", 1),
    ("<p>Below options apply if the whole dictionary entry is added to Anki.</p>", "<p>Параметры ниже применяются, если в Anki добавляется вся словарная статья.</p>", 1),
    ('"Numbered list"', '"Нумерованный список"', 1),
    ('"Bulleted list"', '"Маркированный список"', 1),
    ('"Single line"', '"Одна строка"', 1),
    ('"Yomichan style"', '"Стиль Yomichan"', 1),
    ('title="Format"', 'title="Формат"', 1),
    ("How the meanings should be formatted.", "Как оформлять значения.", 1),
    ('title="Part of Speech"', 'title="Часть речи"', 2),
    ("Include part of speech", "Добавлять часть речи", 2),
    ('title="Max Items Per Meaning"', 'title="Макс. переводов на значение"', 1),
    ("Use the first N glossaries per meaning. Use 0 to set no limit.", "Первые N переводов на значение. 0 — без ограничений.", 1),
    ('<h4 class="second">Selected Meaning</h4>', '<h4 class="second">Выбранное значение</h4>', 1),
    ("When you select a meaning in the dictionary entry,", "Когда вы выбираете значение в словарной статье,", 1),
    ("<IconAddCircleOutline /> button turns", "<IconAddCircleOutline /> кнопка становится", 1),
    ("        orange.\n", "        оранжевой.\n", 1),
    ("        Clicking\n", "        Нажатие на\n", 1),
    ("        will let you add only that meaning of the word to Anki.\n", "        добавит в Anki только это значение слова.\n", 1),
    ("<p>Below options apply for such case.</p>", "<p>Параметры ниже применяются в этом случае.</p>", 1),
    ('title="Max Items"', 'title="Макс. переводов"', 1),
    ("Use the first N glossaries. Use 0 to set no limit.", "Первые N переводов. 0 — без ограничений.", 1),
])
edit(c / "options/modals/ModalThirdParty.svelte", [
    ('title="Third Party Licenses"', 'title="Лицензии третьих сторон"', 1),
    ("<h3>Dictionary Files</h3>", "<h3>Файлы словаря</h3>", 1),
    ("Yomikiri uses JMDict/JMneDict dictionary files for JP-EN dictionary.", "Yomikiri использует словарные файлы JMDict/JMneDict.", 1),
    ("The JMDict/JMneDict dictionary files are the property of the", "Словарные файлы JMDict/JMneDict принадлежат", 1),
    (">, and are used in conformance with the Group's", ">, и используются в соответствии с", 1),
    ('">license</a>.', '">лицензией группы</a>.', 1),
    ("<h3>Others</h3>", "<h3>Прочее</h3>", 1),
])
print("v2 patch OK")
