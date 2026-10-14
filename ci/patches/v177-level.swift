
// MARK: - Level v1.77: JLPT estimate by the cards and the frequent words, frequent kanji

/// The JLPT words and the kanji order of CalibrationData.
@available(iOS 16.0, *)
enum LevelData {
    private(set) static var jlpt: [(level: Int, word: String, reading: String)] = []
    /// kanji from the most frequent, with the rank of the most frequent word that has it
    private(set) static var kanji: [(kanji: String, first: Int)] = []

    @MainActor
    static func load() {
        guard jlpt.isEmpty && kanji.isEmpty else { return }
        for line in CalibrationData.text.split(separator: "\n") {
            let parts = line.split(separator: "\t", omittingEmptySubsequences: false).map { String($0) }
            guard parts.count >= 4, let number = Int(parts[1]) else { continue }
            if parts[0] == "j" {
                jlpt.append((level: number, word: parts[2], reading: parts[3]))
            } else if parts[0] == "c", let first = Int(parts[3]) {
                kanji.append((kanji: parts[2], first: first))
            }
        }
    }
}

/// A rough JLPT level: the share of the JLPT words known by your cards and the frequent words; and how many of the
/// most frequent kanji you know.
@available(iOS 16.0, *)
enum JLPTEstimate {
    static let threshold = 0.75

    struct LevelShare: Identifiable {
        var id: Int { level }
        let level: Int
        let known: Int
        let total: Int
        /// this level and all the easier ones
        let knownUpTo: Int
        let totalUpTo: Int
    }

    struct KanjiTier: Identifiable {
        var id: Int { top }
        let top: Int
        let known: Int
    }

    struct Result {
        let levels: [LevelShare]
        /// the hardest level reached, nil below N5
        let reached: Int?
        let next: Int?
        let nextShare: Double
        let nextMissing: Int
        let kanji: [KanjiTier]
        let knownKanji: Int
        let cards: Int
        let vocabulary: Int
    }

    static func compute(cards: Set<String>, vocabulary: Int, jlpt: [(level: Int, word: String, reading: String)],
                        kanji: [(kanji: String, first: Int)]) -> Result {
        let index = KnownWordsIndex(cards)
        func known(_ word: String, _ reading: String) -> Bool {
            if index.forms.contains(word) || index.forms.contains(reading) { return true }
            if let rank = HighlightData.bestRank(base: word, reading: reading, text: word), rank <= vocabulary {
                return true
            }
            return false
        }
        var levels: [LevelShare] = []
        var knownUpTo = 0
        var totalUpTo = 0
        for level in [5, 4, 3, 2, 1] {
            let words = jlpt.filter { $0.level == level }
            guard !words.isEmpty else { continue }
            let count = words.filter { known($0.word, $0.reading) }.count
            knownUpTo += count
            totalUpTo += words.count
            levels.append(LevelShare(level: level, known: count, total: words.count, knownUpTo: knownUpTo,
                                     totalUpTo: totalUpTo))
        }
        var reached: Int? = nil
        for item in levels {
            guard Double(item.knownUpTo) >= threshold * Double(item.totalUpTo) else { break }
            reached = item.level
        }
        let nextLevel: Int? = reached.map { $0 - 1 } ?? 5
        var next: Int? = nil
        var nextShare = 0.0
        var nextMissing = 0
        if let nextLevel, let item = levels.first(where: { $0.level == nextLevel }) {
            next = nextLevel
            nextShare = Double(item.knownUpTo) / Double(max(1, item.totalUpTo))
            nextMissing = max(0, Int((threshold * Double(item.totalUpTo)).rounded(.up)) - item.knownUpTo)
        }
        // a kanji is known when a card has it or one of the frequent words does
        var knownKanji = Set<String>()
        for word in cards {
            for scalar in word.unicodeScalars where statIsKanji(scalar) {
                knownKanji.insert(String(scalar))
            }
        }
        for item in kanji where item.first <= vocabulary {
            knownKanji.insert(item.kanji)
        }
        var tiers: [KanjiTier] = []
        for top in [500, 1000, 2000, 3000] where top <= kanji.count {
            let known = kanji.prefix(top).filter { knownKanji.contains($0.kanji) }.count
            tiers.append(KanjiTier(top: top, known: known))
        }
        return Result(levels: levels, reached: reached, next: next, nextShare: nextShare, nextMissing: nextMissing,
                      kanji: tiers, knownKanji: knownKanji.count, cards: cards.count, vocabulary: vocabulary)
    }
}

