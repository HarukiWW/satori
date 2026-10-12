# Moved out of build-ios-v141-player.yml, step "Patch pitch accent (compact display next to the word)" (GitHub limits workflow files to 500 KB).
import base64, glob, json, pathlib, struct, zipfile

web = pathlib.Path("src/main/src")


def replace_once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


def fnv(s):
    h = 0x811C9DC5
    b = s.encode("utf-16-le")
    for i in range(0, len(b), 2):
        h ^= b[i] | (b[i + 1] << 8)
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h


def to_hira(s):
    return "".join(chr(ord(c) - 0x60) if 0x30A1 <= ord(c) <= 0x30F6 else c for c in s)


def position_of(p):
    """Downstep mora: 0 = flat. Yomitan allows a number or a string like LHHL."""
    if isinstance(p, bool):
        return None
    if isinstance(p, int):
        return p if 0 <= p < 255 else None
    if isinstance(p, str):
        i = p.find("HL")
        return i + 1 if i >= 0 else 0
    return None


# ---------- 1. binary table from Yomitan pitch accent dictionaries ----------
table = {}
zips = sorted(glob.glob("ours/custom-dict/pitch*.zip"))
for path in zips:
    z = zipfile.ZipFile(path)
    count = 0
    for name in sorted(n for n in z.namelist() if n.startswith("term_meta_bank_")):
        for term, kind, data in json.loads(z.read(name)):
            if kind != "pitch" or not isinstance(data, dict):
                continue
            reading = to_hira(data.get("reading") or term)
            slot = table.setdefault(fnv(term + "|" + reading), [])
            for p in data.get("pitches", []):
                pos = position_of(p.get("position") if isinstance(p, dict) else p)
                if pos is not None and pos not in slot and len(slot) < 4:
                    slot.append(pos)
                    count += 1
    print("pitch dictionary:", path, count, "accents")


def parse_accents(text):
    """Kanjium accents.txt: word <TAB> reading <TAB> accents, e.g. 0 / 1,3 / (名)0,(動)2.
    A kana word may have no reading column: it is its own reading."""
    import re
    n = 0
    for line in text.split("\n"):
        parts = line.rstrip("\r").split("\t")
        if len(parts) < 2 or not parts[0]:
            continue
        word = parts[0]
        if len(parts) >= 3:
            reading, accents = parts[1], parts[2]
        elif parts[1].replace(",", "").replace("(", "").replace(")", "").isdigit():
            reading, accents = word, parts[1]
        else:
            continue
        if not reading:
            reading = word
        accents = re.sub(r"\([^)]*\)", "", accents)
        slot = table.setdefault(fnv(word + "|" + to_hira(reading)), [])
        for a in accents.split(","):
            a = a.strip()
            if a.isdigit() and int(a) < 255 and int(a) not in slot and len(slot) < 4:
                slot.append(int(a))
                n += 1
    return n


kanjium = pathlib.Path("ours/custom-dict/kanjium_accents.txt")
if kanjium.exists() and kanjium.stat().st_size > 100000:
    print("Kanjium accents.txt:", parse_accents(kanjium.read_text(encoding="utf-8")), "accents")
    zips.append("kanjium_accents.txt")
if not zips:
    print("NO pitch dictionary found (kanjium_accents.txt / pitch*.zip): pitch accent will not be shown")

flat = []
for key in sorted(table):
    if not table[key]:
        continue
    packed = 0
    for i, pos in enumerate(table[key]):
        packed |= (pos + 1) << (8 * i)
    flat += [key, packed]
blob = struct.pack("<%dI" % len(flat), *flat)

bg = web / "extension/background"
(bg / "pitchData.ts").write_text(
    'export const PITCH_DATA = "' + base64.b64encode(blob).decode("ascii") + '";\n'
)

