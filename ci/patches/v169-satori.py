# v1.69: rebranding to Satori, step 2, and the accent color.
# - The extension icons (normal and the faded "disabled" one) and the icon of the old onboarding page are the Satori
#   icon (ci/assets, made from satori-icon.png); icon.svg shows the same picture.
# - Every visible "Yomikiri" is Satori now, except where it says that Satori is a fork of Yomikiri. The links go to
#   github.com/itsHiyori/satori. Internal names (bundle IDs, the App Group, the yomikiri:// scheme, code names) stay:
#   changing them would stop the app installing over the old one, lose its data and break the return from AnkiMobile.
# - Accent color: Settings → Внешний вид → «Акцентный цвет», blue by default. The app (tab bar, switches, buttons,
#   progress bars) and the web pages (dictionary, Safari tooltip, extension) use it.
import base64
import pathlib
import shutil


def times(text, old, new, count, label):
    assert text.count(old) == count, "pattern not found " + str(count) + " times: " + label
    return text.replace(old, new)


def patch(path, edits):
    p = pathlib.Path(path)
    s = p.read_text(encoding="utf-8")
    for edit in edits:
        old, new, label = edit[0], edit[1], edit[-1]
        count = edit[2] if len(edit) == 4 else 1
        s = times(s, old, new, count, label)
    p.write_text(s, encoding="utf-8")


assets = pathlib.Path(__file__).resolve().parent.parent / "assets"
main = "src/main/src/"
repo = "https://github.com/itsHiyori/satori"

# ---------- icons ----------
shutil.copyfile(assets / "satori-icon-128.png", main + "assets/static/images/icon128.png")
shutil.copyfile(assets / "satori-icon-128-disabled.png", main + "assets/icon128-20a.png")
shutil.copyfile(assets / "satori-icon-256.png", "src/safari/Shared (App)/Resources/Icon.png")
png = base64.b64encode((assets / "satori-icon-256.png").read_bytes()).decode()
pathlib.Path(main + "assets/static/images/icon.svg").write_text(
    '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 256 256">'
    '<image width="256" height="256" xlink:href="data:image/png;base64,' + png + '"/></svg>\n', encoding="utf-8")

# ---------- names ----------
patch(main + "components/options/ankiTemplate/AnkiTemplateEdit.svelte", [
    ('      title="Готовые типы заметок Anki для Yomikiri"\n'
     '      href="https://github.com/BlueGreenMagick/yomikiri/blob/main/Anki_Template.md"\n'
     '      >Типы заметок Yomikiri</a\n',
     '      title="Готовые типы заметок Anki для Satori"\n'
     '      href="' + repo + '/blob/main/Anki_Template.md"\n'
     '      >Типы заметок Satori</a\n', "template link"),
])
patch(main + "components/options/ankiTemplate/exampleMarkerData.ts",
      [('  pageTitle: "Yomikiri Examples",\n', '  pageTitle: "Satori Examples",\n', "example title")])
patch(main + "components/options/groups/GroupAbout.svelte", [
    ('Platform.openExternalLink("https://github.com/itsHiyori/yomikiri");',
     'Platform.openExternalLink("' + repo + '");', "about link"),
    ("    Satori — проект с открытым исходным кодом на основе Yomikiri (BlueGreenMagick). Код можно посмотреть на\n"
     "    GitHub.\n",
     "    Satori — открытый проект, форк Yomikiri (BlueGreenMagick). Код — на GitHub.\n", "about text"),
])
patch(main + "components/options/modals/ModalThirdParty.svelte",
      [("        Yomikiri использует словарные файлы JMDict/JMneDict.\n",
        "        Satori использует словарные файлы JMDict/JMneDict.\n", "third party")])
patch(main + "manifest.json.ejs", [('    "default_title": "Yomikiri"\n', '    "default_title": "Satori"\n', "toolbar title")])
patch("src/safari/Shared (App)/Base.lproj/Main.html", [
    ('alt="Yomikiri Icon"', 'alt="Satori"', "onboarding icon"),
    ("Yomikiri’s", "Satori’s", 4, "onboarding text"),
])
patch("src/safari/iOS (App)/HelpView.swift", [
    ('request.setValue("Yomikiri/1.8", forHTTPHeaderField: "User-Agent")',
     'request.setValue("Satori/1.69", forHTTPHeaderField: "User-Agent")', "jimaku user agent"),
])

