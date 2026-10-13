# v1.48: reading / watching switch above the common metrics; a blue progress bar in the video list instead of the
# "stopped at" text; tapping the video closes the dictionary window; lighter Anki form; smaller toolbar buttons.
import pathlib

hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


# 1) statistics: the switch goes above "Слов в Anki" / "Кандзи"
s = once(s, '''                LazyVGrid(
                    columns: [GridItem(.flexible(), spacing: 12), GridItem(.flexible(), spacing: 12)],
                    spacing: 12
                ) {
                    StatCard(title: "Слов в Anki", value: statNumber(s.minedWords))
                    StatCard(title: "Кандзи (уник.)", value: statNumber(s.kanji))
                }

                Picker("Режим", selection: $mode) {
                    Text("Чтение").tag(0)
                    Text("Просмотр").tag(1)
                }
                .pickerStyle(.segmented)
''', '''                Picker("Режим", selection: $mode) {
                    Text("Чтение").tag(0)
                    Text("Просмотр").tag(1)
                }
                .pickerStyle(.segmented)

                LazyVGrid(
                    columns: [GridItem(.flexible(), spacing: 12), GridItem(.flexible(), spacing: 12)],
                    spacing: 12
                ) {
                    StatCard(title: "Слов в Anki", value: statNumber(s.minedWords))
                    StatCard(title: "Кандзи (уник.)", value: statNumber(s.kanji))
                }
''', "switch order")

# 2) video list: the length is kept with the position, the row shows a blue bar instead of the text
s = once(s, '''        UserDefaults.standard.set(position, forKey: "resume." + name)
''', '''        UserDefaults.standard.set(position, forKey: "resume." + name)
        UserDefaults.standard.set(duration, forKey: "duration." + name)
''', "save duration")
s = once(s, '''    static func isWatched(_ name: String) -> Bool {
''', '''    /// Watched part for the bar in the list: 1 when watched, nil before the first 10 s or before the length is known.
    static func fraction(_ name: String) -> Double? {
        if isWatched(name) { return 1 }
        let duration = UserDefaults.standard.double(forKey: "duration." + name)
        let current = position(name)
        guard duration > 0, current > 10 else { return nil }
        return min(1, current / duration)
    }

    static func isWatched(_ name: String) -> Bool {
''', "fraction")
s = once(s, "if let text = library.status[name] ?? watchText(name, isFolder: item.isFolder) {",
         "if let text = library.status[name] {", "no watch text")
s = once(s, '''                if let value = library.progress[name] {
                    ProgressView(value: value)
                }
''', '''                if let value = library.progress[name] {
                    ProgressView(value: value)
                } else if !item.isFolder, let watched = VideoProgress.fraction(name) {
                    // like YouTube: how much of the video is watched
                    GeometryReader { geo in
                        ZStack(alignment: .leading) {
                            Capsule().fill(Color.secondary.opacity(0.25))
                            Capsule().fill(Color.blue).frame(width: geo.size.width * watched)
                        }
                    }
                    .frame(height: 3)
                    .padding(.top, 2)
                }
''', "progress bar")
s = once(s, 'for key in ["resume.", "watched.", "subchoice.", "subdelay."] {',
         'for key in ["resume.", "watched.", "subchoice.", "subdelay.", "duration."] {', "delete duration")

# 3) a tap on the video closes the dictionary window (the sheet lets taps through to the video)
s = once(s, '''                        .onTapGesture { toggleControls() }
                    pictureLayer(rect)
''', '''                        .onTapGesture {
                            if showLookup {
                                showLookup = false
                            } else {
                                toggleControls()
                            }
                        }
                    pictureLayer(rect)
''', "tap closes lookup")
hv.write_text(s, encoding="utf-8")

# 4) web: the Anki form in the card colour, smaller toolbar buttons (they were too large in Safari)
css = pathlib.Path("src/main/src/global.css")
c = css.read_text(encoding="utf-8")
assert "Yomikiri: iOS 26 look" in c, "the v1.47 dictionary style must come first"
c = c.rstrip("\n") + """

/* ---- v1.48: Anki form not pure black, compact toolbar ---- */
.add-to-anki {
  background-color: #1c1c1e !important;
}
.add-to-anki .title-bar {
  border-bottom-color: #2c2c2e !important;
}
.field-value {
  background-color: #2c2c2e !important;
  border: none !important;
  border-radius: 10px;
  padding: 6px 8px !important;
}
.toolbar {
  align-items: center;
}
.tool-button {
  padding: 0.2em 0.75em !important;
  margin: 0.2em 0.15em !important;
}
.tool-button .icon {
  width: 1em !important;
  height: 1em !important;
}
"""
css.write_text(c, encoding="utf-8")
print("v1.48 fixes applied")
