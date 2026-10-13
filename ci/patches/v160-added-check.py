# v1.60: a word already added shows a green check mark that can't be tapped instead of ⊕: a card of the statistics
# (the same lookup as the "Anki" badge), a note added in this session (also in Safari), or a note in the player's
# mining queue (the web asks the app with "queuedWords").
import pathlib


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


def patch(path, edits):
    p = pathlib.Path(path)
    s = p.read_text(encoding="utf-8")
    for old, new, label in edits:
        s = once(s, old, new, label)
    p.write_text(s, encoding="utf-8")


main = "src/main/src/"

# ---------- the words added in this session ----------
patch(main + "components/anki/addNoteNow.ts", [
    ('import HourglassToastIcon from "components/toast/HourglassToastIcon.svelte";\n',
     'import HourglassToastIcon from "components/toast/HourglassToastIcon.svelte";\n'
     'import { wordFromNoteLite } from "lib/statsLite";\n'
     'import { writable } from "svelte/store";\n', "imports"),
    ("let adding = false;\n", """let adding = false;

/** Words of the notes added (or put in a queue) in this session, as the statistics keep them. */
export const addedWords = writable(new Set<string>());
""", "store"),
    ("""    const added = await AnkiApi.addNote(note as AnkiNote);
""", """    const added = await AnkiApi.addNote(note as AnkiNote);
    const word = wordFromNoteLite(note as AnkiNote);
    if (word !== "") {
      addedWords.update((words) => new Set(words).add(word));
    }
""", "mark added"),
])

# ---------- the entry: check mark instead of ⊕ ----------
patch(main + "components/dictionary/Badges.svelte", [
    ("  let mined: { exact: string[]; related: string[] } = { exact: [], related: [] };\n",
     "  /** read by the entry (bound): cards in Anki and notes in the player's queue */\n"
     "  export let mined: { exact: string[]; related: string[]; queued?: string[] } = {\n"
     "    exact: [],\n    related: [],\n  };\n", "mined prop"),
])
patch(main + "components/dictionary/DicEntryView.svelte", [
    ('  import IconAddCircleOutline from "@icons/add-circle-outline.svg";\n',
     '  import IconAddCircleOutline from "@icons/add-circle-outline.svg";\n'
     '  import IconCheckmarkCircle from "@icons/checkmark-circle.svg";\n'
     '  import { addedWords } from "components/anki/addNoteNow";\n', "imports"),
    ("""  $: mainFormRuby = generateMainFormRuby(entry);
""", """  let mined: { exact: string[]; related: string[]; queued?: string[] } = {
    exact: [],
    related: [],
  };

  /** Already in Anki, in the player's queue, or added in this session. */
  function isAdded(entry: Entry, words: Set<string>): boolean {
    if (entry.type !== "word") return false;
    if (mined.exact.length > 0 || (mined.queued ?? []).length > 0) return true;
    const forms = entry.kanjis.map((k) => k.kanji);
    if (forms.length === 0) forms.push(...entry.readings.map((r) => r.reading));
    return forms.some((form) => words.has(form));
  }

  $: mainFormRuby = generateMainFormRuby(entry);
  $: added = mined && isAdded(entry, $addedWords);
""", "added state"),
    ("""      {#if $ankiEnabledConfig && entry.type === "word"}
        <IconedButton
""", """      {#if $ankiEnabledConfig && entry.type === "word" && added}
        <IconedButton size="2rem" disabled={true} color="#5fd068">
          <IconCheckmarkCircle />
        </IconedButton>
      {:else if $ankiEnabledConfig && entry.type === "word"}
        <IconedButton
""", "check mark"),
    ("  <Badges {entry} />\n", "  <Badges {entry} bind:mined />\n", "bind mined"),
])

# ---------- the app: queued words of the player ----------
patch(main + "platform/iosapp/index.ts", [("  openLink: [string, boolean | null];\n",
                                           "  openLink: [string, boolean | null];\n  queuedWords: [null, string[] | null];\n",
                                           "queuedWords type")])
patch(main + "platform/iosapp/appStats.ts", [("""export async function lookupMinedApp(
  forms: string[],
): Promise<{ exact: string[]; related: string[] }> {
  return findMinedLite(await loadApp(), forms);
}""", """export async function lookupMinedApp(
  forms: string[],
): Promise<{ exact: string[]; related: string[]; queued: string[] }> {
  const found = findMinedLite(await loadApp(), forms);
  let queued: string[] = [];
  try {
    const words = await Platform.messageWebview("queuedWords", null);
    queued = (words ?? []).filter((w) => forms.includes(w));
  } catch (e) {
    console.error(e);
  }
  return { ...found, queued };
}""", "lookup with queue")])
patch("src/safari/Shared (iOS)/YomikiriWebView.swift", [
    ("""            case "loadStats":
                return try Storage.stats.get()
""", """            case "queuedWords":
                // the words of the player's mining queue (set by the app)
                let words: [String] = await MainActor.run { yomikiriQueuedWordsHook?() ?? [] }
                return try jsonSerialize(obj: words)
            case "loadStats":
                return try Storage.stats.get()
""", "queuedWords message"),
    ("var yomikiriOpenLinkHook: ((URL) -> URL?)? = nil\n",
     "var yomikiriOpenLinkHook: ((URL) -> URL?)? = nil\n"
     "/// The words of the notes in the player's mining queue.\n"
     "var yomikiriQueuedWordsHook: (() -> [String])? = nil\n", "queued words hook"),
])
patch("src/safari/iOS (App)/HelpView.swift", [
    ("""        MiningFrame.jpegBase64 = nil
        let video = url.lastPathComponent
        yomikiriOpenLinkHook = { link in
""", """        MiningFrame.jpegBase64 = nil
        let video = url.lastPathComponent
        yomikiriQueuedWordsHook = {
            MiningQueue.shared.entries.map { MiningQueue.statsWord(of: $0.url) }
        }
        yomikiriOpenLinkHook = { link in
""", "set queued words hook"),
    ("""            yomikiriOpenLinkHook = nil
            MiningFrame.jpegBase64 = nil
""", """            yomikiriOpenLinkHook = nil
            yomikiriQueuedWordsHook = nil
            MiningFrame.jpegBase64 = nil
""", "clear queued words hook"),
])
print("v1.60 added check mark applied")
