# v2.05: fixes.
# - The check mark after ⊕ when the word of the note is not a written form of the entry (いたずら in the text, the
#   entry 悪戯): the block that marks every form of the tapped entry runs inside Svelte's update, and a store set
#   there reaches only the reactive statements below it in the same update; `added` stood above it and stayed false,
#   so ⊕ came back. `added` now comes after it.
# - The bundle ID of the .ipa is the certificate's (app.uva7695.libra5806): set in the workflow when it packs the app.
import pathlib


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


entry = pathlib.Path("src/main/src/components/dictionary/DicEntryView.svelte")
s = entry.read_text(encoding="utf-8")
s = once(s, '''  $: added = mined && isAdded(entry, $addedWords);
  // the add has finished''', '''  // the add has finished''', "added above the block")
s = once(s, '''      addedWords.update((words) => new Set([...words, ...forms]));
    }
  }
</script>''', '''      addedWords.update((words) => new Set([...words, ...forms]));
    }
  }
  // below the block above: a store set inside a reactive block reaches only the statements after it in that update
  $: added = mined && isAdded(entry, $addedWords);
</script>''', "added after the block")
entry.write_text(s, encoding="utf-8")
print("v2.05 fixes applied")
