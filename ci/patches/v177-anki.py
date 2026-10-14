# v1.77: Anki.
# - The example sentences of the dictionary go into the note: under every meaning of the "meaning" field (the word
#   in bold), or into a field of their own (the new field type "example") when the template has one.
# - "Открыть в Satori": a .colpkg or .apkg shared from AnkiMobile (or opened from Files) opens the import page and
#   is imported at once. The page reads the file from the app in parts of 2 MB.
import pathlib
import plistlib


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


web = pathlib.Path("src/main/src")

# ---------- the field type "example" ----------
p = web / "lib/anki/template.ts"
t = p.read_text(encoding="utf-8")
t = once(t, '  audio: FieldBase<"audio">;\n}', '  audio: FieldBase<"audio">;\n  example: FieldBase<"example">;\n}', "types")
t = once(t, '  "audio",\n];', '  "audio",\n  "example",\n];', "type list")
t = once(t, '  audio: "audio",\n};', '  audio: "audio",\n  example: "example",\n};', "labels")
t = once(t, '    content === "link" ||\n    content === "audio"\n  ) {', '    content === "link" ||\n    content === "audio" ||\n    content === "example"\n  ) {', "new field")
p.write_text(t, encoding="utf-8")

# ---------- examples in the note ----------
p = web / "lib/anki/ankiBuilder.ts"
t = p.read_text(encoding="utf-8")
t = once(t, 'addBuilder("meaning", (opts, data) => {\n', 'addBuilder("meaning", (opts, data, ctx) => {\n'
         '  // the examples go under the meanings, unless the template has a field of their own\n'
         '  const withExamples = !hasExampleField(ctx);\n', "meaning ctx")
t = once(t, '          const itemsLine = escapeHTML(items.join(", "));\n',
         '          const itemsLine =\n            escapeHTML(items.join(", ")) +\n'
         '            (withExamples && format !== "line" ? examplesHtml(sense) : "");\n', "full meaning examples")
t = once(t, '    line += escapeHTML(items.join(", "));\n',
         '    line += escapeHTML(items.join(", ")) + (withExamples ? examplesHtml(sense) : "");\n', "single meaning examples")
t = t.rstrip("\n") + r'''

/** The template has a field for the example sentences. */
function hasExampleField(ctx: AnkiBuilderContext): boolean {
  const template = ctx.config.get("anki.anki_template");
  return template !== null && template.fields.some((field) => field.content === "example");
}

/** The example sentences of a sense with their translations; the word (marked \ue000 … \ue001) in bold. */
function examplesHtml(sense: unknown, lead = "<br>"): string {
  const examples =
    (sense as { examples?: { japanese: string; translation: string }[] }).examples ?? [];
  return examples
    .map((example) => {
      const japanese = escapeHTML(example.japanese)
        .replace(/\ue000/g, "<b>")
        .replace(/\ue001/g, "</b>");
      return (
        lead +
        '<span class="yomi-example" style="font-size: 0.85em; opacity: 0.8;">' +
        japanese +
        " — " +
        escapeHTML(example.translation) +
        "</span>"
      );
    })
    .join(lead === "" ? "<br>" : "");
}

/** The examples of the chosen meaning, or of the first meaning that has some. */
addBuilder("example", (_opts, data) => {
  const senses =
    data.selected !== undefined
      ? [data.selected.sense]
      : data.entry.groupedSenses.flatMap((group) => group.senses);
  for (const sense of senses) {
    const html = examplesHtml(sense, "");
    if (html !== "") return html;
  }
  return "";
});
'''
p.write_text(t, encoding="utf-8")

