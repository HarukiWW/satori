/// What the calibration found: the share of the words (not in the cards) that are known, by frequency rank. The JLPT
/// estimate and the level the calibration suggests are both counted from it, so they agree.
struct KnowledgeCurve: Codable {
    static let key = "ykKnowledgeCurve"
    /// band centers (ranks), from the most frequent
    let ranks: [Double]
    /// shares known there (never growing with the rank)
    let shares: [Double]
    var date = Date()

    /// The share at a rank: between the bands on a log scale; more frequent than the first band, up to 98% at the
    /// top 100; rarer than the last one or not in the lists, as the last one.
    func share(at rank: Int?) -> Double {
        guard let first = shares.first, let last = shares.last, ranks.count == shares.count else { return 0 }
        guard let rank else { return last }
        let r = Double(max(1, rank))
        if r <= ranks[0] {
            let top = max(first, 0.98)
            guard ranks[0] > 100, r > 100 else { return top }
            let t = (log(r) - log(100)) / (log(ranks[0]) - log(100))
            return top + t * (first - top)
        }
        for i in 1 ..< ranks.count where r <= ranks[i] {
            let t = (log(r) - log(ranks[i - 1])) / (log(ranks[i]) - log(ranks[i - 1]))
            return shares[i - 1] + t * (shares[i] - shares[i - 1])
        }
        return last
    }

    static func saved() -> KnowledgeCurve? {
        guard let data = UserDefaults.standard.data(forKey: key) else { return nil }
        return try? JSONDecoder().decode(KnowledgeCurve.self, from: data)
    }

    func save() {
        if let data = try? JSONEncoder().encode(self) {
            UserDefaults.standard.set(data, forKey: KnowledgeCurve.key)
        }
    }
}

/// The calibration of "Мой уровень японского": about 63 frequent words around the present number (from half of it to
/// six times it), "know" or "don't know". The number moves to where about half of the words are known; the answers
/// give the knowledge curve, and the JLPT level is counted from it like on the "Уровень JLPT" page.
@available(iOS 16.0, *)
enum Calibration {
    struct Word: Identifiable {
        let id: Int
        let word: String
        let reading: String
        /// written in kana as a rule (する, きっと): the reading is shown
        let kana: Bool
        let band: Int

        var shown: String {
            kana && !reading.isEmpty ? reading : word
        }

        var hint: String? {
            kana || reading.isEmpty || reading == word ? nil : reading
        }
    }

    struct Band {
        let from: Int
        let to: Int

        var center: Double {
            (Double(from) * Double(to)).squareRoot()
        }
    }

    struct BandAnswer: Identifiable {
        let id: Int
        let band: Band
        let known: Int
        let asked: Int
    }

    struct Found {
        let vocabulary: Int
        /// every band known by more than half: the boundary may be further
        let open: Bool
        let bands: [BandAnswer]
        let curve: KnowledgeCurve
    }

    private static var frequency: [(rank: Int, word: String, reading: String, kana: Bool)] = []

    private static func load() {
        guard frequency.isEmpty else { return }
        for line in CalibrationData.text.split(separator: "\n") {
            let parts = line.split(separator: "\t", omittingEmptySubsequences: false).map { String($0) }
            guard parts.count >= 4, parts[0] == "f" || parts[0] == "k", let number = Int(parts[1]) else { continue }
            frequency.append((rank: number, word: parts[2], reading: parts[3], kana: parts[0] == "k"))
        }
    }

    /// The word lists are in this build (they are made from the dictionaries of the release).
    @MainActor
    static var available: Bool {
        load()
        return !frequency.isEmpty
    }

    /// Bands of ranks from a half to six times the number of frequent words.
    static func bands(around vocabulary: Int) -> [Band] {
        let steps: [Double] = [0.5, 0.8, 1.0, 1.25, 1.6, 2.0, 2.6, 3.4, 4.5, 6.0]
        let top = frequency.last?.rank ?? 40000
        var result: [Band] = []
        for i in 0 ..< steps.count - 1 {
            let from = max(200, Int(Double(vocabulary) * steps[i]))
            let to = min(top, Int(Double(vocabulary) * steps[i + 1]))
            if to - from >= 30 {
                result.append(Band(from: from, to: to))
            }
        }
        return result
    }

