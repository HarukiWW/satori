# v1.93: fixes.
# - Words with furigana keep their whole width: the layout gave a word exactly the width it measured, rounding took a
#   fraction of a point away and the text in the middle became "…" (歩…る, 呆気…られた, … for 中年), in the reader and
#   in the subtitles.
# - The live background: the patches wander on their own, keep away from each other and from the edges (now and then
#   two meet or one touches an edge), so they spread over the whole screen; only the background on screen is drawn
#   (each tab had its own running at 30 frames a second).
# - The backups of AnkiMobile: the folder «Anki» can be chosen too (its Backups is read); the check waits while the
#   queue is being sent and while a deck shared from AnkiMobile waits for its import.
# - ⊕ is faster: the translation of the sentence and the check of the word's audio start when the dictionary opens
#   on a word in a sentence, so the note is ready at once; one translation request per sentence.
import pathlib


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")

# ---------- words with furigana: no truncation ----------
s = once(s, '''                    ForEach(tokens) { token in
                        word(token)
                            .padding(.vertical, 4)
''', '''                    ForEach(tokens) { token in
                        // the whole word, even when the layout gives it a fraction of a point less
                        word(token)
                            .fixedSize()
                            .padding(.vertical, 4)
''', "subtitle words fixed size")
s = once(s, '''                    ForEach(tokens) { token in
                        word(token)
                            .padding(.vertical, fontSize * 0.17)
''', '''                    ForEach(tokens) { token in
                        // the whole word, even when the layout gives it a fraction of a point less
                        word(token)
                            .fixedSize()
                            .padding(.vertical, fontSize * 0.17)
''', "reader words fixed size")

# ---------- the backups ----------
s = once(s, '''    func check(force: Bool = false) {
        guard !importing, let folder = folder() else { return }
''', '''    func check(force: Bool = false) {
        guard !importing, let folder = folder() else { return }
        // not while notes go to AnkiMobile, not over a deck shared from AnkiMobile that waits for its import
        if !force, !MiningQueue.shared.sending.isEmpty || DeckInbox.waitingRecently {
            return
        }
''', "backup check waits")
s = once(s, '''        let files = (try? FileManager.default.contentsOfDirectory(at: folder, includingPropertiesForKeys: keys)) ?? []
        func date(_ file: URL) -> Date {
''', '''        // the folder «Anki» itself: its backups are in Backups
        var files = (try? FileManager.default.contentsOfDirectory(at: folder.appendingPathComponent("Backups", isDirectory: true),
                                                                  includingPropertiesForKeys: keys)) ?? []
        if !files.contains(where: { $0.pathExtension.lowercased() == "colpkg" }) {
            files = (try? FileManager.default.contentsOfDirectory(at: folder, includingPropertiesForKeys: keys)) ?? []
        }
        func date(_ file: URL) -> Date {
''', "backup subfolder")
s = once(s, '''        var text = "Выберите «На iPhone → Anki → Backups». Когда AnkiMobile сделает новый бэкап (при синхронизации), "
''', '''        var text = "Выберите «На iPhone → Anki» или Backups в ней. Когда AnkiMobile сделает новый бэкап (при синхронизации), "
''', "backup footer")

s = once(s, '''    static var pending: URL? {
        (try? FileManager.default.contentsOfDirectory(at: folder, includingPropertiesForKeys: nil))?.first
    }
''', '''    static var pending: URL? {
        (try? FileManager.default.contentsOfDirectory(at: folder, includingPropertiesForKeys: nil))?.first
    }

    /// A deck received in the last ten minutes and not imported yet (a copy left by an import that never ended does
    /// not count).
    static var waitingRecently: Bool {
        guard pending != nil,
              let made = (try? folder.resourceValues(forKeys: [.creationDateKey]))?.creationDate else { return false }
        return Date().timeIntervalSince(made) < 600
    }
''', "inbox waiting")

# ---------- the background ----------
start = s.index("@available(iOS 16.0, *)\nstruct SatoriBackdrop: View {")
end = s.index("\nextension View {\n    /// The live background under a list")
s = s[:start] + (pathlib.Path(__file__).resolve().parent / "v193-backdrop.swift").read_text(encoding="utf-8").strip("\n") + "\n" + s[end:]
hv.write_text(s, encoding="utf-8")

