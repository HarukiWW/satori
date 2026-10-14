# v1.67: after a tap on ⊕ the button shows a spinner until the note is added (or put in the mining queue), then the
# check mark; on an error ⊕ comes back. The spinner stays at least 0.45 s, so a fast add is still seen.
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


patch("src/main/src/components/anki/addNoteNow.ts", [
    ("""let adding = false;
""", """let adding = false;

/** true while a note is being added: the ⊕ button that was tapped shows a spinner */
export const addingNote = writable(false);

/** the spinner shows at least this long, a fast add would only flash it */
const MIN_SPINNER_MS = 450;
""", "store"),
    ("""  if (adding) return;
  adding = true;
  try {
""", """  if (adding) return;
  adding = true;
  addingNote.set(true);
  const started = Date.now();
  try {
""", "start"),
    ("""  } finally {
    adding = false;
  }
}""", """  } finally {
    const left = MIN_SPINNER_MS - (Date.now() - started);
    if (left > 0) await new Promise((resolve) => setTimeout(resolve, left));
    adding = false;
    addingNote.set(false);
  }
}""", "finish"),
])

patch("src/main/src/components/dictionary/DicEntryView.svelte", [
    ('  import { addedWords } from "components/anki/addNoteNow";\n',
     '  import { addedWords, addingNote } from "components/anki/addNoteNow";\n', "import"),
    ("""  $: mainFormRuby = generateMainFormRuby(entry);
  $: added = mined && isAdded(entry, $addedWords);
""", """  /** this entry's ⊕ was tapped and its note is on the way */
  let pressed = false;

  $: mainFormRuby = generateMainFormRuby(entry);
  $: added = mined && isAdded(entry, $addedWords);
  // the add has finished (added, queued or failed): the check mark or ⊕ again
  $: if (pressed && !$addingNote) pressed = false;
""", "pressed state"),
    ("""      {#if $ankiEnabledConfig && entry.type === "word" && added}
        <IconedButton size="2rem" disabled={true} color="#5fd068">
          <IconCheckmarkCircle />
        </IconedButton>
      {:else if $ankiEnabledConfig && entry.type === "word"}
        <IconedButton
          size="2rem"
          highlight={$selectedMeaning?.entry === entry}
          on:click={() => {
            onSelectEntryForAnki({
""", """      {#if $ankiEnabledConfig && entry.type === "word" && pressed}
        <IconedButton size="2rem" disabled={true}>
          <span class="spinner" aria-label="Добавляю" />
        </IconedButton>
      {:else if $ankiEnabledConfig && entry.type === "word" && added}
        <IconedButton size="2rem" disabled={true} color="#5fd068">
          <IconCheckmarkCircle />
        </IconedButton>
      {:else if $ankiEnabledConfig && entry.type === "word"}
        <IconedButton
          size="2rem"
          highlight={$selectedMeaning?.entry === entry}
          on:click={() => {
            // set before the add starts (it marks the store at once), so the spinner shows right away
            pressed = true;
            onSelectEntryForAnki({
""", "buttons"),
    ("""  .icons {
    flex: 0 0 auto;
    margin-left: auto;

    display: flex;
  }
</style>""", """  .icons {
    flex: 0 0 auto;
    margin-left: auto;

    display: flex;
  }

  .spinner {
    display: block;
    box-sizing: border-box;
    width: 100%;
    height: 100%;
    border: 2.5px solid var(--button-light);
    border-top-color: transparent;
    border-radius: 50%;
    animation: entry-spin 0.8s linear infinite;
  }

  @keyframes entry-spin {
    to {
      transform: rotate(360deg);
    }
  }
</style>""", "spinner css"),
])
print("v1.67 adding spinner applied")
