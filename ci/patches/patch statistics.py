# Moved out of build-ios-v141-player.yml, step "Patch statistics (mined words, kanji, reading counter, popup view)" (GitHub limits workflow files to 500 KB).
import pathlib

ext = pathlib.Path("src/main/src/extension")

def replace_once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)

# ---------- storage + summary logic (runs in background and popup) ----------
(ext / "stats.ts").write_text("""import { browserStorage } from "extension/browserApi";
import { ExtensionPlatform as Platform } from "@platform";

export const STATS_KEY = "stats:v1";
const TOKEN_KEY = "stats:token";
/** hashes of already counted sentences are kept in 256 buckets */
const SEEN_PREFIX = "stats:seen:";

export interface DayStats {
  /** unique words (dictionary form) mined that day */
  mined: string[];
  /** unique kanji in those words */
  kanji: string[];
  /** Japanese characters read */
  read: number;
  /** seconds spent reading */
  time?: number;
  /** sentences read */
  sentences?: number;
  /** words read */
  words?: number;
}

export interface StatsData {
  days: Record<string, DayStats>;
  /** changed when the statistics are reset (also from the app) */
  resetToken?: string;
}

export interface ReadSentence {
  /** hash of the sentence */
  h: number;
  /** characters */
  c: number;
  /** words */
  w: number;
}

export interface Summary {
  minedWords: number;
  kanji: number;
  read: number;
  time: number;
  sentences: number;
  readWords: number;
}

const KANJI = /[\\u3400-\\u4dbf\\u4e00-\\u9fff]/g;

export function localDate(d: Date = new Date()): string {
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return d.getFullYear() + "-" + m + "-" + day;
}

function localLoad(): Promise<StatsData | null> {
  return new Promise((resolve) => {
    browserStorage().get(STATS_KEY, (obj) => {
      const v = obj?.[STATS_KEY] as StatsData | undefined;
      resolve(v !== undefined && v.days !== undefined ? v : null);
    });
  });
}

function localSave(data: StatsData): Promise<void> {
  return new Promise((resolve) => {
    browserStorage().set({ [STATS_KEY]: data }, () => resolve());
  });
}

/** The statistics are kept by the app, so the extension and the app see the same numbers. */
async function nativeLoad(): Promise<StatsData | null> {
  try {
    // eslint-disable-next-line
    const v = await (Platform as any).requestToApp("loadStats", null);
    if (v !== null && typeof v === "object" && v.days !== undefined) {
      return v as StatsData;
    }
    return null;
  } catch (_e) {
    return null;
  }
}

async function nativeSave(data: StatsData): Promise<void> {
  try {
    // eslint-disable-next-line
    await (Platform as any).requestToApp("saveStats", data);
  } catch (e) {
    console.warn("Could not save stats to the app", e);
  }
}

function getToken(): Promise<string | undefined> {
  return new Promise((resolve) => {
    browserStorage().get(TOKEN_KEY, (obj) => {
      resolve(obj?.[TOKEN_KEY] as string | undefined);
    });
  });
}

function setToken(token: string): Promise<void> {
  return new Promise((resolve) => {
    browserStorage().set({ [TOKEN_KEY]: token }, () => resolve());
  });
}

function removeKeys(keys: string[]): Promise<void> {
  return new Promise((resolve) => {
    browserStorage().remove(keys, () => resolve());
  });
}

/** If the statistics were reset (for example in the app), forget the counted sentences too. */
async function applyResetToken(data: StatsData): Promise<void> {
  if (data.resetToken === undefined) return;
  if ((await getToken()) === data.resetToken) return;
  await removeKeys(allBucketKeys());
  await setToken(data.resetToken);
}

export async function loadStats(): Promise<StatsData> {
  let data = await nativeLoad();
  if (data === null) {
    data = await localLoad();
    // first run after an update: move the old statistics to the app
    if (data !== null) await nativeSave(data);
  }
  if (data === null) data = { days: {} };
  await applyResetToken(data);
  return data;
}

async function saveStats(data: StatsData): Promise<void> {
  await nativeSave(data);
  await localSave(data);
}

function getMany(keys: string[]): Promise<Record<string, number[]>> {
  return new Promise((resolve) => {
    browserStorage().get(keys, (obj) => resolve((obj ?? {}) as Record<string, number[]>));
  });
}

function setMany(values: Record<string, number[]>): Promise<void> {
  return new Promise((resolve) => {
    if (Object.keys(values).length === 0) return resolve();
    browserStorage().set(values, () => resolve());
  });
}

function bucketKey(hash: number): string {
  return SEEN_PREFIX + (hash & 255).toString(16).padStart(2, "0");
}

function allBucketKeys(): string[] {
  const keys: string[] = [];
  for (let i = 0; i < 256; i++) {
    keys.push(SEEN_PREFIX + i.toString(16).padStart(2, "0"));
  }
  return keys;
}

// updates are applied one after another so they never overwrite each other
let chain: Promise<void> = Promise.resolve();

function update(fn: (data: StatsData) => void | Promise<void>): Promise<void> {
  chain = chain
    .then(async () => {
      const data = await loadStats();
      await fn(data);
      await saveStats(data);
    })
    .catch((e) => console.error("Could not update stats", e));
  return chain;
}

function today(data: StatsData): DayStats {
  const key = localDate();
  if (data.days[key] === undefined) {
    data.days[key] = { mined: [], kanji: [], read: 0, time: 0 };
  }
  return data.days[key];
}

/** Dictionary form of the mined word, from the note's fields. */
export function wordFromNote(note: {
  fields: { name: string; value: string }[];
}): string {
  const field =
    note.fields.find((f) => f.name === "Furigana") ??
    note.fields.find((f) => f.name === "Word") ??
    note.fields[0];
  const value = field?.value ?? "";
  return value
    .replace(/<[^>]*>/g, "")
    .replace(/\\[[^\\]]*\\]/g, "")
    .replace(/\\s+/g, "");
}

export function recordMinedNote(note: {
  fields: { name: string; value: string }[];
}): Promise<void> {
  const word = wordFromNote(note);
  if (word === "") return Promise.resolve();
  minedCache = undefined;
  return update((data) => {
    const d = today(data);
    if (!d.mined.includes(word)) d.mined.push(word);
    for (const k of word.match(KANJI) ?? []) {
      if (!d.kanji.includes(k)) d.kanji.push(k);
    }
  });
}

const STEM = /^[\u3400-\u4dbf\u4e00-\u9fff]+/;
let minedCache: { at: number; words: string[] } | undefined;

async function allMinedWords(): Promise<string[]> {
  const now = Date.now();
  if (minedCache !== undefined && now - minedCache.at < 5000) {
    return minedCache.words;
  }
  const data = await loadStats();
  const set = new Set<string>();
  for (const d of Object.values(data.days)) {
    d.mined.forEach((w) => set.add(w));
  }
  minedCache = { at: now, words: Array.from(set) };
  return minedCache.words;
}

/**
 * Which of the given forms of a dictionary entry were already added to Anki.
 * `related`: other mined words that start with the same kanji (聞こえる and 聞く).
 */
export async function lookupMined(
  forms: string[],
): Promise<{ exact: string[]; related: string[] }> {
  const mined = await allMinedWords();
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

/** Removes a word from today's mined words and recounts today's kanji. */
export function removeMinedWord(word: string): Promise<void> {
  minedCache = undefined;
  return update((data) => {
    const d = today(data);
    d.mined = d.mined.filter((w) => w !== word);
    const kanji = new Set<string>();
    for (const w of d.mined) {
      for (const k of w.match(KANJI) ?? []) kanji.add(k);
    }
    d.kanji = Array.from(kanji);
  });
}

/** Sentences that were already counted before are ignored. */
export function recordReading(
  sentences: ReadSentence[],
  seconds: number,
): Promise<void> {
  if (sentences.length === 0 && !(seconds > 0)) return Promise.resolve();
  return update(async (data) => {
    const d = today(data);
    if (seconds > 0) d.time = (d.time ?? 0) + Math.round(seconds);
    if (sentences.length === 0) return;

    const keys = Array.from(new Set(sentences.map((s) => bucketKey(s.h))));
    const buckets = await getMany(keys);
    const dirty = new Set<string>();
    for (const s of sentences) {
      const key = bucketKey(s.h);
      if (buckets[key] === undefined) buckets[key] = [];
      if (buckets[key].includes(s.h)) continue;
      buckets[key].push(s.h);
      dirty.add(key);
      d.sentences = (d.sentences ?? 0) + 1;
      d.read += s.c;
      d.words = (d.words ?? 0) + s.w;
    }
    const changed: Record<string, number[]> = {};
    dirty.forEach((k) => (changed[k] = buckets[k]));
    await setMany(changed);
  });
}

/** Deletes all statistics, including the memory of already counted sentences. */
export function resetStats(): Promise<void> {
  chain = chain
    .then(async () => {
      const token = String(Date.now());
      await removeKeys(allBucketKeys());
      await setToken(token);
      await saveStats({ days: {}, resetToken: token });
    })
    .catch((e) => console.error("Could not reset stats", e));
  minedCache = undefined;
  return chain;
}

function dayKeys(days: number): string[] {
  const now = new Date();
  const keys: string[] = [];
  for (let i = 0; i < days; i++) {
    keys.push(
      localDate(new Date(now.getFullYear(), now.getMonth(), now.getDate() - i)),
    );
  }
  return keys;
}

/** `days`: number of last days including today. null: all time. */
export function summarize(data: StatsData, days: number | null): Summary {
  const words = new Set<string>();
  const kanji = new Set<string>();
  const sum = { read: 0, time: 0, sentences: 0, readWords: 0 };
  const keys = days === null ? Object.keys(data.days) : dayKeys(days);
  for (const key of keys) {
    const d = data.days[key];
    if (d === undefined) continue;
    d.mined.forEach((w) => words.add(w));
    d.kanji.forEach((k) => kanji.add(k));
    sum.read += d.read;
    sum.time += d.time ?? 0;
    sum.sentences += d.sentences ?? 0;
    sum.readWords += d.words ?? 0;
  }
  return { minedWords: words.size, kanji: kanji.size, ...sum };
}

/** Number of days in a row (up to today) with reading or mining. */
export function streak(data: StatsData): number {
  const active = (key: string) => {
    const d = data.days[key];
    return d !== undefined && (d.read >= 50 || d.mined.length > 0);
  };
  const now = new Date();
  const keyAgo = (i: number) =>
    localDate(new Date(now.getFullYear(), now.getMonth(), now.getDate() - i));
  // today may have not started yet
  let i = active(keyAgo(0)) ? 0 : 1;
  let n = 0;
  while (i < 3650 && active(keyAgo(i))) {
    n++;
    i++;
  }
  return n;
}

/** Oldest first. */
export function lastDays(
  data: StatsData,
  n: number,
): { date: string; read: number; mined: number }[] {
  return dayKeys(n)
    .reverse()
    .map((date) => ({
      date,
      read: data.days[date]?.read ?? 0,
      mined: data.days[date]?.mined.length ?? 0,
    }));
}
""")

