# v1.94: furigana over its own kanji, as on the Anki card: the reading of an all-kanji word is divided by the same
# rule as in the card template (殺人事件 → さつ|じん|じ|けん) and every kanji gets its part; when the reading does not
# divide evenly, it stays over the whole word as before. In the reader and in the subtitles.
import pathlib


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")

s = once(s, '''    struct Ruby {
        let head: String
        let core: String
        let reading: String
        let tail: String
    }
''', '''    struct Ruby {
        let head: String
        let core: String
        let reading: String
        let tail: String
        /// the reading of every kanji of the core, when it divides (as on the Anki card)
        var parts: [String]? = nil
    }
''', "ruby parts")
s = once(s, '''        return Ruby(head: String(word[0 ..< start]), core: core, reading: over, tail: String(word[(word.count - end)...]))
''', '''        var ruby = Ruby(head: String(word[0 ..< start]), core: core, reading: over, tail: String(word[(word.count - end)...]))
        ruby.parts = perKanji(core, over)
        return ruby
    }

    /// The reading of every kanji of an all-kanji word (さつ|じん|じ|けん), the rule of the Anki card: syllables (small
    /// kana, ん, っ, ー, う and い go with the kana before them), then く / き / つ / ち joined to the syllable before while
    /// there are more syllables than kanji, then the two shortest neighbours; nil when it does not come out even.
    static func perKanji(_ core: String, _ reading: String) -> [String]? {
        let letters = Array(core)
        guard letters.count > 1,
              letters.allSatisfy({ $0 == "々" || $0.unicodeScalars.allSatisfy { statIsKanji($0) } }) else { return nil }
        let attached: Set<Character> = Set("ゃゅょぁぃぅぇぉゎャュョァィゥェォヮんンっッーうウいイ")
        var parts: [String] = []
        for kana in reading {
            if !parts.isEmpty, attached.contains(kana) {
                parts[parts.count - 1].append(kana)
            } else {
                parts.append(String(kana))
            }
        }
        let joining: Set<String> = ["く", "き", "つ", "ち", "ク", "キ", "ツ", "チ"]
        var i = parts.count - 1
        while i > 0, parts.count > letters.count {
            if joining.contains(parts[i]) {
                parts[i - 1] += parts[i]
                parts.remove(at: i)
            }
            i -= 1
        }
        while parts.count > letters.count {
            var best = parts.count - 2
            var j = parts.count - 2
            while j >= 0 {
                if parts[j].count + parts[j + 1].count < parts[best].count + parts[best + 1].count {
                    best = j
                }
                j -= 1
            }
            parts[best] += parts[best + 1]
            parts.remove(at: best + 1)
        }
        return parts.count == letters.count ? parts : nil
''', "per kanji split")

s = once(s, '''                VStack(spacing: 0) {
                    Text(ruby.reading)
                        .font(small)
                        .foregroundColor(.white.opacity(0.8))
                        .lineLimit(1)
                        .fixedSize()
                    Text(ruby.core)
                }
''', '''                RubyColumns(ruby: ruby, readingFont: small, readingColor: .white.opacity(0.8))
''', "subtitle ruby columns")
s = once(s, '''                VStack(spacing: 0) {
                    Text(ruby.reading)
                        .font(.system(size: fontSize * 0.5))
                        .foregroundColor(.secondary)
                        .lineLimit(1)
                        .fixedSize()
                    Text(ruby.core)
                }
''', '''                RubyColumns(ruby: ruby, readingFont: .system(size: fontSize * 0.5), readingColor: .secondary)
''', "reader ruby columns")

s = s.rstrip("\n") + '''

/// The kanji of a word with furigana: every kanji with its own reading over it when the reading divides (as on the
/// Anki card), else the whole reading over them all. The kanji take the font around them.
@available(iOS 16.0, *)
struct RubyColumns: View {
    let ruby: ReaderFurigana.Ruby
    let readingFont: Font
    let readingColor: Color

    var body: some View {
        if let parts = ruby.parts, parts.count == ruby.core.count {
            let letters = Array(ruby.core)
            HStack(alignment: .bottom, spacing: 0) {
                ForEach(letters.indices, id: \\.self) { i in
                    VStack(spacing: 0) {
                        Text(parts[i])
                            .font(readingFont)
                            .foregroundColor(readingColor)
                            .lineLimit(1)
                            .fixedSize()
                        Text(String(letters[i]))
                    }
                }
            }
        } else {
            VStack(spacing: 0) {
                Text(ruby.reading)
                    .font(readingFont)
                    .foregroundColor(readingColor)
                    .lineLimit(1)
                    .fixedSize()
                Text(ruby.core)
            }
        }
    }
}
'''
hv.write_text(s, encoding="utf-8")
print("v1.94 furigana applied")
