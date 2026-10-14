# v1.73: the catalog. The search field is always shown; covers are small cached copies (they loaded slowly); our
# coverage is counted in the background for the titles on screen, without opening them; sorting (popularity, my
# coverage, Jiten difficulty, release date, length, title) and filters (difficulty, year, genres, no sequels); the
# next 50 titles load at the end of the list. The code is v173-catalog.swift (it replaces CatalogCover and
# CatalogView of 1.71).
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
s = between(s, "/// The cover of a title.\n@available(iOS 16.0, *)\nstruct CatalogCover: View {",
            "/// A title or an episode: Jiten's numbers, our coverage and the unknown words; the episodes of a series.",
            (here / "v173-catalog.swift").read_text(encoding="utf-8"), "catalog views")
s = once(s, """            CatalogStore.save(result, for: deck.deckId)
            coverage = result
""", """            CatalogStore.save(result, for: deck.deckId)
            CatalogCoverageQueue.shared.store(deck.deckId, result)
            coverage = result
""", "detail result to the list")
hv.write_text(s, encoding="utf-8")
print("v1.73 catalog applied")
