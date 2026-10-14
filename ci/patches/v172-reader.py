# v1.72: the "Чтение" tab (between "Статистика" and "Словарь"): web novels from Syosetu downloaded by episodes and
# volumes and read offline in a native reader, with word lookup, mining and reading statistics. The code is
# v172-reader.swift. A tapped word opens the dictionary on that word: the dictionary page takes "charAt".
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


here = pathlib.Path(__file__).resolve().parent
hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")
s = s.rstrip("\n") + "\n" + (here / "v172-reader.swift").read_text(encoding="utf-8")

# ---------- the dictionary page opens on a given character ----------
s = once(s, """struct WordLookupSheet: View {
    let text: String
    /// the landscape panel at the bottom of the screen: square bottom corners and no gap under it
    var docked = false
""", """struct WordLookupSheet: View {
    let text: String
    /// the landscape panel at the bottom of the screen: square bottom corners and no gap under it
    var docked = false
    /// the word to open on (a code point index in `text`), the start when nil
    var charAt: Int? = nil
""", "lookup char")
s = once(s, """            URLQueryItem(name: "search", value: text),
        ])
""", """            URLQueryItem(name: "search", value: text),
            URLQueryItem(name: "charAt", value: String(charAt ?? 0)),
        ])
""", "lookup url")
hv.write_text(s, encoding="utf-8")

main = "src/main/src/"
patch(main + "iosapp/dictionary.ts", [
    ('  const searchText = params.get("search") ?? "";\n  return new DictionaryPage({\n    target: document.body,\n    props: { context, searchText },\n',
     '  const searchText = params.get("search") ?? "";\n'
     '  // the word the page opens on (the reader of the app passes it)\n'
     '  const initialCharAt = Math.max(0, parseInt(params.get("charAt") ?? "0", 10) || 0);\n'
     '  return new DictionaryPage({\n    target: document.body,\n    props: { context, searchText, initialCharAt },\n',
     "page params"),
])
patch(main + "iosapp/DictionaryPage.svelte", [
    ('  export let searchText = "";\n</script>', '  export let searchText = "";\n  export let initialCharAt = 0;\n</script>', "page prop"),
    ("    <DictionaryView {context} {searchText} />", "    <DictionaryView {context} {searchText} {initialCharAt} />", "page pass"),
])
patch(main + "iosapp/DictionaryView.svelte", [
    ("  export let searchText: string;\n", "  export let searchText: string;\n  export let initialCharAt = 0;\n", "view prop"),
    ('      bind:searchText\n      showCloseButton={context === "action"}\n',
     '      bind:searchText\n      {initialCharAt}\n      showCloseButton={context === "action"}\n', "view pass"),
])
patch(main + "components/dictionary/Tokenize.svelte", [
    ("  export let onClose: () => void = () => null;\n",
     "  export let onClose: () => void = () => null;\n  /** the character the first search opens on */\n  export let initialCharAt = 0;\n",
     "tokenize prop"),
    ("  let selectedCharAt = 0;\n", "  let selectedCharAt = initialCharAt;\n", "tokenize start"),
])

# ---------- the tab ----------
patch("src/safari/iOS (App)/MainView.swift", [
    ("""                .tag(Tabs.help)
            DictionaryView()
""", """                .tag(Tabs.help)
            ReaderTabView()
                .tabItem {
                    Label("Чтение", systemImage: "book.fill")
                }
                .tag(Tabs.reader)
            DictionaryView()
""", "reader tab"),
    ("        case help, dictionary, settings, video\n", "        case help, reader, dictionary, settings, video\n", "tab case"),
])
print("v1.72 reader applied")
