# v1.88: the lists of the Video and Reading tabs keep an inline title like the screens they open (the catalog, a
# novel, a folder): a large title area that grows and shrinks on the way back pushed the list under the bar for a
# moment.
import pathlib


def within(text, start, end, old, new, label):
    """Replace `old` (exactly once) between the first `start` and the next `end` after it."""
    a = text.index(start)
    b = text.index(end, a + len(start))
    part = text[a:b]
    assert part.count(old) == 1, "pattern not found once in region: " + label
    return text[:a] + part.replace(old, new) + text[b:]


hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")
s = within(s, "struct NativeVideoListView: View {", "\nstruct ", "        .navigationTitle(title)\n",
           "        .navigationTitle(title)\n        .navigationBarTitleDisplayMode(.inline)\n", "video list title")
s = within(s, "struct NovelLibraryView: View {", "\nstruct ", '        .navigationTitle("Чтение")\n',
           '        .navigationTitle("Чтение")\n        .navigationBarTitleDisplayMode(.inline)\n', "reader list title")
hv.write_text(s, encoding="utf-8")
print("v1.88 nav applied")
