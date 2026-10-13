# v1.49: coverage counts a known word in any form (inflected, written in kana, another spelling with the same
# reading and a common kanji, the stem of a する verb); deleting a video deletes its subtitles and any subtitle file
# left without a video.
import pathlib

hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


# ---------- coverage: any form of a known word ----------
a = s.index("    nonisolated static func coverage(of file: URL, known: Set<String>) -> Int? {")
b = s.index("    /// Coverage of every video with Jimaku subtitles", a)
s = s[:a] + '''    nonisolated static func coverage(of file: URL, index: KnownWordsIndex) -> Int? {
        var total = 0
        var familiar = 0
        var readings: [String: String] = [:]
        for cue in EmbeddedSubtitles.cues(fromFile: file) {
            for token in NativeLookup.tokenize(cue.text, charAt: 0).tokens {
                guard token.text.unicodeScalars.contains(where: { CharacterSet.letters.contains($0) }) else { continue }
                // particles, auxiliaries and symbols do not count
                if token.pos.hasPrefix("助詞") || token.pos.hasPrefix("助動詞") || token.pos.contains("記号") { continue }
                total += 1
                let base = token.base.isEmpty ? token.text : token.base
                if index.forms.contains(base) || index.forms.contains(token.text) {
                    familiar += 1
                    continue
                }
                let reading: String
                if let saved = readings[base] {
                    reading = saved
                } else {
                    reading = KnownWordsIndex.isKana(base) ? HighlightData.hiragana(base)
                        : HighlightData.hiragana(NativeLookup.tokenize(base, charAt: 0).tokens.map { $0.reading }.joined())
                    readings[base] = reading
                }
                if !reading.isEmpty {
                    // known in kana; or written in kana here; or another spelling with a common kanji
                    if index.kanaReadings.contains(reading) {
                        familiar += 1
                        continue
                    }
                    if let kanji = index.kanjiByReading[reading],
                       KnownWordsIndex.isKana(token.text) || !kanji.isDisjoint(with: KnownWordsIndex.kanji(base)) {
                        familiar += 1
                        continue
                    }
                }
                let jlptReading = reading.isEmpty ? HighlightData.hiragana(token.reading) : reading
                if HighlightData.jlptLevel(base: base, reading: jlptReading) == 5 {
                    familiar += 1
                }
            }
        }
        return total > 0 ? Int((Double(familiar) * 100 / Double(total)).rounded()) : nil
    }

''' + s[b:]

s = once(s, '''        Task { @MainActor in
            for (name, file, stamp) in pending {
                let value = await Task.detached(priority: .utility) {
                    VideoLibraryStore.coverage(of: file, known: known)
                }.value
''', '''        Task { @MainActor in
            let index = await Task.detached(priority: .utility) { KnownWordsIndex(known) }.value
            for (name, file, stamp) in pending {
                let value = await Task.detached(priority: .utility) {
                    VideoLibraryStore.coverage(of: file, index: index)
                }.value
''', "coverage task")
# saved values of the old way of counting are not reused
s = once(s, 'let stamp = String(known.count) + "|" + String(size)',
         'let stamp = "2|" + String(known.count) + "|" + String(size)', "coverage stamp")

s = s.rstrip("\n") + '''

/// Known words for the coverage badge, matched in any form: the dictionary form of an inflected word, the word written
/// in kana, another spelling with the same reading and a common kanji, the stem of a する verb.
struct KnownWordsIndex {
    var forms = Set<String>()
    var kanaReadings = Set<String>()
    var kanjiByReading: [String: Set<Character>] = [:]

    init(_ words: Set<String>) {
        for raw in words {
            let word = KnownWordsIndex.clean(raw)
            guard !word.isEmpty else { continue }
            forms.insert(word)
            if word.hasSuffix("する"), word.count > 2 {
                forms.insert(String(word.dropLast(2)))
            }
            let tokens = NativeLookup.tokenize(word, charAt: 0).tokens
            if tokens.count == 1, !tokens[0].base.isEmpty {
                forms.insert(tokens[0].base)
            }
            if KnownWordsIndex.isKana(word) {
                kanaReadings.insert(HighlightData.hiragana(word))
            } else {
                let reading = HighlightData.hiragana(tokens.map { $0.reading }.joined())
                if !reading.isEmpty {
                    kanjiByReading[reading, default: []].formUnion(KnownWordsIndex.kanji(word))
                }
            }
        }
    }

    /// Words from Anki can carry HTML and furigana in brackets: 食[た]べる.
    static func clean(_ text: String) -> String {
        var s = text.replacingOccurrences(of: "<[^>]+>", with: "", options: .regularExpression)
        s = s.replacingOccurrences(of: "\\\\[[^\\\\]]*\\\\]", with: "", options: .regularExpression)
        s = s.replacingOccurrences(of: "&nbsp;", with: "")
        return s.components(separatedBy: .whitespacesAndNewlines).joined()
    }

    static func isKana(_ text: String) -> Bool {
        !text.isEmpty && text.unicodeScalars.allSatisfy { (0x3040 ... 0x30FF).contains($0.value) }
    }

    static func kanji(_ text: String) -> Set<Character> {
        Set(text.filter { character in character.unicodeScalars.contains { statIsKanji($0) } })
    }
}
'''

# ---------- subtitles of a deleted video ----------
a = s.index("    static func subtitle(_ file: URL, belongsTo video: URL) -> Bool {")
b = s.index("\n    }\n", a) + len("\n    }\n")
s = s[:a] + '''    static func subtitle(_ file: URL, belongsTo video: URL) -> Bool {
        guard isSubtitle(file.lastPathComponent) else { return false }
        let base = video.deletingPathExtension().lastPathComponent
        let full = video.lastPathComponent
        var stem = file.deletingPathExtension().lastPathComponent
        // up to three short tags: .ja, .jimaku, .forced (a number like ".5" is part of the episode, not a tag)
        for _ in 0 ..< 3 {
            if stem == base || stem == full { return true }
            let tag = (stem as NSString).pathExtension
            guard !tag.isEmpty, tag.count <= 16, !tag.contains(" "), Int(tag) == nil else { break }
            stem = (stem as NSString).deletingPathExtension
        }
        return stem == base || stem == full
    }
''' + s[b:]

s = once(s, '''        try? fm.removeItem(at: item.url)
        status[name] = nil
        progress[name] = nil
        reload()
''', '''        try? fm.removeItem(at: item.url)
        if !item.isFolder, VideoLibraryStore.isVideo(name) {
            // subtitle files left without their video (also from earlier deletions)
            let remaining = (try? fm.contentsOfDirectory(at: folder, includingPropertiesForKeys: nil)) ?? []
            let videos = remaining.filter { VideoLibraryStore.isVideo($0.lastPathComponent) }
            for file in remaining where VideoLibraryStore.isSubtitle(file.lastPathComponent)
                && !videos.contains(where: { VideoLibraryStore.subtitle(file, belongsTo: $0) }) {
                try? fm.removeItem(at: file)
            }
            UserDefaults.standard.removeObject(forKey: "coverage." + name)
        }
        status[name] = nil
        progress[name] = nil
        coverage[name] = nil
        reload()
''', "delete orphans")

hv.write_text(s, encoding="utf-8")
print("v1.49 fixes applied")