    /// Seven words of every band in a random order: words to learn (one token in the dictionary), never a card.
    static func pick(bands: [Band], level: Int, vocabulary: Int, index: KnownWordsIndex) -> [Word] {
        let judge = WordKnowledge(index: index, level: level, vocabulary: vocabulary)
        var result: [Word] = []
        for (number, band) in bands.enumerated() {
            var taken = 0
            for item in frequency.filter({ $0.rank >= band.from && $0.rank < band.to }).shuffled() where taken < 7 {
                if index.forms.contains(item.word) { continue }
                let rank = HighlightData.bestRank(base: item.word, reading: item.reading, text: item.word) ?? item.rank
                guard rank >= band.from && rank < band.to else { continue }
                let tokens = autoreleasepool { NativeLookup.tokenize(item.word, charAt: 0).tokens }
                guard tokens.count == 1, let token = tokens.first, WordKnowledge.counted(token),
                      judge.inDictionary(token) else { continue }
                result.append(Word(id: result.count, word: item.word, reading: item.reading, kana: item.kana,
                                   band: number))
                taken += 1
            }
        }
        return result.shuffled()
    }

    /// Shares that do not grow with the rank (adjacent bands that break the order are pooled, by the words asked).
    static func decreasing(_ values: [(share: Double, weight: Double)]) -> [Double] {
        var blocks: [(sum: Double, weight: Double, count: Int)] = []
        for value in values {
            blocks.append((sum: value.share * value.weight, weight: value.weight, count: 1))
            while blocks.count > 1 {
                let last = blocks[blocks.count - 1]
                let previous = blocks[blocks.count - 2]
                guard last.sum / last.weight > previous.sum / previous.weight else { break }
                blocks.removeLast(2)
                blocks.append((sum: previous.sum + last.sum, weight: previous.weight + last.weight,
                               count: previous.count + last.count))
            }
        }
        var result: [Double] = []
        for block in blocks {
            result += Array(repeating: block.sum / block.weight, count: block.count)
        }
        return result
    }

    static func estimate(words: [Word], answers: [Int: Bool], bands: [Band], vocabulary: Int) -> Found {
        var bandAnswers: [BandAnswer] = []
        for (number, band) in bands.enumerated() {
            let asked = words.filter { $0.band == number }
            guard !asked.isEmpty else { continue }
            let known = asked.filter { answers[$0.id] == true }.count
            bandAnswers.append(BandAnswer(id: number, band: band, known: known, asked: asked.count))
        }
        guard !bandAnswers.isEmpty else {
            return Found(vocabulary: vocabulary, open: false, bands: [], curve: KnowledgeCurve(ranks: [], shares: []))
        }
        let fitted = decreasing(bandAnswers.map { (share: Double($0.known) / Double($0.asked), weight: Double($0.asked)) })
        // the boundary: where the share of known words falls below one half (between the centers of two bands)
        var boundary: Double
        var open = false
        if let first = fitted.firstIndex(where: { $0 < 0.5 }) {
            if first == 0 {
                boundary = Double(bandAnswers[0].band.from)
            } else {
                let a = log(bandAnswers[first - 1].band.center)
                let b = log(bandAnswers[first].band.center)
                let t = (fitted[first - 1] - 0.5) / max(fitted[first - 1] - fitted[first], 0.0001)
                boundary = exp(a + t * (b - a))
            }
        } else {
            boundary = Double(bandAnswers[bandAnswers.count - 1].band.to)
            open = true
        }
        let curve = KnowledgeCurve(ranks: bandAnswers.map { $0.band.center }, shares: fitted)
        let rounded = max(300, Int((boundary / 100).rounded()) * 100)
        return Found(vocabulary: rounded, open: open, bands: bandAnswers, curve: curve)
    }
}

/// The calibration screen: about 63 words one by one, "know" or "don't know", then the new boundaries to apply.
@available(iOS 16.0, *)
struct CalibrationView: View {
    @AppStorage("ykUserLevel") private var userLevel = 5
    @AppStorage("ykVocabSure") private var vocabSure = 0
    @State private var words: [Calibration.Word] = []
    @State private var bands: [Calibration.Band] = []
    @State private var answers: [Int: Bool] = [:]
    @State private var position = 0
    @State private var loading = false
    @State private var found: Calibration.Found? = nil
    @State private var estimate: JLPTEstimate.Result? = nil
    @State private var applied = false

    private var level: Int {
        (1 ... 5).contains(userLevel) ? userLevel : 5
    }

    private var vocabulary: Int {
        VideoLibraryStore.vocabulary(level: level)
    }

