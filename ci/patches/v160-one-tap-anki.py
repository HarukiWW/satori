# v1.60: the ⊕ button of a dictionary entry adds the note (or puts it in the player's mining queue) right away, without
# the "Добавить в Anki" form: in the app and the player, in the Safari tooltip and in the extension popup. The adding
# is one shared function (components/anki/addNoteNow.ts); a field that fails to load (audio) stays empty.
import pathlib

main = pathlib.Path("src/main/src")


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


def patch(path, edits):
    p = main / path
    s = p.read_text(encoding="utf-8")
    for old, new, label in edits:
        s = once(s, old, new, label)
    for gone in ["AddToAnki", "previewIsVisible", "previewNoteData"]:
        assert gone not in s, path + ": left over " + gone
    p.write_text(s, encoding="utf-8")


(main / "components/anki/addNoteNow.ts").write_text('''import type { AnkiNote, LoadingAnkiNote } from "lib/anki";
import { AnkiApi } from "@platform/anki";
import { Toast } from "lib/toast";
import { YomikiriError } from "lib/error";
import HourglassToastIcon from "components/toast/HourglassToastIcon.svelte";

let adding = false;

/**
 * Adds the note right away, without the preview form. A second tap while adding does nothing.
 * `false` from the platform: the note waits (Anki not connected, or the player's mining queue).
 */
export async function addNoteNow(build: () => LoadingAnkiNote): Promise<void> {
  if (adding) return;
  adding = true;
  try {
    const note = build();
    for (const field of note.fields) {
      try {
        field.value = await field.value;
      } catch (err) {
        console.error(err);
        field.value = "";
      }
    }
    const added = await AnkiApi.addNote(note as AnkiNote);
    if (added) {
      Toast.success("Добавлено в Anki");
    } else {
      Toast.success("Заметка отложена, добавится позже", "", {
        icon: HourglassToastIcon,
        duration: 3000,
      });
    }
  } catch (err) {
    Toast.yomikiriError(YomikiriError.from(err));
  } finally {
    adding = false;
  }
}
''', encoding="utf-8")

# ---------- the app and the player ----------
patch("iosapp/DictionaryView.svelte", [
    ('  import AddToAnki from "components/anki/AddToAnki.svelte";\n',
     '  import { addNoteNow } from "components/anki/addNoteNow";\n', "app import"),
    ("""  import {
    type LoadingAnkiNote,
    type AnkiBuilderData,
    buildAnkiNote,
  } from "lib/anki";
""", """  import { type AnkiBuilderData, buildAnkiNote } from "lib/anki";
""", "app anki import"),
    ("""  let previewIsVisible = false;
  let previewNoteData: LoadingAnkiNote;

""", "", "app state"),
    ("""    let note = buildAnkiNote({ config }, markerData);

    previewNoteData = note;
    previewIsVisible = true;
  }

  function onBack() {
    previewIsVisible = false;
  }

  function noteAdded() {
    previewIsVisible = false;
  }
""", """    void addNoteNow(() => buildAnkiNote({ config }, markerData));
  }
""", "app handler"),
    ('  <div class="tokenize-container" class:previewIsVisible>\n', '  <div class="tokenize-container">\n', "app class"),
    ("""  {#if previewIsVisible}
    <AddToAnki noteData={previewNoteData} {onBack} {noteAdded} />
  {/if}
""", "", "app form"),
    ("""  .tokenize-container.previewIsVisible {
    display: none;
  }

""", "", "app css"),
])

# the player's queue answers false: the toast says the note waits
patch("platform/iosapp/anki.ts", [("""    const opened = await Platform.messageWebview("openLink", url);
    if (opened !== false) {
      try {
        await recordMinedNoteApp(note);
      } catch (e) {
        console.error(e);
      }
    }
    return true;
  }
""", """    const opened = await Platform.messageWebview("openLink", url);
    if (opened === false) {
      return false;
    }
    try {
      await recordMinedNoteApp(note);
    } catch (e) {
      console.error(e);
    }
    return true;
  }
""", "app add result")])

