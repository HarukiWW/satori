# v1.89:
# - The live background in the Dictionary tab: the page is clear there (its cards stay dark), the hint in the middle
#   of the empty page is gone.
# - The background is livelier and covers more of the screen: six larger patches, faster, a little brighter.
import pathlib


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


app = pathlib.Path("src/safari/iOS (App)")
hv = app / "HelpView.swift"
s = hv.read_text(encoding="utf-8")
s = once(s, '''        let paths: [(sx: Double, sy: Double, phase: Double, size: Double, tilt: Double)] = [
            (0.011, 0.017, 0.0, 0.42, -0.5), (0.013, 0.009, 2.1, 0.36, -0.7),
            (0.007, 0.012, 4.2, 0.48, -0.4), (0.015, 0.011, 5.3, 0.30, -0.6),
        ]
''', '''        let paths: [(sx: Double, sy: Double, phase: Double, size: Double, tilt: Double)] = [
            (0.019, 0.029, 0.0, 0.58, -0.5), (0.023, 0.016, 2.1, 0.50, -0.7),
            (0.013, 0.021, 4.2, 0.64, -0.4), (0.026, 0.019, 5.3, 0.44, -0.6),
            (0.017, 0.025, 1.3, 0.52, -0.3), (0.021, 0.014, 3.6, 0.47, -0.8),
        ]
''', "backdrop paths")
s = once(s, '''            sum += exp(-(u * u + v * v) * 2)
        }
        let level = min(1, max(0, (sum - 0.25) / 0.75))
        return level * level * 0.26
''', '''            sum += exp(-(u * u + v * v) * 1.6)
        }
        let level = min(1, max(0, (sum - 0.12) / 0.7))
        return level * (0.55 + 0.45 * level) * 0.34
''', "backdrop field")
hv.write_text(s, encoding="utf-8")

wv = pathlib.Path("src/safari/Shared (iOS)/YomikiriWebView.swift")
t = wv.read_text(encoding="utf-8")
t = once(t, "    var edgeToEdge = false\n", "    var edgeToEdge = false\n    /// the page is drawn over what is behind the view\n    var transparent = false\n",
         "web view clear flag")
t = once(t, '''        if edgeToEdge {
            webview.scrollView.contentInsetAdjustmentBehavior = .never
        }
''', '''        if edgeToEdge {
            webview.scrollView.contentInsetAdjustmentBehavior = .never
        }
        if transparent {
            webview.isOpaque = false
            webview.backgroundColor = .clear
            webview.scrollView.backgroundColor = .clear
        }
''', "web view clear")
t = once(t, '''    func edgeToEdge(_ value: Bool) -> YomikiriWebView {
''', '''    func transparent(_ value: Bool) -> YomikiriWebView {
        var view = self
        view.transparent = value
        return view
    }

    func edgeToEdge(_ value: Bool) -> YomikiriWebView {
''', "web view clear modifier")
wv.write_text(t, encoding="utf-8")

dv = app / "DictionaryView.swift"
t = dv.read_text(encoding="utf-8")
t = once(t, '''URL_DICT_DIR.withPathComponents([URLQueryItem(name: "context", value: "app")])!''',
         '''URL_DICT_DIR.withPathComponents([URLQueryItem(name: "context", value: "app"),
                                          URLQueryItem(name: "backdrop", value: "1")])!''', "dictionary url")
t = once(t, '''            .background(DictionaryView.BACKGROUND_COLOR)
''', '''            .transparent(true)
            .background {
                if #available(iOS 16.0, *) {
                    SatoriBackdrop()
                } else {
                    DictionaryView.BACKGROUND_COLOR
                }
            }
''', "dictionary backdrop")
dv.write_text(t, encoding="utf-8")

web = pathlib.Path("src/main/src/iosapp")
p = web / "dictionary.ts"
t = p.read_text(encoding="utf-8")
t = once(t, '''  const searchText = params.get("search") ?? "";
''', '''  const searchText = params.get("search") ?? "";
  // the Dictionary tab draws the live background behind the page
  if (params.get("backdrop") === "1") document.documentElement.classList.add("backdrop");
''', "backdrop param")
p.write_text(t, encoding="utf-8")

p = web / "DictionaryPage.svelte"
t = p.read_text(encoding="utf-8")
t = once(t, '''  html,
  html body {
    height: 100%;
  }
''', '''  /* the Dictionary tab: the live background shows between the cards */
  html.backdrop:root,
  html.backdrop body,
  html.backdrop .search > .header,
  html.backdrop .search > .entries {
    background-color: transparent !important;
  }

  html,
  html body {
    height: 100%;
  }
''', "backdrop css")
p.write_text(t, encoding="utf-8")

p = web / "DictionaryView.svelte"
t = p.read_text(encoding="utf-8")
t = once(t, '''        <div class="placeholder">Введите японский текст</div>
''', "", "no hint")
t = once(t, '''  .placeholder-container {
    flex: 1 1 auto;
    background-color: #000000;
''', '''  .placeholder-container {
    flex: 1 1 auto;
    background-color: transparent;
''', "clear empty page")
p.write_text(t, encoding="utf-8")
print("v1.89 dictionary applied")