    var body: some View {
        Group {
            if let found, let estimate {
                resultView(found, estimate)
            } else if loading {
                VStack(spacing: 12) {
                    ProgressView()
                    Text(words.isEmpty ? "Подбираю слова…" : "Считаю…").foregroundColor(.secondary)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else if words.isEmpty {
                intro
            } else {
                question
            }
        }
        .navigationTitle("Калибровка")
        .navigationBarTitleDisplayMode(.inline)
    }

    private var intro: some View {
        let ready = Calibration.available
        let now: String = "Сейчас знакомыми считаются " + String(vocabulary) + " самых частых слов и слова JLPT до N"
            + String(level) + "."
        return List {
            Section {
                Text(now)
                Text("Калибровка покажет около 63 слов: от вдвое более частых до вшестеро более редких, чем ваше число. Ваши зрелые карточки не показываются. По ответам сдвинется число частых слов, а уровень JLPT посчитается по тем же ответам — так же, как на странице «Уровень JLPT по словам».")
                    .foregroundColor(.secondary)
                Text("Нажимайте «Знаю», если понимаете значение, увидев или услышав слово. Не угадывайте: от этого зависит точность. Займёт 2–3 минуты.")
                    .foregroundColor(.secondary)
            }
            Section {
                Button("Начать") {
                    Task { await start() }
                }
                .disabled(!ready)
            } footer: {
                if !ready {
                    Text("В этой сборке нет списка слов для калибровки.")
                }
            }
        }
    }

    private var question: some View {
        let word = words[position]
        return VStack(spacing: 18) {
            ProgressView(value: Double(position), total: Double(words.count))
                .padding(.horizontal, 20)
                .padding(.top, 12)
            Text(String(position + 1) + " из " + String(words.count))
                .font(.footnote)
                .foregroundColor(.secondary)
            Spacer()
            VStack(spacing: 8) {
                Text(word.shown)
                    .font(.system(size: 46, weight: .semibold))
                    .lineLimit(1)
                    .minimumScaleFactor(0.4)
                if let hint = word.hint {
                    Text(hint)
                        .font(.title3)
                        .foregroundColor(.secondary)
                }
            }
            .padding(.horizontal, 24)
            Spacer()
            HStack(spacing: 12) {
                Button {
                    answer(false)
                } label: {
                    Text("Не знаю").frame(maxWidth: .infinity)
                }
                .buttonStyle(.bordered)
                .controlSize(.large)
                Button {
                    answer(true)
                } label: {
                    Text("Знаю").frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.large)
            }
            .padding(.horizontal, 20)
            Button("Назад") {
                position = max(0, position - 1)
            }
            .disabled(position == 0)
            .padding(.bottom, 16)
        }
    }

    private func bandRow(_ item: Calibration.BandAnswer) -> some View {
        HStack {
            Text("Места " + String(item.band.from) + "–" + String(item.band.to))
            Spacer()
            Text(String(item.known) + " из " + String(item.asked)).foregroundColor(.secondary)
        }
    }

    private func levelRow(_ item: JLPTEstimate.LevelShare) -> some View {
        HStack {
            Text("JLPT N" + String(item.level))
            Spacer()
            Text(JLPTEstimate.percent(item.share)).foregroundColor(.secondary)
        }
    }

    /// The level the answers reach (N5 below it; unchanged without the JLPT lists).
    private func suggestedLevel(_ estimate: JLPTEstimate.Result) -> Int {
        estimate.levels.isEmpty ? level : (estimate.reached ?? 5)
    }

    private func resultView(_ found: Calibration.Found, _ estimate: JLPTEstimate.Result) -> some View {
        let frequent: String = String(vocabulary) + " → " + String(found.vocabulary)
        let jlptLevels: String = "N" + String(level) + " → N" + String(suggestedLevel(estimate))
        return List {
            Section {
                HStack {
                    Text("Частых слов")
                    Spacer()
                    Text(frequent).foregroundColor(.secondary)
                }
                HStack {
                    Text("Уровень JLPT")
                    Spacer()
                    Text(jlptLevels).foregroundColor(.secondary)
                }
            } header: {
                Text("Результат")
            } footer: {
                Text(found.open
                     ? "Вы знаете больше половины слов даже в самой редкой группе: граница может быть дальше. Примените результат и пройдите калибровку ещё раз."
                     : "Граница — место в списке частотности, где вы знаете примерно половину слов: чаще неё слова в основном знакомы, реже — нет. Уровень JLPT — по тем же ответам: достигнут, когда знакомы 75% слов его и всех более лёгких уровней.")
            }
            Section {
                ForEach(found.bands) { item in
                    bandRow(item)
                }
            } header: {
                Text("Ответы")
            }
            Section {
                ForEach(estimate.levels) { item in
                    levelRow(item)
                }
            } header: {
                Text("Слова JLPT по этим ответам")
            } footer: {
                Text("Ваши карточки Anki — знакомы, остальные слова — с той долей, которую показали ответы для их частотности.")
            }
            Section {
                Button(applied ? "Применено" : "Применить") {
                    vocabSure = found.vocabulary
                    userLevel = suggestedLevel(estimate)
                    found.curve.save()
                    applied = true
                }
                .disabled(applied)
                Button("Пройти ещё раз") {
                    self.found = nil
                    self.estimate = nil
                    words = []
                    answers = [:]
                    applied = false
                }
            } footer: {
                Text("Покрытие и сложность серий, глав и тайтлов пересчитаются сами.")
            }
        }
    }

    private func answer(_ known: Bool) {
        guard !loading else { return }
        answers[words[position].id] = known
        if position + 1 < words.count {
            position += 1
        } else {
            Task { await finish() }
        }
    }

    private func start() async {
        loading = true
        let index = await CatalogStore.knownIndex()
        let level = self.level
        let vocabulary = self.vocabulary
        let bands = Calibration.bands(around: vocabulary)
        let picked = await Task.detached(priority: .userInitiated) {
            Calibration.pick(bands: bands, level: level, vocabulary: vocabulary, index: index)
        }.value
        self.bands = bands
        answers = [:]
        position = 0
        words = picked
        loading = false
    }

    /// The boundary from the answers, then the JLPT level from the same answers.
    private func finish() async {
        loading = true
        let result = Calibration.estimate(words: words, answers: answers, bands: bands, vocabulary: vocabulary)
        LevelData.load()
        let cards = HighlightData.minedWords()
        let jlpt = LevelData.jlpt
        let kanji = LevelData.kanji
        let curve = result.curve
        let boundary = result.vocabulary
        let levels = await Task.detached(priority: .userInitiated) {
            JLPTEstimate.compute(cards: cards, vocabulary: boundary, curve: curve, jlpt: jlpt, kanji: kanji)
        }.value
        estimate = levels
        found = result
        loading = false
    }
}

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

/// A rough JLPT level: how many JLPT words you know — your cards, and the other words with the share the calibration
/// found for their frequency (without a calibration: the frequent words up to the number); and the frequent kanji.
@available(iOS 16.0, *)
enum JLPTEstimate {
    static let threshold = 0.75

    struct LevelShare: Identifiable {
        var id: Int { level }
        let level: Int
        let known: Double
        let total: Int
        /// this level and all the easier ones
        let knownUpTo: Double
        let totalUpTo: Int

        var share: Double {
            known / Double(max(1, total))
        }
    }

    struct KanjiTier: Identifiable {
        var id: Int { top }
        let top: Int
        let known: Double
    }

    struct Result {
        let levels: [LevelShare]
        /// the hardest level reached, nil below N5
        let reached: Int?
        let next: Int?
        let nextShare: Double
        let nextMissing: Int
        let kanji: [KanjiTier]
        let cards: Int
        let vocabulary: Int
        let calibrated: Bool
    }

    static func percent(_ value: Double) -> String {
        String(Int((value * 100).rounded())) + "%"
    }

    static func compute(cards: Set<String>, vocabulary: Int, curve: KnowledgeCurve?,
                        jlpt: [(level: Int, word: String, reading: String)],
                        kanji: [(kanji: String, first: Int)]) -> Result {
        let index = KnownWordsIndex(cards)
        let usable = curve.map { !$0.shares.isEmpty } ?? false
        func known(_ word: String, _ reading: String) -> Double {
            if index.forms.contains(word) || index.forms.contains(reading) { return 1 }
            let rank = HighlightData.bestRank(base: word, reading: reading, text: word)
            if usable, let curve {
                return curve.share(at: rank)
            }
            return (rank ?? Int.max) <= vocabulary ? 1 : 0
        }
        var levels: [LevelShare] = []
        var knownUpTo = 0.0
        var totalUpTo = 0
        for level in [5, 4, 3, 2, 1] {
            let words = jlpt.filter { $0.level == level }
            guard !words.isEmpty else { continue }
            var count = 0.0
            for item in words {
                count += known(item.word, item.reading)
            }
            knownUpTo += count
            totalUpTo += words.count
            levels.append(LevelShare(level: level, known: count, total: words.count, knownUpTo: knownUpTo,
                                     totalUpTo: totalUpTo))
        }
        var reached: Int? = nil
        for item in levels {
            guard item.knownUpTo >= threshold * Double(item.totalUpTo) else { break }
            reached = item.level
        }
        let nextLevel: Int = reached.map { $0 - 1 } ?? 5
        var next: Int? = nil
        var nextShare = 0.0
        var nextMissing = 0
        if let item = levels.first(where: { $0.level == nextLevel }) {
            next = nextLevel
            nextShare = item.knownUpTo / Double(max(1, item.totalUpTo))
            nextMissing = max(0, Int((threshold * Double(item.totalUpTo) - item.knownUpTo).rounded(.up)))
        }
        // a kanji is known when a card has it; otherwise as its most frequent word
        var cardKanji = Set<String>()
        for word in cards {
            for scalar in word.unicodeScalars where statIsKanji(scalar) {
                cardKanji.insert(String(scalar))
            }
        }
        var tiers: [KanjiTier] = []
        for top in [500, 1000, 2000, 3000] where top <= kanji.count {
            var count = 0.0
            for item in kanji.prefix(top) {
                if cardKanji.contains(item.kanji) {
                    count += 1
                } else if usable, let curve {
                    count += curve.share(at: item.first)
                } else if item.first <= vocabulary {
                    count += 1
                }
            }
            tiers.append(KanjiTier(top: top, known: count))
        }
        return Result(levels: levels, reached: reached, next: next, nextShare: nextShare, nextMissing: nextMissing,
                      kanji: tiers, cards: cards.count, vocabulary: vocabulary, calibrated: usable)
    }
}

/// "Уровень JLPT": the estimate, the progress to the next level and the frequent kanji.
@available(iOS 16.0, *)
struct JLPTEstimateView: View {
    @AppStorage("ykUserLevel") private var userLevel = 5
    @State private var result: JLPTEstimate.Result? = nil
    @State private var empty = false

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
                    Text(result.calibrated
                         ? "Доля слов уровня, которые вы знаете: карточки Anki и остальные слова с той долей, которую калибровка показала для их частотности."
                         : "Доля слов уровня, которые есть в ваших карточках или среди частых слов. Пройдите калибровку — оценка станет точнее.")
                }
                Section {
                    ForEach(result.kanji) { item in
                        kanjiRow(item)
                    }
                } header: {
                    Text("Частотные кандзи")
                } footer: {
                    Text("Кандзи знаком, если он есть в слове из ваших карточек; иначе — как самое частое слово с ним. Частотность кандзи — по тому, как часто встречаются слова с ним (Jiten).")
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
        let known: String = result.calibrated
            ? "по ответам калибровки и вашим карточкам Anki (" + String(result.cards) + ")"
            : "по вашим карточкам Anki (" + String(result.cards) + ") и " + String(result.vocabulary) + " самым частым словам"
        let basis: String = "Уровень достигнут, когда вы знаете 75% слов JLPT этого и всех более лёгких уровней. Знакомые слова — "
            + known + ". Это оценка словаря, а не экзамена: грамматику и аудирование она не учитывает."
        return Section {
            HStack {
                Text("Примерный уровень")
                Spacer()
                Text(level).font(.title3.bold())
            }
            if let next = result.next {
                VStack(alignment: .leading, spacing: 6) {
                    Text("До N" + String(next) + ": " + JLPTEstimate.percent(result.nextShare) + " слов, осталось ≈ "
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
        let numbers: String = JLPTEstimate.percent(item.share) + " · ≈" + String(Int(item.known.rounded())) + " из "
            + String(item.total)
        return VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text("N" + String(item.level))
                Spacer()
                Text(numbers).foregroundColor(.secondary)
            }
            ProgressView(value: item.share)
                .tint(item.share >= JLPTEstimate.threshold ? .green : .accentColor)
        }
        .padding(.vertical, 2)
    }

    private func kanjiRow(_ item: JLPTEstimate.KanjiTier) -> some View {
        let share = item.known / Double(item.top)
        let numbers: String = "≈" + String(Int(item.known.rounded())) + " · " + JLPTEstimate.percent(share)
        return VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text("Топ-" + String(item.top))
                Spacer()
                Text(numbers).foregroundColor(.secondary)
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
        let curve = KnowledgeCurve.saved()
        let jlpt = LevelData.jlpt
        let kanji = LevelData.kanji
        result = await Task.detached(priority: .userInitiated) {
            JLPTEstimate.compute(cards: cards, vocabulary: vocabulary, curve: curve, jlpt: jlpt, kanji: kanji)
        }.value
    }
}

