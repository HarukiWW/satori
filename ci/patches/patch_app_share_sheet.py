# Moved out of build-ios-v141-player.yml, step "Patch app and share sheet (shared mined words, frequencies, marks, look)" (GitHub limits workflow files to 500 KB).
import pathlib, re

root = pathlib.Path("src/safari")
web = pathlib.Path("src/main/src")


def replace_once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


# ======================= Swift: stats messages for the app and the share sheet =======================
p = root / "Shared (iOS)/YomikiriWebView.swift"
s = p.read_text()
s = replace_once(s, '            case "ttsVoices":\n', '''            case "loadStats":
                return try Storage.stats.get()
            case "saveStats":
                try Storage.stats.set(request)
                return nil
            case "ttsVoices":
''', "webview stats cases")
p.write_text(s)

# ======================= Swift: dark native chrome =======================
p = root / "iOS (App)/MainView.swift"
s = p.read_text()
s = replace_once(s, "                .tag(Tabs.settings)\n        }\n", "                .tag(Tabs.settings)\n        }\n        .preferredColorScheme(.dark)\n", "dark scheme")
p.write_text(s)

LIGHT = "Color(red: 0.95, green: 0.95, blue: 0.95)"
p = root / "iOS (App)/DictionaryView.swift"
s = p.read_text()
s = replace_once(s, LIGHT, "Color(red: 0.110, green: 0.110, blue: 0.118)", "dictionary bg")
p.write_text(s)
p = root / "iOS (App)/OptionsView.swift"
s = p.read_text()
s = replace_once(s, LIGHT, "Color(red: 0, green: 0, blue: 0)", "options bg")
s = replace_once(s, "appearance.shadowColor = .darkGray", "appearance.shadowColor = .clear", "nav shadow")
p.write_text(s)

p = root / "iOS (App)/YomikiriApp.swift"
s = p.read_text()
s = replace_once(s, '''            tabBarAppearance.configureWithDefaultBackground()
            UITabBar.appearance().scrollEdgeAppearance = tabBarAppearance
''', '''            tabBarAppearance.configureWithOpaqueBackground()
            tabBarAppearance.backgroundColor = UIColor(red: 0.07, green: 0.07, blue: 0.075, alpha: 1)
            UITabBar.appearance().standardAppearance = tabBarAppearance
            UITabBar.appearance().scrollEdgeAppearance = tabBarAppearance
''', "tab bar")
p.write_text(s)

# ======================= TS: one frequency lookup for the extension, the app and the share sheet =======================
bg = web / "extension/background"
f = (bg / "frequency.ts").read_text()
f = replace_once(f, 'import { handleMessage } from "extension/browserApi";\nimport { FREQ_DICTS } from "./frequencyData";\n',
                 'import { FREQ_DICTS } from "extension/background/frequencyData";\n', "freq imports")
f = replace_once(f, 'handleMessage("frequency", lookup);\n', "", "freq register")
f = replace_once(f, "function lookup(req: FrequencyRequest)", "export function lookupFrequency(req: FrequencyRequest)", "freq export")
(web / "lib/frequencyLookup.ts").write_text(f)
(bg / "frequency.ts").write_text('''import { handleMessage } from "extension/browserApi";
import { lookupFrequency } from "lib/frequencyLookup";

handleMessage("frequency", lookupFrequency);
''')