# ---------- background: receives read sentences from content scripts ----------
(ext / "background/statsHandlers.ts").write_text("""import { handleMessage } from "extension/browserApi";
import { recordReading, lookupMined } from "extension/stats";

handleMessage("statsRead", (req) => recordReading(req.sentences, req.seconds));
handleMessage("minedLookup", (req) => lookupMined(req.forms));
""")

p = ext / "background/index.ts"
s = p.read_text()
s = replace_once(s, 'import "./frequency";', 'import "./frequency";\nimport "./statsHandlers";', "bg import")
p.write_text(s)

p = ext / "browserApi.ts"
s = p.read_text()
s = replace_once(s, "  getDictMetadata: [void, DictionaryMetadata];\n",
                 "  getDictMetadata: [void, DictionaryMetadata];\n  statsRead: [\n    { sentences: { h: number; c: number; w: number }[]; seconds: number },\n    void,\n  ];\n  minedLookup: [\n    { forms: string[] },\n    { exact: string[]; related: string[] },\n  ];\n", "message map")
p.write_text(s)

# ---------- mined words: record when a note is added ----------
p = ext.parent / "platform/ios/anki.ts"
s = p.read_text()
s = replace_once(s, 'import { iosAnkiMobileURL } from "../shared/anki";',
                 'import { iosAnkiMobileURL } from "../shared/anki";\nimport { recordMinedNote } from "extension/stats";', "anki import")
