# v1.60: a word kept in the mining queue is counted in the statistics only when its note reaches Anki. Before, the web
# counted it before the player took the note into the queue, so a note removed from the queue stayed in the
# statistics. Now "openLink" tells the web whether the link was opened (true) or kept in the queue (false); the queue
# counts its word when AnkiMobile comes back from the note.
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


# ---------- the web view: opened or kept in the queue ----------
patch("src/safari/Shared (iOS)/YomikiriWebView.swift", [("""                DispatchQueue.main.async {
                    // does nothing in ios action
                    // the video player can change an Anki note (its frame) or keep it in the mining queue (nil)
                    if let hook = yomikiriOpenLinkHook {
                        if let changed = hook(url) {
                            openUrl(changed)
                        }
                    } else {
                        openUrl(url)
                    }
                }
                return nil
""", """                // does nothing in ios action
                // the video player can change an Anki note (its frame) or keep it in the mining queue (false)
                let opened: Bool = await MainActor.run {
                    if let hook = yomikiriOpenLinkHook {
                        guard let changed = hook(url) else { return false }
                        openUrl(changed)
                    } else {
                        openUrl(url)
                    }
                    return true
                }
                return try jsonSerialize(obj: opened)
""", "openLink result")])

# ---------- the web: count the word only when the note went to Anki ----------
patch("src/main/src/platform/iosapp/index.ts", [("  openLink: [string, null];\n",
                                                 "  openLink: [string, boolean | null];\n", "openLink type")])
patch("src/main/src/platform/iosapp/anki.ts", [("""  export async function addNote(note: AnkiNote): Promise<boolean> {
    try {
      await recordMinedNoteApp(note);
    } catch (e) {
      console.error(e);
    }
    const url = iosAnkiMobileURL(note, "yomikiri://ankiReturn");
    await Platform.messageWebview("openLink", url);
    return true;
  }
""", """  export async function addNote(note: AnkiNote): Promise<boolean> {
    const url = iosAnkiMobileURL(note, "yomikiri://ankiReturn");
    // false: the video player kept the note in its mining queue; the word is counted when the note reaches Anki
    const opened = await Platform.messageWebview("openLink", url);
    if (opened !== false) {
      try {
        await recordMinedNoteApp(note);
      } catch (e) {
        console.error(e);
      }
    }
    return true;
  }
""", "addNote")])

# ---------- the queue counts its word when the note reached Anki ----------
patch("src/safari/iOS (App)/HelpView.swift", [("""    private func sentOne() {
        guard let done = sending.first else { return }
        sending.removeFirst()
""", """    private func sentOne() {
        guard let done = sending.first else { return }
        MiningQueue.recordMined(MiningQueue.statsWord(of: done.url))
        sending.removeFirst()
""", "count when sent"), ("""    private func save() {
        if let data = try? JSONEncoder().encode(entries) {
            UserDefaults.standard.set(data, forKey: key)
        }
    }
}
""", """    private func save() {
        if let data = try? JSONEncoder().encode(entries) {
            UserDefaults.standard.set(data, forKey: key)
        }
    }

    /// The word of a note as the web counts it (wordFromNoteLite): the Furigana field, else Word, else the first
    /// field, without HTML, furigana brackets and spaces.
    static func statsWord(of link: String) -> String {
        let fields = (URLComponents(string: link)?.queryItems ?? []).filter { $0.name.hasPrefix("fld") }
        let field = fields.first { $0.name == "fldFurigana" } ?? fields.first { $0.name == "fldWord" } ?? fields.first
        var word = field?.value ?? ""
        word = word.replacingOccurrences(of: "<[^>]*>", with: "", options: .regularExpression)
        word = word.replacingOccurrences(of: "\\\\[[^\\\\]]*\\\\]", with: "", options: .regularExpression)
        return word.components(separatedBy: .whitespacesAndNewlines).joined()
    }

    /// Today's mined words and kanji in the shared statistics (stats.v1), as the web adds them (addMinedLite).
    static func recordMined(_ word: String) {
        guard !word.isEmpty else { return }
        var root: [String: Any] = [:]
        if let json = try? Storage.stats.get(), let data = json.data(using: .utf8),
           let saved = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] {
            root = saved
        }
        var days = (root["days"] as? [String: Any]) ?? [:]
        let key = statKey(daysAgo: 0)
        let empty: [String: Any] = ["mined": [String](), "kanji": [String](), "read": 0, "time": 0]
        var day = (days[key] as? [String: Any]) ?? empty
        var mined = (day["mined"] as? [String]) ?? []
        guard !mined.contains(word) else { return }
        mined.append(word)
        var kanji = (day["kanji"] as? [String]) ?? []
        for scalar in word.unicodeScalars where statIsKanji(scalar) {
            let letter = String(scalar)
            if !kanji.contains(letter) {
                kanji.append(letter)
            }
        }
        day["mined"] = mined
        day["kanji"] = kanji
        days[key] = day
        root["days"] = days
        guard let out = try? JSONSerialization.data(withJSONObject: root),
              let text = String(data: out, encoding: .utf8) else { return }
        _ = try? Storage.stats.set(text)
    }
}
""", "stats word and record")])
print("v1.60 mining statistics applied")
