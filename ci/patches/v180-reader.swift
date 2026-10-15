
// MARK: - Reading v1.80: smart furigana, search in the chapter

/// The smart furigana of the reader: the reading over the kanji of the words the analysis does not count as known
/// (the same rules as the coverage: mature cards, JLPT up to the level, the frequent words).
@available(iOS 16.0, *)
@MainActor
final class ReaderFurigana {
    static let shared = ReaderFurigana()

    /// 食べた: head "", core "食", reading "た", tail "べた"
    struct Ruby {
        let head: String
        let core: String
        let reading: String
        let tail: String
    }

    private var judge: WordKnowledge? = nil
    private var stamp: (UInt64, Int, Int)? = nil
    private var known: [String: Bool] = [:]

    /// The judge of the known words now (built again when the cards, the level or the vocabulary change).
    func prepare() async {
        let index = await CatalogStore.knownIndex()
        let level = VideoLibraryStore.userLevel
        let vocabulary = VideoLibraryStore.vocabulary(level: level)
        if let stamp, stamp == (index.fingerprint, level, vocabulary) {
            return
        }
        judge = WordKnowledge(index: index, level: level, vocabulary: vocabulary)
        stamp = (index.fingerprint, level, vocabulary)
        known = [:]
    }

    /// The readings to show in a paragraph, by token id.
    func rubies(for tokens: [LookupToken]) -> [Int: Ruby] {
        guard let judge else { return [:] }
        var result: [Int: Ruby] = [:]
        for token in tokens where token.text.unicodeScalars.contains(where: { statIsKanji($0) }) && WordKnowledge.counted(token) {
            let key = token.text + "|" + token.base
            let isKnown: Bool
            if let saved = known[key] {
                isKnown = saved
            } else {
                isKnown = judge.known(token)
                known[key] = isKnown
            }
            if !isKnown, let ruby = ReaderFurigana.split(token.text, token.reading) {
                result[token.id] = ruby
            }
        }
        return result
    }

    /// The reading over the kanji only: the kana the word and its reading share at the ends stay outside.
    static func split(_ text: String, _ reading: String) -> Ruby? {
        let word = Array(text)
        let plain = Array(HighlightData.hiragana(text))
        let kana = Array(HighlightData.hiragana(reading))
        guard !kana.isEmpty, plain.count == word.count else { return nil }
        func isKanji(_ letter: Character) -> Bool {
            letter.unicodeScalars.contains { statIsKanji($0) }
        }
        var start = 0
        while start < word.count, start < kana.count, !isKanji(word[start]), plain[start] == kana[start] {
            start += 1
        }
        var end = 0
        while end < word.count - start, end < kana.count - start, !isKanji(word[word.count - 1 - end]),
              plain[word.count - 1 - end] == kana[kana.count - 1 - end] {
            end += 1
        }
        let core = String(word[start ..< word.count - end])
        let over = String(kana[start ..< kana.count - end])
        guard core.unicodeScalars.contains(where: { statIsKanji($0) }), !over.isEmpty else { return nil }
        return Ruby(head: String(word[0 ..< start]), core: core, reading: over, tail: String(word[(word.count - end)...]))
    }
}

/// Search in the chapter: the paragraphs with the text; a tap goes to one. The Japanese keyboard opens at once.
@available(iOS 16.0, *)
struct ChapterSearchSheet: View {
    let paragraphs: [String]
    let onPick: (Int) -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var query = ""

    private struct Match: Identifiable {
        let id: Int
        let snippet: AttributedString
    }

    private var matches: [Match] {
        let needle = query.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !needle.isEmpty else { return [] }
        var result: [Match] = []
        for (index, paragraph) in paragraphs.enumerated() {
            guard let range = paragraph.range(of: needle) else { continue }
            let start = paragraph.index(range.lowerBound, offsetBy: -12, limitedBy: paragraph.startIndex) ?? paragraph.startIndex
            let end = paragraph.index(range.upperBound, offsetBy: 30, limitedBy: paragraph.endIndex) ?? paragraph.endIndex
            var snippet = AttributedString((start > paragraph.startIndex ? "…" : "") + String(paragraph[start ..< end])
                                           + (end < paragraph.endIndex ? "…" : ""))
            if let found = snippet.range(of: needle) {
                snippet[found].foregroundColor = .accentColor
                snippet[found].font = .body.bold()
            }
            result.append(Match(id: index, snippet: snippet))
        }
        return result
    }

    var body: some View {
        let found = matches
        return VStack(spacing: 6) {
            HStack(spacing: 10) {
                Image(systemName: "magnifyingglass").foregroundColor(.secondary)
                JapaneseTextField(text: $query, placeholder: "Найти в главе") {}
                    .frame(height: 36)
            }
            .padding(.horizontal, 14)
            .padding(.vertical, 6)
            .background(Color(.secondarySystemBackground))
            .cornerRadius(12)
            .padding(.horizontal, 12)
            .padding(.top, 14)
            List {
                if !query.isEmpty {
                    Text(found.isEmpty ? "Не найдено" : "Найдено: " + String(found.count))
                        .font(.footnote)
                        .foregroundColor(.secondary)
                }
                ForEach(found) { match in
                    Button {
                        onPick(match.id)
                        dismiss()
                    } label: {
                        Text(match.snippet).foregroundColor(.primary)
                    }
                }
            }
            .listStyle(.plain)
        }
        .presentationDetents([.medium, .large])
        .presentationDragIndicator(.visible)
    }
}