# ======================= TS: mined-words logic without browser APIs =======================
(web / "lib/statsLite.ts").write_text(r'''/**
 * Mined words, in the same format as the statistics of the extension.
 * No browser APIs here, so it also runs inside the app and the share sheet.
 */
export interface LiteDay {
  mined: string[];
  kanji: string[];
  read: number;
  time?: number;
  sentences?: number;
  words?: number;
}

export interface LiteStats {
  days: Record<string, LiteDay>;
  resetToken?: string;
}

const KANJI = /[\u3400-\u4dbf\u4e00-\u9fff]/g;
const STEM = /^[\u3400-\u4dbf\u4e00-\u9fff]+/;

export function emptyLiteStats(): LiteStats {
  return { days: {} };
}

export function localDateKey(d: Date = new Date()): string {
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return d.getFullYear() + "-" + m + "-" + day;
}

/** Dictionary form of the mined word, from the note's fields. */
export function wordFromNoteLite(note: {
  fields: { name: string; value: string }[];
}): string {
  const field =
    note.fields.find((f) => f.name === "Furigana") ??
    note.fields.find((f) => f.name === "Word") ??
    note.fields[0];
  const value = field?.value ?? "";
  return value
    .replace(/<[^>]*>/g, "")
    .replace(/\[[^\]]*\]/g, "")
    .replace(/\s+/g, "");
}

export function addMinedLite(data: LiteStats, word: string): void {
  const key = localDateKey();
  if (data.days[key] === undefined) {
    data.days[key] = { mined: [], kanji: [], read: 0, time: 0 };
  }
  const d = data.days[key];
  if (!d.mined.includes(word)) d.mined.push(word);
  for (const k of word.match(KANJI) ?? []) {
    if (!d.kanji.includes(k)) d.kanji.push(k);
  }
}

export function findMinedLite(
  data: LiteStats,
  forms: string[],
): { exact: string[]; related: string[] } {
  const set = new Set<string>();
  for (const d of Object.values(data.days)) {
    d.mined.forEach((w) => set.add(w));
  }
  const mined = Array.from(set);
  const exact = mined.filter((w) => forms.includes(w));
  const stems = new Set<string>();
  for (const f of forms) {
    const m = f.match(STEM);
    if (m !== null) stems.add(m[0]);
  }
  const related = mined.filter((w) => {
    if (exact.includes(w)) return false;
    const m = w.match(STEM);
    return m !== null && stems.has(m[0]);
  });
  return { exact, related };
}
''')

# ======================= TS: app + share sheet use the shared native statistics =======================
(web / "platform/iosapp/appStats.ts").write_text('''import type { AnkiNote } from "lib/anki";
import {
  addMinedLite,
  emptyLiteStats,
  findMinedLite,
  wordFromNoteLite,
  type LiteStats,
} from "lib/statsLite";
import { Platform } from ".";

async function loadApp(): Promise<LiteStats> {
  const raw = (await Platform.messageWebview("loadStats", null)) as
    | LiteStats
    | null;
  if (raw !== null && typeof raw === "object" && raw.days !== undefined) {
    return raw;
  }
  return emptyLiteStats();
}

/** The word goes to the same storage that the extension uses. */
export async function recordMinedNoteApp(note: AnkiNote): Promise<void> {
  const word = wordFromNoteLite(note);
  if (word === "") return;
  const data = await loadApp();
  addMinedLite(data, word);
  await Platform.messageWebview("saveStats", data);
}

export async function lookupMinedApp(
  forms: string[],
): Promise<{ exact: string[]; related: string[] }> {
  return findMinedLite(await loadApp(), forms);
}
''')

# Badges ask `rt.sendMessage(...)`. In the app and the share sheet this answers locally instead of the background script.
(web / "platform/iosapp/runtimeShim.ts").write_text('''import { lookupFrequency } from "lib/frequencyLookup";
import { lookupMinedApp } from "./appStats";

interface ShimMessage {
  key: string;
  request: unknown;
}

async function handle(msg: ShimMessage): Promise<unknown> {
  if (msg.key === "frequency") {
    return lookupFrequency(msg.request as { term: string; reading: string });
  }
  if (msg.key === "minedLookup") {
    return await lookupMinedApp((msg.request as { forms: string[] }).forms);
  }
  throw new Error("Unknown message: " + msg.key);
}

// eslint-disable-next-line
(globalThis as any).yomikiriRuntime = {
  lastError: undefined,
  sendMessage(msg: ShimMessage, cb?: (resp: unknown) => void): void {
    handle(msg).then(
      (resp) => cb?.({ success: true, resp }),
      (err: unknown) => {
        console.error(err);
        cb?.({ success: false });
      },
    );
  },
};
''')

