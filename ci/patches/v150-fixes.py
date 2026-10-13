# v1.50: crash after closing a video. The coverage of the list was recounted with a tokenizer call for every known
# word (thousands with an imported deck) inside one background loop, so the memory of every call was freed only at
# the end, and a second recount could start while the first one ran. Now: one recount at a time, the known word index
# is kept, memory is freed after every word and line, kana words and long strings are not tokenized. The lock screen
# frame is not taken after the player is closed.
import pathlib

hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


s = once(s, "    @Published var coverage: [String: Int] = [:]\n", """    @Published var coverage: [String: Int] = [:]
    private var coverageRunning = false
    private var knownIndex: (count: Int, index: KnownWordsIndex)?
""", "coverage state")

s = once(s, """        guard !pending.isEmpty else { return }
        Task { @MainActor in
            let index = await Task.detached(priority: .utility) { KnownWordsIndex(known) }.value
""", """        guard !pending.isEmpty, !coverageRunning else { return }
        coverageRunning = true
        Task { @MainActor in
            defer { coverageRunning = false }
            let index: KnownWordsIndex
            if let saved = knownIndex, saved.count == known.count {
                index = saved.index
            } else {
                index = await Task.detached(priority: .utility) { KnownWordsIndex(known) }.value
                knownIndex = (known.count, index)
            }
""", "one recount at a time")

s = once(s, "            for token in NativeLookup.tokenize(cue.text, charAt: 0).tokens {\n",
         "            // an empty line (an ASS line of formatting tags only) never goes to the tokenizer\n"
         "            guard !cue.text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { continue }\n"
         "            let tokens = autoreleasepool { NativeLookup.tokenize(cue.text, charAt: 0).tokens }\n"
         "            for token in tokens {\n", "cue pool")
s = once(s, """                    reading = KnownWordsIndex.isKana(base) ? HighlightData.hiragana(base)
                        : HighlightData.hiragana(NativeLookup.tokenize(base, charAt: 0).tokens.map { $0.reading }.joined())
""", """                    reading = KnownWordsIndex.isKana(base) ? HighlightData.hiragana(base) : autoreleasepool {
                        HighlightData.hiragana(NativeLookup.tokenize(base, charAt: 0).tokens.map { $0.reading }.joined())
                    }
""", "reading pool")

a = s.index("/// Known words for the coverage badge")
s = s[:a] + '''/// Known words for the coverage badge, matched in any form: the dictionary form of an inflected word, the word written
/// in kana, another spelling with the same reading and a common kanji, the stem of a する verb.
@available(iOS 16.0, *)
struct KnownWordsIndex {
    var forms = Set<String>()
    var kanaReadings = Set<String>()
    var kanjiByReading: [String: Set<Character>] = [:]

    init(_ words: Set<String>) {
        for raw in words {
            let word = KnownWordsIndex.clean(raw)
            // whole sentences from a deck are not words
            guard !word.isEmpty, word.count <= 24 else { continue }
            forms.insert(word)
            if word.hasSuffix("する"), word.count > 2 {
                forms.insert(String(word.dropLast(2)))
            }
            if KnownWordsIndex.isKana(word) {
                kanaReadings.insert(HighlightData.hiragana(word))
                continue
            }
            guard word.unicodeScalars.contains(where: { statIsKanji($0) }) else { continue }
            // the memory of every call is freed right away (thousands of words with an imported deck)
            let tokens = autoreleasepool { NativeLookup.tokenize(word, charAt: 0).tokens }
            if tokens.count == 1, !tokens[0].base.isEmpty {
                forms.insert(tokens[0].base)
            }
            let reading = HighlightData.hiragana(tokens.map { $0.reading }.joined())
            if !reading.isEmpty {
                kanjiByReading[reading, default: []].formUnion(KnownWordsIndex.kanji(word))
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

s = once(s, "            guard let frame = await player.thumbnailImageAtCurrentTime() else { return }\n",
         "            // the player may be closed by now: no frame then\n"
         "            guard nowPlayingReady, let frame = await player.thumbnailImageAtCurrentTime(), nowPlayingReady else { return }\n",
         "frame after close")

hv.write_text(s, encoding="utf-8")
print("v1.50 fixes applied")