# ---------- the import page: a deck opened in Satori ----------
p = web / "components/options/groups/GroupAnkiImport.svelte"
p.write_text('''<script lang="ts">
  import { onMount } from "svelte";
  import { Platform } from "@platform";
  import { readAnkiDeck, importDeck } from "lib/ankiImport";

  let status = "";
  let busy = false;
  // the bridge to the app: a deck opened in Satori comes in parts
  const app = Platform as unknown as {
    messageWebview(key: string, request: unknown): Promise<any>;
  };

  async function importBuffer(buf: ArrayBuffer) {
    status = "Чтение колоды...";
    const deck = await readAnkiDeck(buf);
    const result = await importDeck(deck);
    status =
      `Слов в колоде: ${deck.words.length}, новых: ${result.added}, зрелых (интервал от 21 дня): ${deck.mature.length}. ` +
      "Все слова колоды больше не подсвечиваются; в покрытии и сложности учитываются только зрелые.";
    if (deck.words.length > 0 && deck.mature.length === 0) {
      status +=
        " Зрелых карточек нет: похоже, колода экспортирована без расписания. Экспортируйте .colpkg " +
        "или .apkg с включённым Include scheduling information.";
    }
  }

  async function onFile(e: Event) {
    const input = e.target as HTMLInputElement;
    const file = input.files ? input.files[0] : undefined;
    input.value = "";
    if (!file) return;
    busy = true;
    try {
      await importBuffer(await file.arrayBuffer());
    } catch (err) {
      status = "Не удалось прочитать колоду: " + (err instanceof Error ? err.message : String(err));
    } finally {
      busy = false;
    }
  }

  /** A deck opened in Satori from another app is imported at once. */
  async function importPending() {
    let pending: { name: string; size: number } | null = null;
    try {
      pending = await app.messageWebview("pendingDeck", null);
    } catch (err) {
      return;
    }
    if (!pending || !pending.size) return;
    busy = true;
    try {
      const bytes = new Uint8Array(pending.size);
      const step = 2 * 1024 * 1024;
      for (let offset = 0; offset < pending.size; offset += step) {
        status = `Получаю ${pending.name}: ${Math.floor((offset / pending.size) * 100)}%`;
        const chunk: string = await app.messageWebview("pendingDeckChunk", { offset, length: step });
        const raw = atob(chunk);
        for (let i = 0; i < raw.length; i++) bytes[offset + i] = raw.charCodeAt(i);
      }
      await importBuffer(bytes.buffer);
    } catch (err) {
      status = "Не удалось прочитать колоду: " + (err instanceof Error ? err.message : String(err));
    } finally {
      busy = false;
      await app.messageWebview("pendingDeckDone", null).catch(() => undefined);
    }
  }

  onMount(() => {
    void importPending();
  });
</script>

<div class="import">
  <div class="title">Импорт колоды Anki</div>
  <div class="note">
    Экспортируйте колоду из AnkiMobile (.colpkg или .apkg с расписанием) и в меню «Поделиться» выберите Satori —
    импорт начнётся сам. Или выберите файл здесь. Все слова колоды перестанут подсвечиваться, а в покрытии и сложности
    будут учитываться слова зрелых карточек (интервал от 21 дня). Импорт можно повторять: новые зрелые карточки
    добавятся.
  </div>
  <label class="pick">
    <input type="file" on:change={onFile} disabled={busy} />
    Выбрать файл .colpkg или .apkg
  </label>
  {#if status}<div class="status">{status}</div>{/if}
</div>

<style>
  .import {
    margin: 12px 16px;
    font-size: 0.95rem;
  }
  .title {
    font-weight: 600;
    margin-bottom: 6px;
  }
  .note {
    margin-bottom: 8px;
    font-size: 0.85rem;
    color: var(--text-faint);
  }
  .status {
    margin-top: 6px;
    font-size: 0.85rem;
    color: var(--text-faint);
  }
</style>
''', encoding="utf-8")

# ---------- the app: decks open in Satori ----------
app = pathlib.Path("src/safari/iOS (App)")
plist = app / "Info.plist"
info = plistlib.loads(plist.read_bytes())
info["CFBundleDocumentTypes"] = [{
    "CFBundleTypeName": "Anki Deck",
    "CFBundleTypeRole": "Viewer",
    "LSHandlerRank": "Alternate",
    "LSItemContentTypes": ["net.ankiweb.apkg", "net.ankiweb.colpkg"],
}]
info["UTImportedTypeDeclarations"] = [
    {
        "UTTypeIdentifier": "net.ankiweb." + ext,
        "UTTypeDescription": "Anki " + ext,
        "UTTypeConformsTo": ["public.data", "public.archive"],
        "UTTypeTagSpecification": {"public.filename-extension": [ext]},
    }
    for ext in ("apkg", "colpkg")
]
plist.write_bytes(plistlib.dumps(info))

p = app / "YomikiriApp.swift"
t = p.read_text(encoding="utf-8")
t = once(t, '''    func handleOpenUrl(url: URL) {
''', '''    func handleOpenUrl(url: URL) {
        // a deck opened in Satori ("Поделиться → Satori" in AnkiMobile, or Files)
        if DeckInbox.accepts(url) {
            if DeckInbox.receive(url) {
                appState.deckImport = true
            }
            return
        }
''', "open url")
t = once(t, '''    @Published var settingsNavigation: OptionsView.Navigation = .init()
''', '''    @Published var settingsNavigation: OptionsView.Navigation = .init()
    /// a deck opened in Satori waits for the import page
    @Published var deckImport = false
''', "app state")
p.write_text(t, encoding="utf-8")

