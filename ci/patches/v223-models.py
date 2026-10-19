# v2.23: the note types of the backup are read by the first query that works.
# - 2.22 showed the error of the read: «no query solution». The SQLite of sql.js refuses NOT INDEXED on the tables
#   without rowid (fields, templates), and without it may read through the indexes of the names, which need the
#   collation "unicase" sql.js does not have. Every table is now asked by the first of several queries that works;
#   the first ones take a column the index of the names does not have (config, common), so SQLite reads the table
#   itself; the order is made in JavaScript, not by the query. The words of a backup use the same (with the field
#   names, not only the first field of every note).
import pathlib


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


ai = pathlib.Path("src/main/src/lib/ankiImport.ts")
a = ai.read_text(encoding="utf-8")

# the words: the field names by the same queries
a = once(a, '''  try {
    const rows = db.exec("select ntid, ord, name from fields order by ntid, ord");
    for (const row of rows[0] ? rows[0].values : []) {
      const key = String(row[0]);
      if (!out[key]) out[key] = [];
      out[key].push(String(row[2]));
    }
    if (Object.keys(out).length > 0) return out;
  } catch (e) {''', '''  try {
    for (const row of fieldRows(db, [])) {
      const key = String(row[0]);
      if (!out[key]) out[key] = [];
      out[key].push(String(row[2]));
    }
    if (Object.keys(out).length > 0) return out;
  } catch (e) {''', "field names")

a = once(a, '''function rowsOf(result: any[]): any[][] {
  return result[0] ? result[0].values : [];
}''', '''function rowsOf(result: any[]): any[][] {
  return result[0] ? result[0].values : [];
}

/** The rows of the first of the queries that works: sql.js has no collation "unicase" (Anki's indexes of the names
 * use it) and its SQLite refuses "not indexed" on a table without rowid («no query solution»). A query that takes a
 * column the index of the names has not (config, common) makes SQLite read the table itself. The errors of the
 * queries that failed go to `problems`. */
function firstRows(db: any, queries: string[], problems: string[]): any[][] {
  for (const query of queries) {
    try {
      return rowsOf(db.exec(query));
    } catch (e) {
      problems.push(e instanceof Error ? e.message : String(e));
    }
  }
  throw new Error(problems.join("; "));
}

/** ntid, ord, name… of the fields or card types, in the order of their note type (sorted here, not by a query). */
function byOrder(rows: any[][]): any[][] {
  return rows.sort((x, y) => Number(x[0]) - Number(y[0]) || Number(x[1]) - Number(y[1]));
}

function fieldRows(db: any, problems: string[]): any[][] {
  return byOrder(firstRows(db, [
    "select ntid, ord, name, config from fields",
    "select ntid, ord, name from fields",
    "select ntid, ord, name from fields order by ntid, ord",
  ], problems));
}''', "first rows")

a = once(a, '''    for (const row of rowsOf(db.exec("select ntid, name from fields not indexed order by ntid, ord"))) {
      const id = Number(row[0]);
      if (!fields.has(id)) fields.set(id, []);
      fields.get(id)!.push(String(row[1]));
    }''', '''    const problems: string[] = [];
    for (const row of fieldRows(db, problems)) {
      const id = Number(row[0]);
      if (!fields.has(id)) fields.set(id, []);
      fields.get(id)!.push(String(row[2]));
    }''', "fields query")
a = once(a, '''    for (const row of rowsOf(db.exec("select ntid, name, config from templates not indexed order by ntid, ord"))) {
      const id = Number(row[0]);
      const config = protoFields(row[2] as Uint8Array);
      if (!templates.has(id)) templates.set(id, []);
      templates.get(id)!.push({ name: String(row[1]), qfmt: protoText(config.get(1)), afmt: protoText(config.get(2)) });
    }''', '''    const templateRows = byOrder(firstRows(db, [
      "select ntid, ord, name, config from templates",
      "select ntid, ord, name, config from templates order by ntid, ord",
    ], problems));
    for (const row of templateRows) {
      const id = Number(row[0]);
      const config = protoFields(row[3] as Uint8Array);
      if (!templates.has(id)) templates.set(id, []);
      templates.get(id)!.push({ name: String(row[2]), qfmt: protoText(config.get(1)), afmt: protoText(config.get(2)) });
    }''', "templates query")
a = once(a, '''    for (const row of rowsOf(db.exec("select id, name, config from notetypes not indexed order by id"))) {''',
         '''    const notetypeRows = firstRows(db, [
      "select id, name, config from notetypes",
      "select id, name, config from notetypes not indexed",
    ], problems);
    for (const row of notetypeRows) {''', "notetypes query")
a = once(a, '''      for (const row of rowsOf(db.exec("select id, name from decks not indexed order by id"))) {''',
         '''      const deckRows = firstRows(db, [
        "select id, name, common from decks",
        "select id, name from decks not indexed",
        "select id, name from decks",
      ], []);
      for (const row of deckRows) {''', "decks query")
ai.write_text(a, encoding="utf-8")
print("v2.23 models applied")
