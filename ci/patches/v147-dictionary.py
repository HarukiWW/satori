# v1.47 (dictionary): the look of the native screens (iOS 26): black page, entries as rounded cards, a pill search
# field, round toolbar buttons. Svelte styles are scoped to their components, so these rules use !important.
import pathlib

p = pathlib.Path("src/main/src/global.css")
CSS = """

/* ---- Yomikiri: iOS 26 look, like the native statistics and video screens ---- */
body {
  --background: #000000;
  --background-alt: #000000;
  --background-alt-light: #1c1c1e;
  --input: #1c1c1e;
  --border: #2c2c2e;
  font-family: -apple-system, system-ui, "Hiragino Sans", sans-serif;
  background-color: #000000;
}
.searchbar {
  border-radius: 999px !important;
  border: none !important;
  min-height: 40px;
  padding: 2px 12px !important;
  background-color: #1c1c1e !important;
}
.searchbar input {
  font-size: 17px !important;
  background-color: transparent !important;
}
.tokensview {
  margin: 8px 12px 0 12px !important;
  border-radius: 18px;
  background-color: #1c1c1e !important;
}
.entryView {
  background-color: #1c1c1e;
  border-radius: 18px;
  margin: 10px 12px !important;
  padding: 10px 0 !important;
  border: none !important;
}
.toolbar {
  background-color: transparent !important;
}
.tool-button {
  border-radius: 999px !important;
}
"""
s = p.read_text(encoding="utf-8")
assert "Yomikiri: iOS 26 look" not in s
p.write_text(s.rstrip("\n") + "\n" + CSS, encoding="utf-8")
print("v1.47 dictionary style applied")