p = app / "MainView.swift"
t = p.read_text(encoding="utf-8")
t = once(t, '''        .preferredColorScheme(.dark)
''', '''        .sheet(isPresented: $appState.deckImport) {
            NavigationView {
                AnkiImportPage()
                    .toolbar {
                        ToolbarItem(placement: .confirmationAction) {
                            Button("Готово") {
                                appState.deckImport = false
                            }
                        }
                    }
            }
        }
        .preferredColorScheme(.dark)
''', "import sheet")
p.write_text(t, encoding="utf-8")

hv = app / "HelpView.swift"
s = hv.read_text(encoding="utf-8")
s = once(s, '''                NavigationLink(destination: webPage("ankiImport", "Импорт колоды Anki")) {
''', '''                NavigationLink(destination: AnkiImportPage()) {
''', "settings import page")
s = s.rstrip("\n") + "\n" + r'''
// MARK: - Anki decks opened in Satori (v1.77)

/// A deck given to Satori by another app (AnkiMobile's "Поделиться", Files): kept in Caches until the import page
/// reads it.
enum DeckInbox {
    private static var folder: URL {
        FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask)[0].appendingPathComponent("deck-import")
    }

    static var pending: URL? {
        (try? FileManager.default.contentsOfDirectory(at: folder, includingPropertiesForKeys: nil))?.first
    }

    static func accepts(_ url: URL) -> Bool {
        url.isFileURL && ["apkg", "colpkg"].contains(url.pathExtension.lowercased())
    }

    /// Keeps a copy of the deck; the copy iOS put into Documents/Inbox is removed.
    @discardableResult
    static func receive(_ url: URL) -> Bool {
        let scoped = url.startAccessingSecurityScopedResource()
        defer {
            if scoped {
                url.stopAccessingSecurityScopedResource()
            }
        }
        let manager = FileManager.default
        try? manager.removeItem(at: folder)
        try? manager.createDirectory(at: folder, withIntermediateDirectories: true)
        do {
            try manager.copyItem(at: url, to: folder.appendingPathComponent(url.lastPathComponent))
        } catch {
            return false
        }
        if url.path.contains("/Documents/Inbox/") {
            try? manager.removeItem(at: url)
        }
        return true
    }

    /// The import page asks for the deck: "pendingDeck" (its name and size, or null), "pendingDeckChunk" (a part in
    /// base64), "pendingDeckDone" (the copy is removed).
    static func handle(_ key: String, _ request: Any) async throws -> String?? {
        switch key {
        case "pendingDeck":
            guard let file = pending,
                  let size = (try? FileManager.default.attributesOfItem(atPath: file.path)[.size]) as? Int else {
                return .some("null")
            }
            let info: [String: Any] = ["name": file.lastPathComponent, "size": size]
            let data = try JSONSerialization.data(withJSONObject: info)
            return .some(String(data: data, encoding: .utf8))
        case "pendingDeckChunk":
            guard let file = pending, let text = request as? String, let body = text.data(using: .utf8),
                  let part = (try? JSONSerialization.jsonObject(with: body)) as? [String: Any],
                  let offset = (part["offset"] as? NSNumber)?.intValue,
                  let length = (part["length"] as? NSNumber)?.intValue else {
                return .some("\"\"")
            }
            let handle = try FileHandle(forReadingFrom: file)
            defer {
                try? handle.close()
            }
            try handle.seek(toOffset: UInt64(offset))
            let chunk = handle.readData(ofLength: length)
            return .some("\"" + chunk.base64EncodedString() + "\"")
        case "pendingDeckDone":
            try? FileManager.default.removeItem(at: folder)
            return .some("true")
        default:
            return nil
        }
    }
}

/// The deck import page (web); a deck opened in Satori is imported there at once.
struct AnkiImportPage: View {
    var body: some View {
        YomikiriWebView(url: OptionsView.URL_OPTIONS.withPathComponents([URLQueryItem(name: "only", value: "ankiImport")])
                        ?? OptionsView.URL_OPTIONS)
            .handleExtraMessage(DeckInbox.handle)
            .ignoresSafeArea(.keyboard)
            .navigationTitle("Импорт колоды Anki")
            .navigationBarTitleDisplayMode(.inline)
    }
}
'''
hv.write_text(s, encoding="utf-8")
print("v1.77 anki applied")