s = replace_once(s, "  async function _addNote(note: AnkiNote): Promise<boolean> {\n",
                 "  async function _addNote(note: AnkiNote): Promise<boolean> {\n    try {\n      await recordMinedNote(note);\n    } catch (e) {\n      console.error(e);\n    }\n", "add note")
p.write_text(s)

# ---------- smart reading counter (content script, top frame only) ----------
(ext / "content/readingStats.ts").write_text("""/**
 * Smart reading counter.
 *
 * The page text is split into sentences. A sentence counts as read when
 *  - it was on screen for at least 10 seconds (while the user was active), and
 *  - the reading speed over the whole page is realistic: credit is taken from a
 *    bucket that fills at READ_CPS characters per second, so a full screen
 *    cannot be credited just because 10 seconds have passed.
 * Interface text (menus, headers, buttons, links, fixed bars) is ignored.
 * The same sentence is counted only once (the background script remembers it).
 */
const JP = /[\\u3040-\\u30ff\\u3400-\\u4dbf\\u4e00-\\u9fff]/g;
const HAS_JP = /[\\u3040-\\u30ff\\u3400-\\u4dbf\\u4e00-\\u9fff]/;
const BLOCKS = "p, li, h1, h2, h3, h4, h5, h6, blockquote, dd, dt, td, pre, div";
const SKIP =
  "nav, header, footer, aside, button, a, form, select, label, summary, script, style, noscript, " +
  "[role='navigation'], [role='button'], [role='menu'], [role='menuitem'], [role='tab']";
const SENTENCE_RE = /[^。！？!?\\n]*[。！？!?]+[」』）)”]*|[^。！？!?\\n]+/g;
const MIN_ON_SCREEN_MS = 10000;
const READ_CPS = 15;
const BUCKET_MAX = 150;
const MIN_CHARS = 4;
const MAX_SENTENCES_PER_BLOCK = 3000;
const IDLE_MS = 45000;
const FLUSH_MS = 10000;

interface Sentence {
  text: string;
  start: number;
  end: number;
  hash: number;
  chars: number;
  ms: number;
  done: boolean;
  queued: boolean;
}

interface Block {
  nodes: { node: Text; start: number }[];
  sentences: Sentence[];
}

function fnv(s: string): number {
  let h = 0x811c9dc5;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return h >>> 0;
}

// eslint-disable-next-line
const segmenter: any =
  typeof Intl !== "undefined" && "Segmenter" in Intl
    ? // eslint-disable-next-line
      new (Intl as any).Segmenter("ja", { granularity: "word" })
    : undefined;

function countWords(text: string, chars: number): number {
  if (segmenter === undefined) return Math.max(1, Math.round(chars / 1.7));
  let n = 0;
  // eslint-disable-next-line
  for (const seg of segmenter.segment(text) as Iterable<{ isWordLike?: boolean }>) {
    if (seg.isWordLike === true) n++;
  }
  return Math.max(1, n);
}

function isInterface(el: Element): boolean {
  if (el.closest(SKIP) !== null) return true;
  for (let n: Element | null = el; n !== null && n !== document.body; n = n.parentElement) {
    const pos = getComputedStyle(n).position;
    if (pos === "fixed" || pos === "sticky") return true;
  }
  return false;
}

function buildBlock(el: Element): Block | null {
  const nodes: { node: Text; start: number }[] = [];
  let text = "";
  const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, {
    acceptNode: (n) =>
      n.parentElement?.closest("rt, rp, script, style, noscript") != null
        ? NodeFilter.FILTER_REJECT
        : NodeFilter.FILTER_ACCEPT,
  });
  for (let n = walker.nextNode(); n !== null; n = walker.nextNode()) {
    nodes.push({ node: n as Text, start: text.length });
    text += (n as Text).data;
  }
  const sentences: Sentence[] = [];
  for (const m of text.matchAll(SENTENCE_RE)) {
    const raw = m[0];
    const chars = raw.match(JP)?.length ?? 0;
    if (chars < MIN_CHARS) continue;
    const start = m.index ?? 0;
    sentences.push({
      text: raw,
      start,
      end: start + raw.length,
      hash: fnv(raw.replace(/\\s+/g, "")),
      chars,
      ms: 0,
      done: false,
      queued: false,
    });
    if (sentences.length >= MAX_SENTENCES_PER_BLOCK) break;
  }
  return sentences.length === 0 ? null : { nodes, sentences };
}

function locate(block: Block, pos: number): { node: Text; offset: number } {
  const nodes = block.nodes;
  let lo = 0;
  let hi = nodes.length - 1;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (nodes[mid].start <= pos) lo = mid;
    else hi = mid - 1;
  }
  const n = nodes[lo];
  return { node: n.node, offset: Math.min(pos - n.start, n.node.data.length) };
}

function rectOf(block: Block, s: Sentence): DOMRect | null {
  try {
    const a = locate(block, s.start);
    const b = locate(block, s.end - 1);
    const range = document.createRange();
    range.setStart(a.node, a.offset);
    range.setEnd(b.node, Math.min(b.offset + 1, b.node.data.length));
    const r = range.getBoundingClientRect();
    return r.width === 0 && r.height === 0 ? null : r;
  } catch (_e) {
    return null;
  }
}

function mostlyOnScreen(r: DOMRect): boolean {
  const w = Math.max(0, Math.min(r.right, window.innerWidth) - Math.max(r.left, 0));
  const h = Math.max(0, Math.min(r.bottom, window.innerHeight) - Math.max(r.top, 0));
  return (w * h) / Math.max(1, r.width * r.height) >= 0.8;
}

function eachVisibleSentence(block: Block, fn: (s: Sentence, r: DOMRect) => void): void {
  const list = block.sentences;
  let i = 0;
  if (list.length > 30) {
    // binary search: first sentence that is not above the screen
    let lo = 0;
    let hi = list.length;
    while (lo < hi) {
      const mid = (lo + hi) >> 1;
      const r = rectOf(block, list[mid]);
      if (r !== null && r.bottom <= 0) lo = mid + 1;
      else hi = mid;
    }
    i = lo;
  }
  for (; i < list.length; i++) {
    const r = rectOf(block, list[i]);
    if (r === null) continue;
    if (r.top >= window.innerHeight) break;
    if (r.bottom <= 0) continue;
    fn(list[i], r);
  }
}

function start(): void {
  const blocks = new WeakMap<Element, Block>();
  const rejected = new WeakSet<Element>();
  const visible = new Set<Block>();
  const counted = new Set<number>();
  let queue: Sentence[] = [];
  let outbox: { h: number; c: number; w: number }[] = [];
  let bucket = 0;
  let pendingMs = 0;
  let lastActive = Date.now();
  let lastTick = Date.now();

  const io = new IntersectionObserver(
    (entries) => {
      for (const e of entries) {
        const block = blocks.get(e.target);
        if (block === undefined) continue;
        if (e.isIntersecting) visible.add(block);
        else visible.delete(block);
      }
    },
    { threshold: 0 },
  );

  function scan(): void {
    for (const el of Array.from(document.querySelectorAll(BLOCKS))) {
      if (blocks.has(el) || rejected.has(el)) continue;
      if (el.querySelector(BLOCKS) !== null) continue;
      const text = el.textContent;
      if (text === null || !HAS_JP.test(text)) continue;
      if (isInterface(el)) {
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
  function scheduleScan(): void {
    if (scanTimer !== undefined) return;
    scanTimer = window.setTimeout(() => {
      scanTimer = undefined;
      scan();
    }, 3000);
  }

  function credit(s: Sentence): void {
    s.done = true;
    s.queued = false;
    if (counted.has(s.hash)) return;
    counted.add(s.hash);
    outbox.push({ h: s.hash, c: s.chars, w: countWords(s.text, s.chars) });
  }

  function flush(): void {
    const seconds = Math.floor(pendingMs / 1000);
    if (outbox.length === 0 && seconds < 1) return;
    const sentences = outbox;
    outbox = [];
    pendingMs -= seconds * 1000;
    try {
      chrome.runtime.sendMessage(
        { key: "statsRead", request: { sentences, seconds } },
        () => void chrome.runtime.lastError,
      );
    } catch (_e) {
      // extension was reloaded
    }
  }

  function tick(): void {
    const now = Date.now();
    const dt = Math.min(now - lastTick, 2000);
    lastTick = now;
    if (
      document.visibilityState !== "visible" ||
      now - lastActive > IDLE_MS ||
      visible.size === 0
    ) {
      return;
    }
    pendingMs += dt;
    bucket = Math.min(BUCKET_MAX, bucket + (dt / 1000) * READ_CPS);

    const onScreen = new Set<Sentence>();
    for (const block of visible) {
      eachVisibleSentence(block, (s, r) => {
        if (s.done || !mostlyOnScreen(r)) return;
        onScreen.add(s);
        s.ms += dt;
        if (s.ms >= MIN_ON_SCREEN_MS && !s.queued) {
          s.queued = true;
          queue.push(s);
        }
      });
    }

    // sentences that left the screen before being credited are dropped
    queue = queue.filter((s) => {
      if (onScreen.has(s)) return true;
      s.queued = false;
      return false;
    });
    while (queue.length > 0) {
      const s = queue[0];
      if (bucket < Math.min(s.chars, BUCKET_MAX)) break;
      queue.shift();
      bucket = Math.max(0, bucket - s.chars);
      credit(s);
    }
  }

  const touch = () => {
    lastActive = Date.now();
  };
  for (const ev of ["scroll", "touchstart", "touchmove", "pointerdown", "keydown", "click"]) {
    window.addEventListener(ev, touch, { passive: true, capture: true });
  }

  window.setInterval(tick, 1000);
  window.setInterval(flush, FLUSH_MS);
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") flush();
  });
  window.addEventListener("pagehide", flush);

  scan();
  new MutationObserver(scheduleScan).observe(document.documentElement, {
    childList: true,
    subtree: true,
  });
}

try {
  if (
    window.top === window &&
    typeof chrome !== "undefined" &&
    typeof chrome.runtime?.sendMessage === "function"
  ) {
    start();
  }
} catch (e) {
  console.error("Reading stats could not start", e);
}
""")

