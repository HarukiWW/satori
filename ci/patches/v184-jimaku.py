# v1.84: Jimaku finds subtitles for names with "Chapter NN" ("Monster - Chapter 10 - An Erased Past DVDRip … [SEV]"):
# the chapter is the episode, checked before " - NN" so a number in the episode title ("- 511 Kinderheim") loses.
import pathlib


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")

s = once(s, r'''            #"\b\d{1,2}x(\d{1,3})\b"#,
            #"(?:^|\s)-\s*(\d{1,3})(?:v\d+)?(?=\s|$|-)"#,
''', r'''            #"\b\d{1,2}x(\d{1,3})\b"#,
            #"\bChapter\s*(\d{1,3})\b"#,
            #"(?:^|\s)-\s*(\d{1,3})(?:v\d+)?(?=\s|$|-)"#,
''', "chapter rule")

hv.write_text(s, encoding="utf-8")
