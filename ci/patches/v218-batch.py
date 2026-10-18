# v2.18: the mining queue goes to AnkiMobile as one package.
# - «Добавить все» and «Выбрать» send two notes or more as one Anki package (.apkg) through the share sheet:
#   AnkiMobile imports them at once, instead of a trip to its add screen and back for every note. The sounds and
#   frames go into the package as files ([sound:…], <img>), the word audio of JapanesePod101 is downloaded for it.
# - The note types and decks come from the newest backup of AnkiMobile (the import page reads them, ankiImport.ts):
#   Anki's importer puts the notes into the note type with the same id, fields and card types, into the deck with the
#   same name; the same package twice adds nothing (a note keeps the id of its entry as its guid). A backup read
#   before 2.18 is read again once. A note type the backup does not have: the notes go one by one, as before.
# - Back from AnkiMobile, Satori asks whether the notes arrived: then they leave the queue and count as mined.
import pathlib


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


here = pathlib.Path(__file__).resolve().parent
hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")

s = once(s, "import CryptoKit\n", "import CryptoKit\nimport SQLite3\n", "import sqlite")

# --- the queue: the package
s = once(s, '''    private var awaiting: UUID?
    private var repairing = false
''', '''    private var awaiting: UUID?
    private var repairing = false
    /// the notes of the package handed to AnkiMobile, until the user says whether they arrived
    @Published var packed: [UUID] = []
    /// the package is being made
    @Published var packing = false
    /// why the package was not made
    @Published var packFailure = ""
''', "package state")
s = once(s, '''        sending = entries.filter { (video == nil || $0.video == video) && MiningReady.needs($0, contents).isEmpty }
        sendNext()
    }''', '''        sending = entries.filter { (video == nil || $0.video == video) && MiningReady.needs($0, contents).isEmpty }
        sendTogether()
    }''', "send all together")
s = once(s, '''        sending = entries.filter { ids.contains($0.id) && MiningReady.needs($0, contents).isEmpty }
        sendNext()
    }''', '''        sending = entries.filter { ids.contains($0.id) && MiningReady.needs($0, contents).isEmpty }
        sendTogether()
    }''', "send chosen together")

# --- the queue screen
s = once(s, '''    private var sendTitle: String {
        if !queue.sending.isEmpty {''', '''    private var sendTitle: String {
        if queue.packing {
            return "Собираю пакет…"
        }
        if !queue.sending.isEmpty {''', "packing title")
s = once(s, '''                        .disabled(chosen.isEmpty || !queue.sending.isEmpty)''',
         '''                        .disabled(chosen.isEmpty || !queue.sending.isEmpty || queue.packing)''', "chosen busy")
s = once(s, '''                        .disabled(!queue.sending.isEmpty || readyCount == 0)
                    }
                }
            }
        }
    }
}
''', '''                        .disabled(!queue.sending.isEmpty || queue.packing || !queue.packed.isEmpty || readyCount == 0)
                    }
                }
            }
            .alert("Заметки добавились в Anki?", isPresented: Binding(get: { !queue.packed.isEmpty }, set: { _ in })) {
                Button("Да, убрать из очереди") {
                    queue.packedArrived(true)
                }
                Button("Нет, оставить", role: .cancel) {
                    queue.packedArrived(false)
                }
            } message: {
                Text("Заметок в пакете: " + String(queue.packed.count))
            }
        }
        .alert("Пакет не собран", isPresented: Binding(get: { !queue.packFailure.isEmpty },
                                                        set: { shown in
                                                            if !shown {
                                                                queue.packFailure = ""
                                                            }
                                                        })) {
            Button("OK", role: .cancel) {}
        } message: {
            Text(queue.packFailure)
        }
    }
}
''', "queue alerts")

# --- the note types of the backup, from the import page
s = once(s, '''        case "pendingDeckDone":
            try? FileManager.default.removeItem(at: folder)''', '''        case "ankiModels":
            if let text = request as? String {
                MiningBatch.save(text)
            }
            return .some("true")
        case "pendingDeckDone":
            try? FileManager.default.removeItem(at: folder)''', "models message")
s = once(s, '''        if !force, let lastRead, made <= lastRead.addingTimeInterval(1) {
            return
        }''', '''        // a backup read before 2.18 is read again once: the package of the queue needs its note types
        if !force, let lastRead, made <= lastRead.addingTimeInterval(1), MiningBatch.known {
            return
        }''', "reread backup")

s = s.rstrip("\n") + "\n" + (here / "v218-batch.swift").read_text(encoding="utf-8")
hv.write_text(s, encoding="utf-8")

