# v1.44 (player): season and episode badge in the video list ("S02E05", or "E07" when the name has no season),
# found by the same file-name parser the Jimaku search uses. The parser now also reads dotted names whose group
# tag is in brackets ("[Group].Show.Episode.16.[BD...]"), which the subtitle search did not understand before.
import pathlib

p = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = p.read_text(encoding="utf-8")


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


# 1) one cleaning of the name for the episode, the season and the subtitle search
s = once(s, '''        var s = (file as NSString).deletingPathExtension
        s = s.replacingOccurrences(of: #"\\[[^\\]]*\\]|\\([^)]*\\)"#, with: " ", options: .regularExpression)
        s = s.replacingOccurrences(of: "_", with: " ")
        if !s.contains(" "), s.filter({ $0 == "." }).count >= 2 {
            s = s.replacingOccurrences(of: ".", with: " ")
        }
        s = s.split(separator: " ").joined(separator: " ")
        let rules = [''', '''        let s = clean(file)
        let rules = [''', "parse cleaning")

s = once(s, '''    /// "BD" or "WEB" when the file name says so, to prefer subtitles of the same release
''', '''    /// The name without extension, tags in brackets and separators. Dots count as separators when the name has
    /// no spaces or underscores of its own (decided before the bracket tags are removed).
    static func clean(_ file: String) -> String {
        var s = (file as NSString).deletingPathExtension
        let dotted = !s.contains(" ") && !s.contains("_") && s.filter({ $0 == "." }).count >= 2
        s = s.replacingOccurrences(of: #"\\[[^\\]]*\\]|\\([^)]*\\)"#, with: " ", options: .regularExpression)
        s = s.replacingOccurrences(of: "_", with: " ")
        if dotted || (!s.contains(" ") && s.filter({ $0 == "." }).count >= 2) {
            s = s.replacingOccurrences(of: ".", with: " ")
        }
        return s.split(separator: " ").joined(separator: " ")
    }

    /// The season written in the name: S02E05, 2x05, 2nd Season, Season 2, S2, or II / III / IV / V before the episode.
    static func season(_ file: String) -> Int? {
        let s = clean(file)
        let ns = s as NSString
        let rules = [
            #"\\bS(\\d{1,2})\\s*E\\d{1,3}\\b"#,
            #"\\b(\\d{1,2})x\\d{1,3}\\b"#,
            #"\\b(\\d{1,2})(?:st|nd|rd|th)\\s+Season\\b"#,
            #"\\bSeason\\s*(\\d{1,2})\\b"#,
            #"\\bS(\\d{1,2})\\b"#,
        ]
        for rule in rules {
            guard let re = try? NSRegularExpression(pattern: rule, options: [.caseInsensitive]),
                  let m = re.firstMatch(in: s, range: NSRange(location: 0, length: ns.length)),
                  m.numberOfRanges > 1, let n = Int(ns.substring(with: m.range(at: 1))), n > 0 else { continue }
            return n
        }
        let roman = ["II": 2, "III": 3, "IV": 4, "V": 5]
        if let re = try? NSRegularExpression(pattern: #"\\s(II|III|IV|V)(?=\\s*(?:-|$))"#),
           let m = re.firstMatch(in: s, range: NSRange(location: 0, length: ns.length)) {
            return roman[ns.substring(with: m.range(at: 1))]
        }
        return nil
    }

    /// "S02E05", or "E07" when the name says nothing about the season; nil when no episode is found.
    static func episodeTag(_ file: String) -> String? {
        guard let episode = parse(file).episode else { return nil }
        let e = String(format: "E%02d", episode)
        guard let season = season(file) else { return e }
        return String(format: "S%02d", season) + e
    }

    /// "BD" or "WEB" when the file name says so, to prefer subtitles of the same release
''', "season and tag")

# 2) the badge next to the file type badge
s = once(s, '''                    if !item.isFolder {
                        Text(ext.isEmpty ? "—" : ext)
                            .font(.caption2.bold())
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(Color.secondary.opacity(0.2))
                            .cornerRadius(4)
                    }
''', '''                    if !item.isFolder {
                        Text(ext.isEmpty ? "—" : ext)
                            .font(.caption2.bold())
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(Color.secondary.opacity(0.2))
                            .cornerRadius(4)
                    }
                    if !item.isFolder, VideoLibraryStore.isVideo(name), let tag = JimakuName.episodeTag(name) {
                        Text(tag)
                            .font(.caption2.bold())
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(Color.secondary.opacity(0.2))
                            .cornerRadius(4)
                    }
''', "badge")

p.write_text(s, encoding="utf-8")
print("v1.44 player patch applied")