# ---------- 2. background: lookup ----------
(web / "lib/pitchLookup.ts").write_text('''import { PITCH_DATA } from "extension/background/pitchData";

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

function toHiragana(s: string): string {
  let out = "";
  for (let i = 0; i < s.length; i++) {
    const c = s.charCodeAt(i);
    out += c >= 0x30a1 && c <= 0x30f6 ? String.fromCharCode(c - 0x60) : s[i];
  }
  return out;
}

/** Index of the record (2 numbers: key, packed accents) */
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

export interface PitchRequest {
  term: string;
  reading: string;
}

/** Downstep positions (0 = flat), most common first. */
export function lookupPitch(req: PitchRequest): number[] {
  if (table === undefined) table = decode(PITCH_DATA);
  if (table.length === 0) return [];
  const reading = toHiragana(req.reading);
  const i =
    find(table, hash(req.term + "|" + reading)) ??
    find(table, hash(reading + "|" + reading));
  if (i === undefined) return [];
  const packed = table[i + 1];
  const result: number[] = [];
  for (let n = 0; n < 4; n++) {
    const v = (packed >>> (8 * n)) & 255;
    if (v > 0) result.push(v - 1);
  }
  return result;
}
''')
(bg / "pitch.ts").write_text('''import { handleMessage } from "extension/browserApi";
import { lookupPitch } from "lib/pitchLookup";

handleMessage("pitch", lookupPitch);
''')

edit_path = web / "extension/background/index.ts"
s = edit_path.read_text()
s = replace_once(s, 'import "./frequency";\n', 'import "./frequency";\nimport "./pitch";\n', "bg import pitch")
edit_path.write_text(s)

p = web / "extension/browserApi.ts"
s = p.read_text()
s = replace_once(
    s,
    "  getDictMetadata: [void, DictionaryMetadata];\n",
    "  getDictMetadata: [void, DictionaryMetadata];\n  pitch: [{ term: string; reading: string }, number[]];\n",
    "message map pitch",
)
p.write_text(s)

# ---------- 3. helper: morae and pitch shape ----------
(web / "components/dictionary/pitchAccent.ts").write_text('''export interface PitchMora {
  text: string;
  high: boolean;
  drop: boolean;
}

export interface PitchView {
  pos: number;
  kind: "heiban" | "atamadaka" | "nakadaka" | "odaka";
  label: string;
  morae: PitchMora[];
}

const SMALL = "ぁぃぅぇぉゃゅょゎ";

export function toHiragana(s: string): string {
  let out = "";
  for (const ch of Array.from(s)) {
    const c = ch.codePointAt(0) ?? 0;
    out += c >= 0x30a1 && c <= 0x30f6 ? String.fromCodePoint(c - 0x60) : ch;
  }
  return out;
}

export function splitMorae(reading: string): string[] {
  const out: string[] = [];
  for (const ch of Array.from(toHiragana(reading))) {
    if (out.length > 0 && SMALL.includes(ch)) {
      out[out.length - 1] += ch;
    } else {
      out.push(ch);
    }
  }
  return out;
}

/** pos: downstep mora (0 = flat). Returns null if it does not fit the reading. */
export function buildPitch(pos: number, reading: string): PitchView | null {
  const morae = splitMorae(reading);
  const n = morae.length;
  if (n === 0 || pos < 0 || pos > n) return null;
  let kind: PitchView["kind"];
  let label: string;
  if (pos === 0) {
    kind = "heiban";
    label = "хэйбан";
  } else if (pos === 1) {
    kind = "atamadaka";
    label = "атамадака";
  } else if (pos === n) {
    kind = "odaka";
    label = "одака";
  } else {
    kind = "nakadaka";
    label = "накадака";
  }
  return {
    pos,
    kind,
    label,
    morae: morae.map((text, idx) => {
      const i = idx + 1;
      const high = pos === 0 ? i >= 2 : pos === 1 ? i === 1 : i >= 2 && i <= pos;
      return { text, high, drop: pos >= 1 && i === pos };
    }),
  };
}
''')