# ---------- the extension popup ----------
patch("extension/popup/PopupView.svelte", [
    ("""  import {
    type LoadingAnkiNote,
    type AnkiBuilderData,
    buildAnkiNote,
  } from "lib/anki";
""", """  import { type AnkiBuilderData, buildAnkiNote } from "lib/anki";
""", "popup anki import"),
    ('  import AddToAnki from "../../components/anki/AddToAnki.svelte";\n',
     '  import { addNoteNow } from "components/anki/addNoteNow";\n', "popup import"),
    ("""  let previewIsVisible = false;
  let previewNoteData: LoadingAnkiNote;
""", "", "popup state"),
    ("""    let note = buildAnkiNote({ config }, markerData);
    previewNoteData = note;
    previewIsVisible = true;
  }

  function onBack() {
    previewIsVisible = false;
  }

  function noteAdded() {
    previewIsVisible = false;
  }
""", """    void addNoteNow(() => buildAnkiNote({ config }, markerData));
  }
""", "popup handler"),
    ('  <div class="tokenize-container" class:previewIsVisible>\n', '  <div class="tokenize-container">\n', "popup class"),
    ("""  {#if previewIsVisible}
    <AddToAnki noteData={previewNoteData} {onBack} {noteAdded} />
  {/if}
""", "", "popup form"),
    ("""

  .tokenize-container.previewIsVisible {
    display: none;
  }
""", "", "popup css"),
])

# ---------- the Safari tooltip ----------
patch("extension/content/Tooltip.svelte", [
    ("""  import {
    type LoadingAnkiNote,
    type AnkiBuilderData,
    buildAnkiNote,
  } from "lib/anki";
  import AddToAnki from "../../components/anki/AddToAnki.svelte";
""", """  import { type AnkiBuilderData, buildAnkiNote } from "lib/anki";
  import { addNoteNow } from "components/anki/addNoteNow";
""", "tooltip imports"),
    ("""  import { Toast } from "lib/toast";
  import { YomikiriError } from "lib/error";
""", "", "tooltip toast imports"),
    ("""  let previewIsVisible = false;
  let previewNoteData: LoadingAnkiNote;
""", "", "tooltip state"),
    ("""  async function onBack() {
    previewIsVisible = false;
    await tick();
    updateHeight();
  }

  async function onTokenizeResultChanged(_tokenizeResult: TokenizeResult) {
    previewIsVisible = false;
    selectedTool = null;
""", """  async function onTokenizeResultChanged(_tokenizeResult: TokenizeResult) {
    selectedTool = null;
""", "tooltip back"),
    ("""  async function selectedEntryForAnki(request: SelectedEntryForAnki) {
    try {
      await _selectedEntryForAnki(request);
    } catch (err) {
      Toast.yomikiriError(YomikiriError.from(err));
    }
  }
  async function _selectedEntryForAnki(request: SelectedEntryForAnki) {
""", """  function selectedEntryForAnki(request: SelectedEntryForAnki) {
""", "tooltip handler head"),
    ("""    const note = buildAnkiNote({ config }, markerData);
    previewNoteData = note;
    previewIsVisible = true;
    await tick();
    updateHeight();
  }
""", """    void addNoteNow(() => buildAnkiNote({ config }, markerData));
  }
""", "tooltip handler body"),
    ("""  function noteAdded() {
    onClose();
    previewIsVisible = false;
  }

""", "", "tooltip note added"),
    ('  <div class="dictionary-view" class:previewIsVisible>\n', '  <div class="dictionary-view">\n', "tooltip class"),
    ("""  {#if previewIsVisible}
    <div class="anki-preview">
      <AddToAnki noteData={previewNoteData} {onBack} {noteAdded} />
    </div>
  {/if}
""", "", "tooltip form"),
    ("""  .dictionary-view.previewIsVisible {
    display: none;
  }

""", "", "tooltip css"),
    ("""

  .anki-preview {
    max-height: inherit;
  }
""", "", "tooltip preview css"),
])
print("v1.60 one tap Anki applied")
