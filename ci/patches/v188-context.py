# v1.88: the meaning that fits the sentence. When the dictionary opens on a word inside a sentence (the player, the
# reader, a list of unknown words), the first entry's meaning is chosen by the sentence: the part of speech the word
# has there first, then the Russian translation of the sentence (the meaning whose words it uses). Only a clear
# winner is chosen; it is highlighted, and ⊕ puts only it into the note. A tap elsewhere takes the choice away, as
# before.
import pathlib


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


web = pathlib.Path("src/main/src")

p = web / "lib/dicEntry.ts"
t = p.read_text(encoding="utf-8")
t = once(t, "const unidicPosMap: Record<string, PartOfSpeech> = {\n",
         "export const unidicPosMap: Record<string, PartOfSpeech> = {\n", "export pos map")
p.write_text(t, encoding="utf-8")

p = web / "components/dictionary/Tokenize.svelte"
t = p.read_text(encoding="utf-8")
t = once(t, '''      <DicEntriesView
        entries={tokenizeResult.entries}
''', '''      <DicEntriesView
        entries={tokenizeResult.entries}
        sentence={searchText}
        token={tokenizeResult.tokens[tokenizeResult.tokenIdx]}
''', "entries context")
p.write_text(t, encoding="utf-8")

p = web / "components/dictionary/DicEntriesView.svelte"
t = p.read_text(encoding="utf-8")
t = once(t, '''<script lang="ts">
  import type { Entry } from "lib/dicEntry";
''', '''<script lang="ts">
  import { type Entry, unidicPosMap } from "lib/dicEntry";
  import { Platform } from "@platform";
''', "context imports")
t = once(t, '''  let model: DicEntriesModel = new DicEntriesModel();
''', '''  /** the text the dictionary was opened on, and the word of it */
  export let sentence = "";
  // eslint-disable-next-line
  export let token: any = undefined;

  let model: DicEntriesModel = new DicEntriesModel();

  /** Russian words of a text: lower case, Cyrillic and Latin letters only */
  function words(text: string): string[] {
    return text
      .toLowerCase()
      .split(/[^a-zа-яё]+/)
      .filter((w) => w.length >= 3);
  }

  /** a meaning matches a word of the translation when they share a stem (звонить, звонит) */
  function shares(gloss: string, translated: string[]): boolean {
    return words(gloss).some((w) => {
      const stem = w.slice(0, Math.max(3, w.length - 2));
      return translated.some((t) => t.startsWith(stem));
    });
  }

  let contextRequest = 0;

  /** The meaning of the first entry that fits the sentence, when one clearly does. */
  async function chooseByContext(entries: Entry[], sentence: string, token: any): Promise<void> {
    const id = ++contextRequest;
    const entry = entries[0];
    // a word inside a sentence, not a word looked up alone
    if (entry === undefined || entry.type !== "word" || token === undefined) return;
    if (sentence.trim().length < String(token.text ?? "").length + 3) return;
    const all = entry.groupedSenses.flatMap((group) => group.senses.map((sense) => ({ group, sense })));
    if (all.length < 2) return;
    const pos = unidicPosMap[String(token.pos ?? "")];
    let candidates = pos === undefined ? all : all.filter((c) => c.group.pos.includes(pos));
    if (candidates.length === 0) candidates = all;
    if (candidates.length > 1) {
      let translated: string[];
      try {
        translated = words((await Platform.translate(sentence)).translated);
      } catch (err) {
        return;
      }
      if (id !== contextRequest) return;
      const scores = candidates.map((c) => c.sense.meanings.filter((m) => shares(m, translated)).length);
      const best = Math.max(...scores);
      if (best === 0 || scores.filter((score) => score === best).length > 1) return;
      candidates = [candidates[scores.indexOf(best)]];
    }
    // the part of speech alone leaves one: chosen only when the entry has meanings of other parts of speech
    if (candidates.length === 1 && id === contextRequest) {
      model.selectSense(entry, candidates[0].sense, candidates[0].group.pos);
    }
  }
''', "context logic")
t = once(t, '''  $: onEntriesChange(entries);
''', '''  $: onEntriesChange(entries);
  $: void chooseByContext(entries, sentence, token);
''', "context reactive")
p.write_text(t, encoding="utf-8")
print("v1.88 context applied")