# ---------- 4. component ----------
(web / "components/dictionary/PitchAccent.svelte").write_text('''<script lang="ts">
  import { type Entry, getMainForm, getReadingForForm } from "lib/dicEntry";
  import { buildPitch, type PitchView } from "./pitchAccent";

  export let entry: Entry;

  let pitches: PitchView[] = [];
  let requestId = 0;

  function loadPitch(entry: Entry): void {
    pitches = [];
    if (entry.type !== "word") return;
    // eslint-disable-next-line
    const rt =
      (globalThis as any).yomikiriRuntime ?? (globalThis as any).chrome?.runtime;
    if (rt === undefined || typeof rt.sendMessage !== "function") return;
    const term = getMainForm(entry);
    const reading = getReadingForForm(entry, term, false).reading;
    const id = ++requestId;
    const send = (retry: boolean) => {
      // eslint-disable-next-line
      rt.sendMessage({ key: "pitch", request: { term, reading } }, (resp: any) => {
        void rt.lastError;
        if (id !== requestId) return;
        if (resp === undefined && retry) {
          setTimeout(() => send(false), 1000);
        } else if (resp?.success === true && Array.isArray(resp.resp)) {
          const views: PitchView[] = [];
          for (const pos of resp.resp as number[]) {
            const view = buildPitch(pos, reading);
            if (view !== null) views.push(view);
          }
          pitches = views.slice(0, 3);
        }
      });
    };
    send(true);
  }

  $: loadPitch(entry);
</script>

{#if pitches.length > 0}
  <div class="pitches">
    {#each pitches as p}
      <div class="pitch {p.kind}" title={p.label}>
        <span class="num">{p.pos}</span>
        <span class="graph">{#each p.morae as m}<span class="m" class:high={m.high} class:drop={m.drop}>{m.text}</span>{/each}</span>
      </div>
    {/each}
  </div>
{/if}

<style>
  .pitches {
    flex: 0 1 auto;
    min-width: 0;
    align-self: flex-end;
    display: flex;
    flex-wrap: wrap;
    gap: 0.25rem 0.75rem;
    margin: 0 0.5rem 0.2rem 0;
  }

  .pitch {
    --pitch-color: #5aa9ff;
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    font-size: 0.85rem;
  }

  .heiban {
    --pitch-color: #5aa9ff;
  }

  .atamadaka {
    --pitch-color: #ff6b6b;
  }

  .nakadaka {
    --pitch-color: #ffb454;
  }

  .odaka {
    --pitch-color: #7ed67e;
  }

  .num {
    font-size: 0.7rem;
    font-weight: 600;
    line-height: 1.1rem;
    min-width: 1.1rem;
    padding: 0 0.2rem;
    text-align: center;
    color: var(--pitch-color);
    border: 1px solid var(--pitch-color);
    border-radius: 0.6rem;
  }

  .graph {
    display: inline-flex;
  }

  .m {
    display: inline-block;
    padding: 0 0.05rem;
    line-height: 1.15;
    border-top: 2px solid transparent;
    border-right: 2px solid transparent;
  }

  .m.high {
    border-top-color: var(--pitch-color);
  }

  .m.drop {
    border-right-color: var(--pitch-color);
  }
</style>
''')

# ---------- 5. entry header: the pitch goes right after the word ----------
p = web / "components/dictionary/DicEntryView.svelte"
s = p.read_text()
s = replace_once(s, '  import Badges from "./Badges.svelte";\n',
                 '  import Badges from "./Badges.svelte";\n  import PitchAccent from "./PitchAccent.svelte";\n', "entry import")
s = replace_once(s, '    </div>\n    <div class="icons">', '    </div>\n    <PitchAccent {entry} />\n    <div class="icons">', "entry markup")
s = replace_once(s, "  .term {\n    flex: 1 1 auto;", "  .term {\n    flex: 0 1 auto;", "entry term css")
s = replace_once(s, "  .icons {\n    flex: 0 0 auto;\n", "  .icons {\n    flex: 0 0 auto;\n    margin-left: auto;\n", "entry icons css")
p.write_text(s)
print("pitch accent patch OK")