# --- the web: the note types and decks of a backup
ai = pathlib.Path("src/main/src/lib/ankiImport.ts")
a = ai.read_text(encoding="utf-8")
a = once(a, '''/** Words of all notes of an Anki collection package (.colpkg or .apkg). */''', '''/** A note type of the collection: the mining queue of the app sends its notes into it as one package. */
export interface AnkiModel {
  id: number;
  name: string;
  /** 0 normal, 1 cloze */
  kind: number;
  sortf: number;
  css: string;
  fields: string[];
  templates: { name: string; qfmt: string; afmt: string }[];
}

export interface AnkiModels {
  notetypes: AnkiModel[];
  decks: { id: number; name: string }[];
}

/** The fields of a protobuf message: the number of a field, its last value (a varint, or the bytes of a
 * length-delimited one). */
function protoFields(bytes: Uint8Array): Map<number, number | Uint8Array> {
  const out = new Map<number, number | Uint8Array>();
  let i = 0;
  const varint = (): number => {
    let value = 0;
    let scale = 1;
    while (i < bytes.length) {
      const b = bytes[i++];
      value += (b & 0x7f) * scale;
      scale *= 128;
      if (b < 0x80) break;
    }
    return value;
  };
  while (i < bytes.length) {
    const key = varint();
    const wire = key % 8;
    const field = Math.floor(key / 8);
    if (wire === 0) {
      out.set(field, varint());
    } else if (wire === 2) {
      const length = varint();
      out.set(field, bytes.subarray(i, i + length));
      i += length;
    } else if (wire === 1) {
      i += 8;
    } else if (wire === 5) {
      i += 4;
    } else {
      break;
    }
  }
  return out;
}

function protoText(value: number | Uint8Array | undefined): string {
  return value instanceof Uint8Array ? new TextDecoder().decode(value) : "";
}

function rowsOf(result: any[]): any[][] {
  return result[0] ? result[0].values : [];
}

/** A huge CSS (fonts inside) is left out: it only matters when Anki makes a copy of the note type. */
function smallCss(css: string): string {
  return css.length > 200000 ? "" : css;
}

/** The note types (their fields, card types and CSS) and the decks of a collection. The tables of Anki 2.1.28+ keep
 * the card types and CSS in protobuf (Notetype.Config: kind 1, sort field 2, css 3; Template.Config: front 1, back
 * 2), older ones in col.models and col.decks. */
function readAnkiModels(db: any): AnkiModels {
  const models: AnkiModels = { notetypes: [], decks: [] };
  try {
    const fields = new Map<number, string[]>();
    for (const row of rowsOf(db.exec("select ntid, name from fields order by ntid, ord"))) {
      const id = Number(row[0]);
      if (!fields.has(id)) fields.set(id, []);
      fields.get(id)!.push(String(row[1]));
    }
    const templates = new Map<number, { name: string; qfmt: string; afmt: string }[]>();
    for (const row of rowsOf(db.exec("select ntid, name, config from templates order by ntid, ord"))) {
      const id = Number(row[0]);
      const config = protoFields(row[2] as Uint8Array);
      if (!templates.has(id)) templates.set(id, []);
      templates.get(id)!.push({ name: String(row[1]), qfmt: protoText(config.get(1)), afmt: protoText(config.get(2)) });
    }
    for (const row of rowsOf(db.exec("select id, name, config from notetypes"))) {
      const id = Number(row[0]);
      const config = protoFields(row[2] as Uint8Array);
      models.notetypes.push({
        id,
        name: String(row[1]),
        kind: Number(config.get(1) ?? 0),
        sortf: Number(config.get(2) ?? 0),
        css: smallCss(protoText(config.get(3))),
        fields: fields.get(id) ?? [],
        templates: templates.get(id) ?? [],
      });
    }
    for (const row of rowsOf(db.exec("select id, name from decks"))) {
      models.decks.push({ id: Number(row[0]), name: String(row[1]).replace(/\\x1f/g, "::") });
    }
    if (models.notetypes.length > 0) return models;
  } catch (e) {
    // older collections keep them in col.models and col.decks
  }
  try {
    const row = db.exec("select models, decks from col")[0].values[0];
    const types = JSON.parse(String(row[0] || "{}"));
    for (const key of Object.keys(types)) {
      const m = types[key];
      models.notetypes.push({
        id: Number(m.id),
        name: String(m.name),
        kind: Number(m.type ?? 0),
        sortf: Number(m.sortf ?? 0),
        css: smallCss(String(m.css ?? "")),
        fields: (m.flds ?? []).map((f: any) => String(f.name)),
        templates: (m.tmpls ?? []).map((t: any) => ({ name: String(t.name), qfmt: String(t.qfmt ?? ""), afmt: String(t.afmt ?? "") })),
      });
    }
    const decks = JSON.parse(String(row[1] || "{}"));
    for (const key of Object.keys(decks)) models.decks.push({ id: Number(decks[key].id), name: String(decks[key].name) });
  } catch (e) {
    // no note types: the queue sends its notes one by one
  }
  return models;
}

/** Words of all notes of an Anki collection package (.colpkg or .apkg). */''', "models reader")
a = once(a, '''): Promise<{ words: string[]; mature: string[]; history: [string, number][] }> {''',
         '''): Promise<{ words: string[]; mature: string[]; history: [string, number][]; models: AnkiModels }> {''',
         "deck type")
a = once(a, '''    return { words: Array.from(words), mature: Array.from(mature), history: matureHistory(db, wordOfNote) };''',
         '''    return {
      words: Array.from(words),
      mature: Array.from(mature),
      history: matureHistory(db, wordOfNote),
      models: readAnkiModels(db),
    };''', "deck models")
ai.write_text(a, encoding="utf-8")

gi = pathlib.Path("src/main/src/components/options/groups/GroupAnkiImport.svelte")
g = gi.read_text(encoding="utf-8")
g = once(g, '''    let deck: { words: string[]; mature: string[] };''',
         '''    let deck: { words: string[]; mature: string[]; models?: unknown };''', "deck annotation")
g = once(g, '''    const result = await importDeck(deck, full);
''', '''    const result = await importDeck(deck, full);
    // the backup of AnkiMobile: its note types let the mining queue send its notes as one package
    if (full && deck.models) {
      await app.messageWebview("ankiModels", deck.models).catch(() => undefined);
    }
''', "send models")
gi.write_text(g, encoding="utf-8")
print("v2.18 batch applied")