p = ext / "content/index.ts"
s = p.read_text()
p.write_text('import "./readingStats";\n' + s)

# ---------- popup: statistics instead of the power/settings buttons ----------
(ext / "popup/StatsPage.svelte").write_text("""<script lang="ts">
  import Page from "components/Page.svelte";
  import StatsView from "./StatsView.svelte";
</script>

<Page>
  <StatsView />
</Page>
""")

(ext / "popup/StatsView.svelte").write_text("""<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import {
    loadStats,
    summarize,
    streak,
    lastDays,
    resetStats,
    removeMinedWord,
    localDate,
    STATS_KEY,
    type StatsData,
  } from "extension/stats";

  let data: StatsData = { days: {} };
  let confirmReset = false;
  let confirmTimer: number | undefined;

  async function refresh(): Promise<void> {
    data = await loadStats();
  }

  function onChange(changes: Record<string, unknown>): void {
    if (STATS_KEY in changes) void refresh();
  }

  onMount(() => {
    void refresh();
    chrome.storage.onChanged.addListener(onChange);
  });

  onDestroy(() => {
    chrome.storage.onChanged.removeListener(onChange);
  });

  function onReset(): void {
    if (!confirmReset) {
      confirmReset = true;
      confirmTimer = window.setTimeout(() => (confirmReset = false), 5000);
      return;
    }
    window.clearTimeout(confirmTimer);
    confirmReset = false;
    void resetStats().then(refresh);
  }

  const fmt = (n: number) => n.toLocaleString("ru-RU");

  function fmtTime(seconds: number): string {
    const minutes = Math.round(seconds / 60);
    if (minutes < 60) return minutes + " мин";
    return Math.floor(minutes / 60) + " ч " + (minutes % 60) + " мин";
  }

  function speed(read: number, seconds: number): string {
    if (seconds < 60 || read === 0) return "—";
    return fmt(Math.round(read / (seconds / 60)));
  }

  function weekday(date: string): string {
    const [y, m, d] = date.split("-").map(Number);
    return new Date(y, m - 1, d).toLocaleDateString("ru-RU", {
      weekday: "short",
    });
  }

  $: columns = [
    { title: "Сегодня", s: summarize(data, 1) },
    { title: "7 дней", s: summarize(data, 7) },
    { title: "Всё время", s: summarize(data, null) },
  ];
  $: days = lastDays(data, 7);
  $: maxRead = Math.max(1, ...days.map((d) => d.read));
  $: streakDays = streak(data);
  $: todayWords = data.days[localDate()]?.mined ?? [];
</script>

<div class="stats">
  <div class="title">Статистика</div>
  <table>
    <thead>
      <tr>
        <th></th>
        {#each columns as c}
          <th>{c.title}</th>
        {/each}
      </tr>
    </thead>
    <tbody>
      <tr>
        <td>Слов в Anki</td>
        {#each columns as c}
          <td>{fmt(c.s.minedWords)}</td>
        {/each}
      </tr>
      <tr>
        <td>Кандзи (уник.)</td>
        {#each columns as c}
          <td>{fmt(c.s.kanji)}</td>
        {/each}
      </tr>
      <tr>
        <td>Прочитано предложений</td>
        {#each columns as c}
          <td>{fmt(c.s.sentences)}</td>
        {/each}
      </tr>
      <tr>
        <td>Прочитано слов</td>
        {#each columns as c}
          <td>{fmt(c.s.readWords)}</td>
        {/each}
      </tr>
      <tr>
        <td>Прочитано знаков</td>
        {#each columns as c}
          <td>{fmt(c.s.read)}</td>
        {/each}
      </tr>
      <tr>
        <td>Время чтения</td>
        {#each columns as c}
          <td>{c.s.time > 0 ? fmtTime(c.s.time) : "—"}</td>
        {/each}
      </tr>
      <tr>
        <td>Скорость, зн./мин</td>
        {#each columns as c}
          <td>{speed(c.s.read, c.s.time)}</td>
        {/each}
      </tr>
    </tbody>
  </table>

  <div class="streak">
    Серия: <b>{streakDays}</b>
    {streakDays === 1 ? "день" : "дн."} подряд
  </div>

  <div class="chart-title">Прочитано знаков за 7 дней</div>
  <div class="chart">
    {#each days as d}
      <div class="col">
        <div class="value">{d.read > 0 ? fmt(d.read) : ""}</div>
        <div class="bar-area">
          <div class="bar" style="height: {Math.round((d.read / maxRead) * 100)}%"></div>
        </div>
        <div class="day">{weekday(d.date)}</div>
        <div class="mined">{d.mined > 0 ? "+" + d.mined : ""}</div>
      </div>
    {/each}
  </div>
  <div class="hint">Под днём: слов добавлено в Anki</div>

  {#if todayWords.length > 0}
    <div class="chart-title">Добавлено сегодня (нажмите на слово, чтобы убрать из счёта)</div>
    <div class="words">
      {#each todayWords as w}
        <button class="word" on:click={() => void removeMinedWord(w)}>{w}</button>
      {/each}
    </div>
  {/if}

  <button class="reset" class:confirm={confirmReset} on:click={onReset}>
    {confirmReset ? "Нажмите ещё раз: удалить всё" : "Сбросить статистику"}
  </button>
</div>

<style>
  .stats {
    padding: 1rem 14px 1.5rem;
    font-size: 1.3rem;
  }

  .title {
    font-weight: bold;
    font-size: 1.15em;
    margin-bottom: 0.6em;
  }

  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.95em;
  }

  th {
    text-align: right;
    font-weight: normal;
    color: var(--text-light);
    padding: 0.2em 0.3em;
    white-space: nowrap;
  }

  td {
    text-align: right;
    padding: 0.4em 0.3em;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }

  th:first-child,
  td:first-child {
    text-align: left;
    padding-left: 0;
    white-space: normal;
  }

  tbody tr + tr td {
    border-top: 1px solid var(--border);
  }

  .streak {
    margin-top: 1em;
  }

  .chart-title {
    margin-top: 1em;
    color: var(--text-light);
    font-size: 0.9em;
  }

  .chart {
    display: flex;
    gap: 0.3em;
    margin-top: 0.4em;
  }

  .col {
    flex: 1 1 0;
    min-width: 0;
    text-align: center;
    font-size: 0.75em;
  }

  .value {
    height: 1.3em;
    color: var(--text-light);
    overflow: hidden;
  }

  .bar-area {
    height: 4.5em;
    display: flex;
    align-items: flex-end;
  }

  .bar {
    width: 100%;
    background-color: var(--accent);
    border-radius: 0.25em 0.25em 0 0;
    min-height: 2px;
  }

  .day {
    margin-top: 0.3em;
  }

  .mined {
    height: 1.3em;
    color: var(--text-light);
  }

  .hint {
    margin-top: 0.4em;
    color: var(--text-faint);
    font-size: 0.75em;
  }

  .words {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4em;
    margin-top: 0.5em;
  }

  .word {
    padding: 0.3em 0.7em;
    border: 1px solid var(--border);
    border-radius: 0.4em;
    font-size: 0.9em;
    text-align: center;
  }

  .reset {
    display: block;
    width: 100%;
    margin-top: 1.4em;
    padding: 0.7em 1em;
    text-align: center;
    border: 1px solid var(--border);
    border-radius: 0.5em;
    color: var(--text-warn);
    font-size: 0.9em;
  }

  .reset.confirm {
    background-color: var(--text-warn);
    border-color: var(--text-warn);
    color: #ffffff;
  }
</style>
""")