p = web / "iosapp/dictionary.ts"
s = p.read_text()
p.write_text('import "platform/iosapp/runtimeShim";\n' + s)

p = web / "platform/iosapp/index.ts"
s = p.read_text()
s = replace_once(s, "  getDictMetadata: [null, DictionaryMetadata];\n\n  // action extension\n",
                 "  getDictMetadata: [null, DictionaryMetadata];\n  loadStats: [null, unknown];\n  saveStats: [unknown, void];\n\n  // action extension\n", "app message map")
p.write_text(s)

p = web / "platform/iosapp/anki.ts"
s = p.read_text()
s = replace_once(s, 'import { iosAnkiMobileURL } from "../shared/anki";\n',
                 'import { iosAnkiMobileURL } from "../shared/anki";\nimport { recordMinedNoteApp } from "./appStats";\n', "app anki import")
s = replace_once(s, "  export async function addNote(note: AnkiNote): Promise<boolean> {\n    const url = iosAnkiMobileURL(note);\n",
                 "  export async function addNote(note: AnkiNote): Promise<boolean> {\n    try {\n      await recordMinedNoteApp(note);\n    } catch (e) {\n      console.error(e);\n    }\n    const url = iosAnkiMobileURL(note);\n", "app addNote")
p.write_text(s)

# ======================= Badges: use the local answer when it exists; badges that do not break =======================
p = web / "components/dictionary/Badges.svelte"
s = p.read_text()
old = "    const rt = (globalThis as any).chrome?.runtime;"
assert s.count(old) == 2, "badges runtime lines"
s = s.replace(old, "    const rt =\n      (globalThis as any).yomikiriRuntime ?? (globalThis as any).chrome?.runtime;")
s = replace_once(s, "    display: flex;\n    gap: 0.25rem;\n  }", "    display: flex;\n    flex-wrap: wrap;\n    gap: 0.25rem;\n  }", "badges wrap")
s = replace_once(s, "    width: max-content;\n", "    width: max-content;\n    flex: 0 0 auto;\n    white-space: nowrap;\n", "badge nowrap")
p.write_text(s)

# ======================= look: black page, rounded cards (same as the statistics screen) =======================
p = web / "components/options/styles.css"
s = p.read_text()
s = replace_once(s, "  background-color: var(--background-alt);\n}", "  background-color: #000000;\n}", "options page bg")
p.write_text(s)
p = web / "components/options/GroupedOptions.svelte"
s = p.read_text()
s = replace_once(s, "    border-radius: 8px;\n", "    border-radius: 14px;\n    overflow: hidden;\n", "card radius")
p.write_text(s)
# ======================= app version everywhere =======================
p = pathlib.Path("src/package.json")
s = p.read_text()
s = replace_once(s, '"version": "0.3.5"', '"version": "' + __import__("os").environ["APP_VERSION"] + '"', "package version")
p.write_text(s)

# ======================= look like the statistics screen =======================
p = root / "iOS (App)/OptionsView.swift"
s = p.read_text()
s = replace_once(s, '.navigationTitle("Настройки")\n            .navigationBarTitleDisplayMode(.inline)',
                 '.navigationTitle("Настройки")\n            .navigationBarTitleDisplayMode(.large)', "large title")
s = replace_once(s, "        appearance.backgroundColor = UIColor(OptionsView.BACKGROUND_COLOR)\n",
                 "        appearance.backgroundColor = UIColor(OptionsView.BACKGROUND_COLOR)\n        appearance.largeTitleTextAttributes = [.font: UIFont.systemFont(ofSize: 30, weight: .bold)]\n", "large title font")
p.write_text(s)

