# v2.16: the smart furigana (subtitles and reader).
# - The reading is cut by kanji the way of the Anki card of 2026-10-18: every cut of the reading is tried and the one
#   with one or two syllables a kanji wins, no reading starting with a small kana, ん, っ, ー or the rest of a long
#   vowel (一員 いち|いん, 舌打 した|う, 会社 かい|しゃ); nothing fits (今日, 大人): the reading stays over the word.
# - A word with kana between its kanji (語り合う) gets the reading over its kanji only: the kana of the word are found
#   in the reading (かた|り|あ), not written again above themselves.
# - The furigana does not take a word of the JLPT of the user's level as known: only the cards, the marks and the most
#   frequent words count (議員 is N3, but not in Anki and 14 000th by frequency). The coverage keeps the JLPT rule.
import pathlib


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")

a = s.index("    /// The reading of every kanji of an all-kanji word (さつ|じん|じ|けん), the rule of the Anki card")
b = s.index("/// Search in the chapter: the paragraphs with the text", a)
end = s.rindex("}\n", a, b)
s = s[:a] + '''    private static let small: Set<Character> = Set("ゃゅょぁぃぅぇぉゎ")
    private static let rows: [(vowel: Character, kana: String)] = [
        ("a", "あかさたなはまやらわがざだばぱぁゃ"), ("i", "いきしちにひみりぎじぢびぴぃ"), ("u", "うくすつぬふむゆるぐずづぶぷぅゅ"),
        ("e", "えけせてねへめれげぜでべぺぇ"), ("o", "おこそとのほもよろをごぞどぼぽぉょ"),
    ]

    private static func vowel(_ kana: Character) -> Character? {
        rows.first { $0.kana.contains(kana) }?.vowel
    }

    /// The reading of every letter of the core ("" over its kana): the kana inside the core are found in the
    /// reading (語り合 → かた|り|あ), a run of kanji is cut by `cut`; nil when it does not fit (今日, 大人) and the
    /// reading stays over the whole core.
    static func perKanji(_ core: String, _ reading: String) -> [String]? {
        let letters = Array(core)
        guard letters.count > 1 else { return nil }
        func isKanji(_ letter: Character) -> Bool {
            letter == "々" || letter.unicodeScalars.allSatisfy { statIsKanji($0) }
        }
        var runs: [(kanji: Bool, text: [Character])] = []
        for letter in letters {
            let kanji = isKanji(letter)
            if let last = runs.last, last.kanji == kanji {
                runs[runs.count - 1].text.append(letter)
            } else {
                runs.append((kanji: kanji, text: [letter]))
            }
        }
        let kana = Array(HighlightData.hiragana(reading))
        guard let pieces = align(runs, kana) else { return nil }
        var parts: [String] = []
        for (run, piece) in zip(runs, pieces) {
            if !run.kanji {
                parts += run.text.map { _ in "" }
            } else if run.text.count == 1 {
                parts.append(String(piece))
            } else {
                guard let cuts = cut(piece, run.text.count) else { return nil }
                parts += cuts
            }
        }
        return parts.count == letters.count ? parts : nil
    }

    /// The reading of every run: a run of kana is itself in the reading, a run of kanji takes what is between.
    private static func align(_ runs: [(kanji: Bool, text: [Character])], _ kana: [Character]) -> [[Character]]? {
        func match(_ index: Int, _ at: Int) -> [[Character]]? {
            if index == runs.count {
                return at == kana.count ? [] : nil
            }
            let run = runs[index]
            if !run.kanji {
                let plain = Array(HighlightData.hiragana(String(run.text)))
                guard at + plain.count <= kana.count, Array(kana[at ..< at + plain.count]) == plain,
                      let rest = match(index + 1, at + plain.count) else { return nil }
                return [plain] + rest
            }
            var end = at + 1
            while end <= kana.count {
                if let rest = match(index + 1, end) {
                    return [Array(kana[at ..< end])] + rest
                }
                end += 1
            }
            return nil
        }
        return match(0, 0)
    }

    /// The reading of a run of kanji, one part a kanji: every cut is tried, the one with one or two syllables a kanji
    /// wins; no part starts with a small kana, ん, っ, ー or the rest of a long vowel (こう, せい), none ends in
    /// あ / い / え-row + う (たう). 一員 いち|いん, 舌打 した|う, 会社 かい|しゃ.
    static func cut(_ reading: [Character], _ count: Int) -> [String]? {
        guard reading.count >= count, reading.count <= 14, count <= 6 else { return nil }
        var best: [String]? = nil
        var bestScore = Double.infinity
        func valid(_ parts: [[Character]]) -> Bool {
            for (i, part) in parts.enumerated() {
                guard let first = part.first else { return false }
                if small.contains(first) || "んっー".contains(first) {
                    return false
                }
                if i > 0, let before = parts[i - 1].last.flatMap({ vowel($0) }) {
                    if first == "う" && (before == "o" || before == "u") {
                        return false
                    }
                    if first == "い" && before == "e" {
                        return false
                    }
                }
                if part.count >= 2, part[part.count - 1] == "う", let v = vowel(part[part.count - 2]),
                   v == "a" || v == "i" || v == "e" {
                    return false
                }
            }
            return true
        }
        func score(_ parts: [[Character]]) -> Double {
            var total: Double = 0
            for (i, part) in parts.enumerated() {
                let morae = Double(part.filter { !small.contains($0) }.count)
                total += (morae - 1.5) * (morae - 1.5)
                // い / う after a kana is more often its diphthong (かい, あい) than the next reading
                if i > 0, let first = part.first, first == "い" || first == "う" {
                    total += 0.3
                }
            }
            return total
        }
        func walk(_ from: Int, _ left: Int, _ taken: [[Character]]) {
            if left == 1 {
                let parts = taken + [Array(reading[from...])]
                if valid(parts) {
                    let value = score(parts)
                    if value < bestScore {
                        bestScore = value
                        best = parts.map { String($0) }
                    }
                }
                return
            }
            let last = reading.count - (left - 1)
            guard from + 1 <= last else { return }
            for end in (from + 1) ... last {
                walk(end, left - 1, taken + [Array(reading[from ..< end])])
            }
        }
        walk(0, count, [])
        return best
    }
''' + s[end:]

