# v1.71: the catalog. A "Каталог" button in the video list opens the Jiten library (anime, dramas, films; search by
# English, Japanese and romaji titles), with Jiten's difficulty, our coverage of a title or an episode (from Jiten's
# word list, counted by the same rules as the episodes) and its unknown words with lookup. The rules of a known word
# move from the episode analysis into WordKnowledge, shared by both. The code is v171-catalog.swift.
import pathlib


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


def between(text, start, end, new, label):
    assert text.count(start) == 1, "start not found exactly once: " + label
    a = text.index(start)
    b = text.index(end, a)
    return text[:a] + new + text[b:]


here = pathlib.Path(__file__).resolve().parent
hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")
s = s.rstrip("\n") + "\n" + (here / "v171-catalog.swift").read_text(encoding="utf-8")

# ---------- the episode analysis uses WordKnowledge ----------
s = between(s, "    nonisolated static func analyze(of file: URL, index: KnownWordsIndex, level: Int, vocabulary: Int) -> EpisodeAnalysis? {\n",
            "        var words = 0\n        var knownWords = 0\n",
            "    nonisolated static func analyze(of file: URL, index: KnownWordsIndex, level: Int, vocabulary: Int) -> EpisodeAnalysis? {\n"
            "        let judge = WordKnowledge(index: index, level: level, vocabulary: vocabulary)\n", "analysis rules")
s = once(s, "            for token in tokens where counted(token) {\n",
         "            for token in tokens where WordKnowledge.counted(token) {\n", "analysis counted")
s = once(s, "                if known(token) {\n                    continue\n                }\n                lineUnknown += 1\n",
         "                if judge.known(token) {\n                    continue\n                }\n                lineUnknown += 1\n",
         "analysis known")
s = once(s, "            list.append(UnknownWord(word: word, reading: reading(of: word), count: count))\n",
         "            list.append(UnknownWord(word: word, reading: judge.reading(of: word), count: count))\n", "analysis reading")

# ---------- the catalog button ----------
s = once(s, """                    Image(systemName: "tray.full")
                }
            }
            ToolbarItem(placement: .navigationBarTrailing) {
                Button {
                    showYouTube = true
""", """                    Image(systemName: "tray.full")
                }
            }
            ToolbarItem(placement: .navigationBarLeading) {
                NavigationLink(destination: CatalogView()) {
                    Image(systemName: "books.vertical")
                }
            }
            ToolbarItem(placement: .navigationBarTrailing) {
                Button {
                    showYouTube = true
""", "catalog button")
hv.write_text(s, encoding="utf-8")
print("v1.71 catalog applied")