p = web / "components/options/GroupedOptions.svelte"
s = p.read_text()
s = replace_once(s, "    font-size: 1.6rem;\n", "    font-size: 0.95rem;\n    color: var(--text-light);\n    padding-left: 8px;\n", "group title")
p.write_text(s)
p = web / "components/options/items/OptionBase.svelte"
s = p.read_text()
s = replace_once(s, "    padding: 6px 0px;\n", "    padding: 12px 0px;\n", "option padding")
s = replace_once(s, "    margin: 0px 8px;\n", "    margin: 0px 14px;\n", "option margin")
p.write_text(s)

# Russian for the last visible English texts that are not technical
p = web / "components/dictionary/Tokenize.svelte"
s = p.read_text()
s = replace_once(s, 'placeholder="Enter Japanese word or sentence."', 'placeholder="Введите японское слово или предложение"', "search placeholder")
s = replace_once(s, 'label="Close"', 'label="Закрыть"', "close label")
p.write_text(s)
p = web / "iosapp/DictionaryView.svelte"
s = p.read_text()
s = replace_once(s, "Type in Japanese text", "Введите японский текст", "placeholder text")
s = replace_once(s, "    background-color: var(--background);\n    display: flex;\n    align-items: center;\n", "    background-color: #000000;\n    display: flex;\n    align-items: center;\n", "placeholder bg")
p.write_text(s)

# dictionary page of the app and the share sheet: black page, rounded search field, entries as cards
p = web / "iosapp/DictionaryPage.svelte"
s = p.read_text()
s = replace_once(s, "<style global>\n", """<style global>
  html:root,
  html body {
    background-color: #000000 !important;
  }

  /* Only the direct children of the search page.
     (".search .header" also matched the header inside every entry card.) */
  .search > .header,
  .search > .entries {
    background-color: #000000 !important;
  }

  .search > .header {
    padding: 10px 12px 6px 12px !important;
  }

  .search > .header.action-button-mode {
    padding-bottom: 28px !important;
    border-bottom: none !important;
  }

  .search .searchbar {
    border: none !important;
    border-radius: 14px !important;
    background-color: #1c1c1e !important;
    padding: 6px 10px !important;
  }

  .search .searchbar input {
    background-color: transparent !important;
  }

  .search > .tokensview {
    margin: 6px 12px;
    padding: 8px 10px !important;
    border-radius: 14px;
    background-color: #1c1c1e !important;
  }

  /* toolbar (translate / grammar): no grey strip, round buttons */
  .search .toolbar-with-pane {
    margin: 4px 12px 0 12px;
    border-bottom: none !important;
  }

  .search .toolbar-with-pane .toolbar,
  .search .toolbar-with-pane .tool-button {
    background-color: transparent !important;
  }

  .search .toolbar-with-pane .toolbar {
    height: auto !important;
  }

  .search .toolbar-with-pane .tool-button {
    padding: 8px 14px !important;
    margin-right: 8px;
    border-radius: 12px;
  }

  .search .toolbar-with-pane .tool-button .icon {
    fill: #a0a0a5 !important;
  }

  .search .toolbar-with-pane .tool-button.selected {
    background-color: #2c2c2e !important;
  }

  .search .toolbar-with-pane .tool-button.selected .icon {
    fill: #ff9f0a !important;
  }

  .search .toolbar-with-pane .tool-button:disabled .icon {
    fill: #48484a !important;
  }

  .search .toolbar-with-pane .tools-pane {
    margin-top: 6px;
    border-radius: 14px;
    background-color: #1c1c1e !important;
  }

  /* entries as cards */
  .search .entries > div {
    padding-bottom: 12px;
  }

  .search .entries > div > div {
    margin: 10px 12px;
    border: none !important;
    border-radius: 14px;
    background-color: #1c1c1e;
  }

  .search .entries > div > div.entryView {
    padding: 12px 6px 14px 6px !important;
  }

""", "dictionary page css")
p.write_text(s)
print("app patch OK")