p = ext / "popup/index.ts"
s = p.read_text()
s = replace_once(s, 'import PopupPage from "./PopupPage.svelte";',
                 'import PopupPage from "./StatsPage.svelte";', "popup page")
p.write_text(s)
p = ext.parent / "platform/ios/index.ts"
s = p.read_text()
s = replace_once(s, "  getDictMetadata: [null, DictionaryMetadata];\n}",
                 "  getDictMetadata: [null, DictionaryMetadata];\n  loadStats: [null, unknown];\n  saveStats: [unknown, null];\n}", "app message map")
p.write_text(s)

# marker "already in Anki" in the dictionary entry badges
p = ext.parent / "components/dictionary/Badges.svelte"
s = p.read_text()
s = replace_once(s, "  let requestId = 0;\n", """  let requestId = 0;
  let mined: { exact: string[]; related: string[] } = { exact: [], related: [] };
  let minedRequestId = 0;

  function loadMined(entry: Entry): void {
    mined = { exact: [], related: [] };
    if (entry.type !== "word") return;
    // eslint-disable-next-line
    const rt = (globalThis as any).chrome?.runtime;
    if (rt === undefined || typeof rt.sendMessage !== "function") return;
    const forms = entry.kanjis.map((k) => k.kanji);
    if (forms.length === 0) forms.push(...entry.readings.map((r) => r.reading));
    const id = ++minedRequestId;
    // eslint-disable-next-line
    rt.sendMessage({ key: "minedLookup", request: { forms } }, (resp: any) => {
      void rt.lastError;
      if (id !== minedRequestId) return;
      if (resp?.success === true && resp.resp !== undefined) {
        mined = resp.resp;
      }
    });
  }
""", "mined state")
s = replace_once(s, "  $: loadFrequencies(entry);", "  $: loadFrequencies(entry);\n  $: loadMined(entry);", "mined reactive")
s = replace_once(s, "  $: hasBadges = isCommon || isName || freqs.length > 0;",
                 "  $: hasBadges =\n    isCommon ||\n    isName ||\n    freqs.length > 0 ||\n    mined.exact.length > 0 ||\n    mined.related.length > 0;", "has badges")
s = replace_once(s, "    {#each freqs as f}", """    {#if mined.exact.length > 0}
      <div class="badge in-anki">в Anki</div>
    {:else if mined.related.length > 0}
      <div class="badge related">≈ {mined.related.slice(0, 2).join(", ")}</div>
    {/if}
    {#each freqs as f}""", "mined markup")
s = replace_once(s, "  .freq {", "  .in-anki {\n    --badge-color: #5fd068;\n  }\n\n  .related {\n    --badge-color: #9a9aa0;\n  }\n\n  .freq {", "mined css")
p.write_text(s)
print("stats patch OK")