/// "Уровень JLPT": the estimate, the progress to the next level and the frequent kanji.
@available(iOS 16.0, *)
struct JLPTEstimateView: View {
    @AppStorage("ykUserLevel") private var userLevel = 5
    @State private var result: JLPTEstimate.Result? = nil
    @State private var empty = false

    private static func percent(_ value: Double) -> String {
        String(Int((value * 100).rounded())) + "%"
    }

    var body: some View {
        List {
            if let result {
                summary(result)
                Section {
                    ForEach(result.levels) { item in
                        levelRow(item)
                    }
                } header: {
                    Text("Слова JLPT")
                } footer: {
                    Text("Доля слов уровня, которые есть в ваших карточках или среди частых слов.")
                }
                Section {
                    ForEach(result.kanji) { item in
                        kanjiRow(item)
                    }
                } header: {
                    Text("Частотные кандзи")
                } footer: {
                    Text("Кандзи знаком, если он есть в слове из ваших карточек или в одном из частых слов. Частотность кандзи — по тому, как часто встречаются слова с ним (Jiten). Всего знакомых кандзи: "
                         + String(result.knownKanji) + ".")
                }
            } else if empty {
                Text("В этой сборке нет списков JLPT.").foregroundColor(.secondary)
            } else {
                HStack(spacing: 10) {
                    ProgressView()
                    Text("Считаю…").foregroundColor(.secondary)
                }
            }
        }
        .navigationTitle("Уровень JLPT")
        .navigationBarTitleDisplayMode(.inline)
        .task {
            await load()
        }
    }

    private func summary(_ result: JLPTEstimate.Result) -> some View {
        let level: String = result.reached.map { "N" + String($0) } ?? "ниже N5"
        let basis: String = "Уровень достигнут, когда вы знаете 75% слов JLPT этого и всех более лёгких уровней. "
            + "Знакомыми считаются ваши карточки Anki (" + String(result.cards) + ") и "
            + String(result.vocabulary) + " самых частых слов (Jiten). Это оценка словаря, а не экзамена: "
            + "грамматику и аудирование она не учитывает."
        return Section {
            HStack {
                Text("Примерный уровень")
                Spacer()
                Text(level).font(.title3.bold())
            }
            if let next = result.next {
                VStack(alignment: .leading, spacing: 6) {
                    Text("До N" + String(next) + ": " + JLPTEstimateView.percent(result.nextShare) + " слов, осталось ≈ "
                         + String(result.nextMissing))
                    ProgressView(value: min(1, result.nextShare / JLPTEstimate.threshold))
                        .tint(.accentColor)
                }
                .padding(.vertical, 2)
            }
            if let reached = result.reached, reached != userLevel {
                Button("Поставить N" + String(reached) + " в «Моём уровне»") {
                    userLevel = reached
                }
            }
        } footer: {
            Text(basis)
        }
    }

    private func levelRow(_ item: JLPTEstimate.LevelShare) -> some View {
        let share = Double(item.known) / Double(max(1, item.total))
        let numbers: String = JLPTEstimateView.percent(share) + " · " + String(item.known) + " из " + String(item.total)
        return VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text("N" + String(item.level))
                Spacer()
                Text(numbers).foregroundColor(.secondary)
            }
            ProgressView(value: share)
                .tint(share >= JLPTEstimate.threshold ? .green : .accentColor)
        }
        .padding(.vertical, 2)
    }

    private func kanjiRow(_ item: JLPTEstimate.KanjiTier) -> some View {
        let share = Double(item.known) / Double(item.top)
        return VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text("Топ-" + String(item.top))
                Spacer()
                Text(String(item.known) + " · " + JLPTEstimateView.percent(share)).foregroundColor(.secondary)
            }
            ProgressView(value: share)
                .tint(.accentColor)
        }
        .padding(.vertical, 2)
    }

    private func load() async {
        LevelData.load()
        guard !LevelData.jlpt.isEmpty else {
            empty = true
            return
        }
        // the frequency tables load on the main thread
        _ = HighlightData.rank(base: "の", reading: "の", dict: "main")
        let cards = HighlightData.minedWords()
        let vocabulary = VideoLibraryStore.vocabulary(level: VideoLibraryStore.userLevel)
        let jlpt = LevelData.jlpt
        let kanji = LevelData.kanji
        result = await Task.detached(priority: .userInitiated) {
            JLPTEstimate.compute(cards: cards, vocabulary: vocabulary, jlpt: jlpt, kanji: kanji)
        }.value
    }
}