# --- RubyColumns: the kana of the core keep the room of a reading
s = once(s, '''                    VStack(spacing: -gap) {
                        Text(parts[i])''', '''                    VStack(spacing: -gap) {
                        Text(parts[i].isEmpty ? " " : parts[i])''', "ruby blank")

# --- the JLPT rule is not for the furigana
s = once(s, '''    let index: KnownWordsIndex
    let level: Int
    let vocabulary: Int
    private var readings: [String: String] = [:]
''', '''    let index: KnownWordsIndex
    let level: Int
    let vocabulary: Int
    /// the words of the JLPT up to the level are known (the coverage); the furigana does not take them as known
    var usesJLPT = true
    private var readings: [String: String] = [:]
''', "jlpt flag")
s = once(s, '''        let jlpt = HighlightData.jlptLevel(base: base, reading: lookup)
        if jlpt > 0, jlpt >= level { return true }''', '''        let jlpt = HighlightData.jlptLevel(base: base, reading: lookup)
        if usesJLPT, jlpt > 0, jlpt >= level { return true }''', "jlpt rule")
s = once(s, '''            let jlpt = HighlightData.jlptLevel(base: entry.headword, reading: reading)
            if jlpt > 0, jlpt >= level { return true }''', '''            let jlpt = HighlightData.jlptLevel(base: entry.headword, reading: reading)
            if usesJLPT, jlpt > 0, jlpt >= level { return true }''', "jlpt rule written")
s = once(s, '''        judge = WordKnowledge(index: index, level: level, vocabulary: vocabulary)
        stamp = (index.fingerprint, level, vocabulary)
        known = [:]''', '''        let made = WordKnowledge(index: index, level: level, vocabulary: vocabulary)
        made.usesJLPT = false
        judge = made
        stamp = (index.fingerprint, level, vocabulary)
        known = [:]''', "furigana judge")
hv.write_text(s, encoding="utf-8")
print("v2.16 furigana applied")
