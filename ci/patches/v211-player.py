# v2.11 (the app): the smart furigana of the subtitles sits closer to its kanji; the strength of Anime4K.
# - The reading over an unknown word of the subtitles comes down by a fifth of the subtitle size (the reader keeps its
#   spacing); the words without a reading keep the same room, so the line stays even.
# - Player settings → «Восстановление линий (Anime4K)» → «Сила»: S (light, as before), M and L (heavier: Anime4K
#   Restore CNN M / L, converted at build time by v211-anime4k.py; a kind that did not convert is not offered).
import pathlib


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")

# --- furigana closer to the kanji in the subtitles
s = once(s, '''struct RubyColumns: View {
    let ruby: ReaderFurigana.Ruby
    let readingFont: Font
    let readingColor: Color
''', '''struct RubyColumns: View {
    let ruby: ReaderFurigana.Ruby
    let readingFont: Font
    let readingColor: Color
    /// how far the reading comes down onto the room above the kanji
    var gap: CGFloat = 0
''', "ruby gap")
s = once(s, '''                ForEach(letters.indices, id: \\.self) { i in
                    VStack(spacing: 0) {
                        Text(parts[i])''', '''                ForEach(letters.indices, id: \\.self) { i in
                    VStack(spacing: -gap) {
                        Text(parts[i])''', "ruby parts spacing")
s = once(s, '''            VStack(spacing: 0) {
                Text(ruby.reading)''', '''            VStack(spacing: -gap) {
                Text(ruby.reading)''', "ruby spacing")
s = once(s, '''    @State private var small = SubtitleStyle.font(scale: 0.5)
    @State private var rubies: [Int: ReaderFurigana.Ruby] = [:]
''', '''    @State private var small = SubtitleStyle.font(scale: 0.5)
    @State private var rubyGap = SubtitleStyle.size() * 0.2
    @State private var rubies: [Int: ReaderFurigana.Ruby] = [:]
''', "subtitle gap state")
s = once(s, '''                RubyColumns(ruby: ruby, readingFont: small, readingColor: .white.opacity(0.8))''',
         '''                RubyColumns(ruby: ruby, readingFont: small, readingColor: .white.opacity(0.8), gap: rubyGap)''',
         "subtitle ruby")
n = s.index("struct SubtitleLookupBar: View {")
m = s.index("    var body: some View {", n)
part = s[n:m]
part = once(part, '''            VStack(spacing: 0) {
                Text(" ")
                    .font(small)''', '''            VStack(spacing: -rubyGap) {
                Text(" ")
                    .font(small)''', "subtitle placeholder")
s = s[:n] + part + s[m:]
s = once(s, '''    static func font(scale: CGFloat = 1) -> Font {
        var size: CGFloat = 22''', '''    /// The size of the subtitles (Настройки → Размер субтитров).
    static func size() -> CGFloat {
        guard let json = (try? Storage.config.get())?.data(using: .utf8),
              let root = (try? JSONSerialization.jsonObject(with: json)) as? [String: Any] else { return 22 }
        let value = CGFloat((root["general.subtitle_size"] as? NSNumber)?.doubleValue ?? 22)
        return min(max(value, 12), 40)
    }

    static func font(scale: CGFloat = 1) -> Font {
        var size: CGFloat = 22''', "subtitle size")

# --- the strength of Anime4K
s = once(s, '''              @AppStorage("ykAnime4K") private var ykAnime4K = false
''', '''              @AppStorage("ykAnime4K") private var ykAnime4K = false
              @AppStorage("ykAnime4KPreset") private var ykAnime4KPreset = "S"
''', "anime4k preset state")
s = once(s, '''                              Toggle("Восстановление линий (Anime4K)", isOn: $ykAnime4K)
                                  .disabled(!YKVideoFilters.anime4KAvailable)
''', '''                              Toggle("Восстановление линий (Anime4K)", isOn: $ykAnime4K)
                                  .disabled(!YKVideoFilters.anime4KAvailable)
                              if ykAnime4K && !YKVideoFilters.heavierPresets.isEmpty {
                                  Picker("Сила", selection: $ykAnime4KPreset) {
                                      Text("S — лёгкая").tag("S")
                                      ForEach(YKVideoFilters.heavierPresets, id: \\.self) { preset in
                                          Text(preset == "M" ? "M — сильнее" : "L — тяжёлая").tag(preset)
                                      }
                                  }
                              }
''', "anime4k preset picker")
hv.write_text(s, encoding="utf-8")
print("v2.11 player applied")