# ---------- web: the note is prepared when the dictionary opens ----------
web = pathlib.Path("src/main/src")
p = web / "platform/common/translate.ts"
t = p.read_text(encoding="utf-8")
t = once(t, "export async function getTranslation(text: string): Promise<TranslateResult> {\n",
         "async function fetchTranslation(text: string): Promise<TranslateResult> {\n", "translate rename")
t = t.rstrip("\n") + '''

const translationPending: Record<string, Promise<TranslateResult>> = {};

/** One request per sentence: the translation asked for early (the dictionary) and again (the note) is shared. */
export function getTranslation(text: string): Promise<TranslateResult> {
  if (!hasOwnProperty(translationPending, text)) {
    translationPending[text] = fetchTranslation(text).catch((err: unknown) => {
      delete translationPending[text];
      throw err;
    });
  }
  return translationPending[text];
}
'''
p.write_text(t, encoding="utf-8")

p = web / "lib/anki/ankiBuilder.ts"
t = p.read_text(encoding="utf-8")
t = once(t, '''addBuilder("audio", (_opts, data) => {
  const token = data.tokenized.tokens[data.tokenized.tokenIdx];
  const word = token.base;
  const reading = getReadingForForm(data.entry, word, false).reading || word;
  return Utils.PromiseWithProgress.fromPromise(
    findJpod101Audio(word, reading),
''', '''const jpod101Checks = new Map<string, Promise<string>>();

/** The check of a word's audio, started early (when the dictionary shows the word), so the note has it at once. */
export function prefetchJpod101Audio(word: string, reading: string): Promise<string> {
  const key = word + "|" + reading;
  let check = jpod101Checks.get(key);
  if (check === undefined) {
    check = findJpod101Audio(word, reading);
    jpod101Checks.set(key, check);
  }
  return check;
}

addBuilder("audio", (_opts, data) => {
  const token = data.tokenized.tokens[data.tokenized.tokenIdx];
  const word = token.base;
  const reading = getReadingForForm(data.entry, word, false).reading || word;
  return Utils.PromiseWithProgress.fromPromise(
    prefetchJpod101Audio(word, reading),
''', "audio prefetch")
p.write_text(t, encoding="utf-8")

p = web / "components/dictionary/Tokenize.svelte"
t = p.read_text(encoding="utf-8")
t = once(t, '''        sentence={searchText}
''', '''        sentence={tokenizeResult.tokens.map((t) => t.text).join("")}
''', "entries sentence of the note")
p.write_text(t, encoding="utf-8")

p = web / "components/dictionary/DicEntriesView.svelte"
t = p.read_text(encoding="utf-8")
t = once(t, '''  import { type Entry, unidicPosMap } from "lib/dicEntry";
''', '''  import { type Entry, unidicPosMap, getReadingForForm } from "lib/dicEntry";
  import { prefetchJpod101Audio } from "lib/anki/ankiBuilder";
''', "prefetch imports")
t = once(t, '''  $: void chooseByContext(entries, sentence, token);
''', '''  $: void chooseByContext(entries, sentence, token);

  /** In the app, the slow parts of the note (the translation of the sentence, the word's audio) start now. */
  // eslint-disable-next-line
  function prepareNote(entries: Entry[], sentence: string, token: any): void {
    // eslint-disable-next-line
    if ((globalThis as any).yomikiriRuntime?.isApp !== true) return;
    const entry = entries[0];
    if (entry === undefined || entry.type !== "word" || token === undefined) return;
    if (sentence.trim() !== "") void Platform.translate(sentence).catch(() => undefined);
    const word = String(token.base ?? "");
    if (word !== "") {
      void prefetchJpod101Audio(word, getReadingForForm(entry, word, false).reading || word);
    }
  }
  $: prepareNote(entries, sentence, token);
''', "prefetch call")
p.write_text(t, encoding="utf-8")
print("v1.93 fixes applied")
