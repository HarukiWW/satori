# v2.24: the backup of AnkiMobile is read without Anki's collation "unicase".
# - The real error of the note types (2.23 showed it whole): «no such collation sequence: unicase; no query solution;
#   no query solution». Anki compares its names by its own collation "unicase", which sql.js does not have, and the
#   tables of fields and card types have a primary key of their own (WITHOUT ROWID): the SQLite of sql.js cannot read
#   them at all — the first query fails on the collation, and then the table is marked unusable («no query solution»).
#   No query could help. Now the collation leaves the schema before sql.js opens the database: «COLLATE unicase»
#   becomes «COLLATE binary » (the same length, so the pages stay valid); the order of the names does not matter for
#   reading. On the backup of 2026-10-19 every query works then (27 note types, quick_check ok).
# - The words of a backup come from the right fields again (Furigana, Word): the field names were never read on the
#   phone, so every note gave its first field.
import pathlib


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


ai = pathlib.Path("src/main/src/lib/ankiImport.ts")
a = ai.read_text(encoding="utf-8")
a = once(a, '''function collectionBytes(data: Uint8Array): Uint8Array {
  const files = unzipSync(data);
  if (files["collection.anki21b"]) return decompress(files["collection.anki21b"]);
  if (files["collection.anki2"]) return files["collection.anki2"];''', '''/** Anki compares its names by its own collation "unicase", unknown to sql.js: a table with such a column and a
 * primary key of its own (fields, templates) cannot be read at all — the first query fails with «no such collation
 * sequence: unicase», the next ones with «no query solution». In the schema it becomes "binary " (the same length, so
 * the pages stay valid); for reading, the order of the names does not matter. */
export function withoutUnicase(bytes: Uint8Array): Uint8Array {
  const from = new TextEncoder().encode("COLLATE unicase");
  const to = new TextEncoder().encode("COLLATE binary ");
  for (let i = bytes.indexOf(from[0]); i >= 0 && i <= bytes.length - from.length; i = bytes.indexOf(from[0], i + 1)) {
    let same = true;
    for (let j = 1; j < from.length && same; j++) {
      same = bytes[i + j] === from[j];
    }
    if (same) bytes.set(to, i);
  }
  return bytes;
}

function collectionBytes(data: Uint8Array): Uint8Array {
  const files = unzipSync(data);
  if (files["collection.anki21b"]) return withoutUnicase(decompress(files["collection.anki21b"]));
  if (files["collection.anki2"]) return withoutUnicase(files["collection.anki2"]);''', "without unicase")
ai.write_text(a, encoding="utf-8")
print("v2.24 unicase applied")
