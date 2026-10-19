# v2.22: the note types of the backup are read first and never lost.
# - A backup of the same day gave its note types once (13:49) and none later: the reading of the note types came last,
#   after the heavy queries of all the notes and the review log, and an error of sql.js there was swallowed into
#   «0 types», which then replaced the good ones. Now they are read first, on the fresh database, with queries that
#   use no index (the indexes of the names need the collation "unicase" sql.js does not have); a read that finds none
#   keeps the last good ones, and the message of the package says the error of the read.
import pathlib


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


ai = pathlib.Path("src/main/src/lib/ankiImport.ts")
a = ai.read_text(encoding="utf-8")
a = once(a, '''export interface AnkiModels {
  notetypes: AnkiModel[];
  decks: { id: number; name: string }[];
}''', '''export interface AnkiModels {
  notetypes: AnkiModel[];
  decks: { id: number; name: string }[];
  /** why no note types were read */
  problem?: string;
}''', "problem field")
for table in ['"select ntid, name from fields order by ntid, ord"', '"select ntid, name, config from templates order by ntid, ord"',
              '"select id, name, config from notetypes order by id"', '"select id, name from decks order by id"']:
    name = table.split(" from ")[1].split(" ")[0]
    a = once(a, "db.exec(" + table + ")", "db.exec(" + table.replace(" from " + name + " ", " from " + name + " not indexed ") + ")",
             "not indexed " + name)
a = once(a, '''  } catch (e) {
    // older collections keep them in col.models and col.decks
    models.notetypes = [];
    models.decks = [];
  }''', '''  } catch (e) {
    // older collections keep them in col.models and col.decks
    models.notetypes = [];
    models.decks = [];
    models.problem = e instanceof Error ? e.message : String(e);
  }''', "schema 18 problem")
a = once(a, '''  } catch (e) {
    // no note types: the queue sends its notes one by one
  }
  return models;''', '''  } catch (e) {
    // no note types: the queue sends its notes one by one
    if (models.notetypes.length === 0 && models.problem === undefined) {
      models.problem = e instanceof Error ? e.message : String(e);
    }
  }
  return models;''', "legacy problem")
a = once(a, '''  const db = new SQL.Database(bytes);
  try {
    const names = fieldNames(db);
    const words = new Set<string>();
    const mature = new Set<string>();''', '''  const db = new SQL.Database(bytes);
  try {
    // first, on the fresh database: after the queries of all the notes and the review log they were lost once
    const models = readAnkiModels(db);
    const names = fieldNames(db);
    const words = new Set<string>();
    const mature = new Set<string>();''', "models first")
a = once(a, '''      history: matureHistory(db, wordOfNote),
      models: readAnkiModels(db),''', '''      history: matureHistory(db, wordOfNote),
      models,''', "models result")
ai.write_text(a, encoding="utf-8")

hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")
s = once(s, '''    struct Models: Codable {
        let notetypes: [Notetype]
        let decks: [Deck]
    }''', '''    struct Models: Codable {
        let notetypes: [Notetype]
        let decks: [Deck]
        /// why the import page read no note types
        var problem: String? = nil
    }''', "models problem")
s = once(s, '''    /// The note types and decks of the newest backup, from the import page.
    static func save(_ json: String) {
        guard let data = json.data(using: .utf8), (try? JSONDecoder().decode(Models.self, from: data)) != nil else {
            return
        }
        try? data.write(to: file, options: .atomic)
    }''', '''    private static let problemKey = "ykAnkiModelsProblem"

    /// The note types and decks of the newest backup, from the import page. A read that found none keeps the last
    /// ones (once, «0 types» of a failed read replaced good ones); its error is kept for the message of the package.
    static func save(_ json: String) {
        guard let data = json.data(using: .utf8), let models = try? JSONDecoder().decode(Models.self, from: data) else {
            return
        }
        guard !models.notetypes.isEmpty else {
            UserDefaults.standard.set(models.problem ?? "типы заметок не найдены", forKey: problemKey)
            return
        }
        UserDefaults.standard.removeObject(forKey: problemKey)
        try? data.write(to: file, options: .atomic)
    }

    /// The error of the last read of the note types, for the message.
    static var problem: String {
        UserDefaults.standard.string(forKey: problemKey).map { " Ошибка чтения бэкапа: " + $0 + "." } ?? ""
    }''', "save keeps good")
s = once(s, '''            throw Failure.reason("Нет типов заметок из бэкапа AnkiMobile: пакет берёт их оттуда. Выберите папку бэкапов "
                + "в Настройках → Anki.")''', '''            throw Failure.reason("Нет типов заметок из бэкапа AnkiMobile: пакет берёт их оттуда. Выберите папку бэкапов "
                + "в Настройках → Anki." + problem)''', "no models problem")
s = once(s, '''        return text + ". Сделайте свежий бэкап в AnkiMobile: Satori прочитает его сам."''',
         '''        return text + ". Сделайте свежий бэкап в AnkiMobile: Satori прочитает его сам." + problem''', "missing problem")
hv.write_text(s, encoding="utf-8")
print("v2.22 models applied")