# ---------- accent color: the web ----------
patch(main + "lib/config.ts", [
    ('  "general.tooltip_max_height": number;\n',
     '  "general.tooltip_max_height": number;\n  /** accent color of the app and the pages (hex), blue by default */\n'
     '  "general.accent": string;\n', "config type"),
    ('  "general.tooltip_max_height": 300,\n',
     '  "general.tooltip_max_height": 300,\n  "general.accent": "#0a84ff",\n', "config default"),
    ("""    const unsubscribeFont = this.store("general.font").subscribe((font) => {""",
     """    const unsubscribeAccent = this.store("general.accent").subscribe((accent) => {
      const el = ref.deref();
      if (el === undefined) {
        unsubscribeAccent();
        return;
      }
      // only a hex color reaches the style
      if (/^#[0-9a-fA-F]{6}$/.test(accent)) el.style.setProperty("--accent", accent);
    });
    const unsubscribeFont = this.store("general.font").subscribe((font) => {""", "accent style"),
])
patch(main + "global.css", [("  --accent: #ff992a;\n", "  --accent: #0a84ff;\n", "accent default")])

# ---------- accent color: the app ----------
hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")
s = s.rstrip("\n") + '''

/// The accent color of the app (Settings → Внешний вид). Kept in UserDefaults for the app and in the shared config
/// ("general.accent") for the web pages and the Safari extension.
enum AppAccent {
    static let key = "ykAccent"
    static let standard = "#0a84ff"
    static let options: [(hex: String, name: String)] = [
        ("#0a84ff", "Синий"), ("#c4392b", "Красный (Satori)"), ("#ff9f0a", "Оранжевый"), ("#30d158", "Зелёный"),
        ("#64d2ff", "Голубой"), ("#bf5af2", "Фиолетовый"), ("#ff375f", "Розовый"),
    ]

    static func color(_ hex: String) -> Color {
        let clean = hex.trimmingCharacters(in: CharacterSet(charactersIn: "#"))
        guard clean.count == 6, let value = UInt32(clean, radix: 16) else { return .blue }
        return Color(red: Double((value >> 16) & 0xFF) / 255, green: Double((value >> 8) & 0xFF) / 255,
                     blue: Double(value & 0xFF) / 255)
    }
}
'''
s = times(s, '''                Stepper(value: config.int("general.font_size", 11), in: 9 ... 24) {''',
          '''                Picker("Акцентный цвет", selection: $accent) {
                    ForEach(AppAccent.options, id: \\.hex) { option in
                        Text(option.name).tag(option.hex)
                    }
                }
                Stepper(value: config.int("general.font_size", 11), in: 9 ... 24) {''', 1, "accent picker")
s = times(s, '''    @AppStorage("ykVocabSure") private var vocabSure = 0
''', '''    @AppStorage("ykVocabSure") private var vocabSure = 0
    @AppStorage(AppAccent.key) private var accent = AppAccent.standard
''', 1, "accent storage")
s = times(s, '''        .onAppear {
            config.reload()
        }
    }
}

/// Reports for finding problems''', '''        .onAppear {
            config.reload()
        }
        .onChange(of: accent) { value in
            config.set("general.accent", value)
        }
    }
}

/// Reports for finding problems''', 1, "accent to config")
# the bars and sliders that were blue follow the accent
s = times(s, "                            Capsule().fill(Color.blue).frame(width: geo.size.width * watched)\n",
          "                            Capsule().fill(Color.accentColor).frame(width: geo.size.width * watched)\n", 1,
          "list progress")
s = times(s, "                                        .tint(.blue)\n", "                                        .tint(.accentColor)\n", 1,
          "youtube list progress")
s = times(s, "               })\n        .tint(.blue)\n", "               })\n", 1, "youtube slider")
hv.write_text(s, encoding="utf-8")

patch("src/safari/iOS (App)/MainView.swift", [
    ("""struct MainView: View {
    @EnvironmentObject var appState: AppState
""", """struct MainView: View {
    @EnvironmentObject var appState: AppState
    @AppStorage(AppAccent.key) private var accent = AppAccent.standard
""", "main accent storage"),
    ("""        }
        .preferredColorScheme(.dark)
    }
""", """        }
        .accentColor(AppAccent.color(accent))
        .tint(AppAccent.color(accent))
        .preferredColorScheme(.dark)
    }
""", "main tint"),
])
print("v1.69 Satori applied")
