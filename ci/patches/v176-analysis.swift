
// MARK: - Analysis v1.76: mature cards, speech speed, calibration

/// Speech speed in the grades: faster than the usual 320 morae a minute counts as fewer known words and clear lines
/// (4 and 10 points for every 50 morae a minute, at most 6 and 15), slower speech as more.
enum SpeechSpeed {
    static let usual = 320.0

    private static func steps(_ speed: Double?) -> Double {
        guard let speed, speed > 0 else { return 0 }
        return max(-1.5, min(1.5, (speed - usual) / 50))
    }

    static func knownShift(_ speed: Double?) -> Double {
        -0.04 * steps(speed)
    }

    static func clearShift(_ speed: Double?) -> Double {
        -0.10 * steps(speed)
    }

    static func text(_ speed: Double) -> String {
        let name: String = speed >= 360 ? "быстрая" : (speed <= 280 ? "медленная" : "обычная")
        return String(Int(speed.rounded())) + " мор/мин, " + name
    }
}

@available(iOS 16.0, *)
extension VideoLibraryStore {
    /// easy / normal / hard from the known words, the clear lines and the speech speed.
    nonisolated static func classify(known: Double, clear: Double, speed: Double?) -> Int {
        classify(known: known + SpeechSpeed.knownShift(speed), clear: clear + SpeechSpeed.clearShift(speed))
    }

    /// Seconds with a line on screen (overlapping lines once, a line at most 15 s).
    nonisolated static func speechSeconds(_ cues: [EmbeddedSubtitles.Cue]) -> Double {
        var seconds = 0.0
        var spanStart = 0.0
        var spanEnd = 0.0
        for cue in cues.sorted(by: { $0.start < $1.start }) where cue.end > cue.start {
            let end = min(cue.end, cue.start + 15)
            if cue.start > spanEnd {
                seconds += spanEnd - spanStart
                spanStart = cue.start
                spanEnd = end
            } else {
                spanEnd = max(spanEnd, end)
            }
        }
        return seconds + (spanEnd - spanStart)
    }
}

@available(iOS 16.0, *)
extension CatalogStore {
    /// easy / normal / hard of a title by the known words and Jiten's speech speed (the catalog has no lines).
    static func grade(known: Double, speed: Double?) -> Int {
        let share = known + SpeechSpeed.knownShift(speed)
        return share >= 0.90 ? 0 : (share >= 0.80 ? 1 : 2)
    }
}

/// The words imported from Anki decks: all of them ("known": not highlighted, marked as in Anki) and the words of
/// mature cards ("mature", an interval of 21 days or more: the analysis counts only these).
enum ImportedWords {
    private static func load() -> [String: Any] {
        guard let json = (try? Storage.stats.get())?.data(using: .utf8),
              let root = (try? JSONSerialization.jsonObject(with: json)) as? [String: Any] else { return [:] }
        return root
    }

    /// The words of mature cards; nil before a deck was imported with its schedule (1.76).
    static func mature() -> [String]? {
        load()["mature"] as? [String]
    }

    static func counts() -> (all: Int, mature: Int, scheduled: Bool) {
        let root = load()
        let mature = root["mature"] as? [String]
        return ((root["known"] as? [String])?.count ?? 0, mature?.count ?? 0, mature != nil)
    }

    /// Forgets the imported words; the statistics and the words added from Satori stay. No card counts in the
    /// analysis until a deck is imported again.
    static func forget() {
        var root = load()
        root["known"] = nil
        root["mature"] = [String]()
        root["matureUpdated"] = nil
        if root["days"] == nil {
            root["days"] = [String: Any]()
        }
        guard let out = try? JSONSerialization.data(withJSONObject: root),
              let text = String(data: out, encoding: .utf8) else { return }
        _ = try? Storage.stats.set(text)
    }
}

/// The calibration of "Мой уровень японского": words around the present boundaries (frequent words a little below
/// and above the number, JLPT words of the level and the next one) that only these settings decide; the answers move
/// the boundaries to where about half of the words are known.
@available(iOS 16.0, *)
enum Calibration {
    struct Word: Identifiable {
        let id: Int
        let word: String
        let reading: String
        /// written in kana as a rule (する, きっと): the reading is shown
        let kana: Bool
        /// the frequency band, nil for a JLPT word
        let band: Int?
        /// the level of a JLPT word
        let level: Int?

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

    struct LevelAnswer: Identifiable {
        var id: Int { level }
        let level: Int
        let known: Int
        let asked: Int
    }

    struct Result {
        let vocabulary: Int
        let level: Int
        let bands: [BandAnswer]
        let levels: [LevelAnswer]
        /// every band known by more than half: the boundary may be further
        let open: Bool
    }

    private static var frequency: [(rank: Int, word: String, reading: String, kana: Bool)] = []
    private static var jlpt: [(level: Int, word: String, reading: String)] = []

    private static func load() {
        guard frequency.isEmpty && jlpt.isEmpty else { return }
        for line in CalibrationData.text.split(separator: "\n") {
            let parts = line.split(separator: "\t", omittingEmptySubsequences: false).map { String($0) }
            guard parts.count >= 4, let number = Int(parts[1]) else { continue }
            if parts[0] == "j" {
                jlpt.append((level: number, word: parts[2], reading: parts[3]))
            } else {
                frequency.append((rank: number, word: parts[2], reading: parts[3], kana: parts[0] == "k"))
            }
        }
    }

    /// The word lists are in this build (they are made from the dictionaries of the release).
    @MainActor
    static var available: Bool {
        load()
        return !frequency.isEmpty
    }

    /// Bands of ranks from 0.3 to 3 times the number of frequent words.
    static func bands(around vocabulary: Int) -> [Band] {
        let steps: [Double] = [0.3, 0.5, 0.7, 0.85, 1.0, 1.2, 1.45, 1.75, 2.2, 3.0]
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

    /// Seven words of every band and of the two JLPT levels, in a random order. A frequency word is asked only when
    /// JLPT does not decide it, a JLPT word only when its frequency does not; never a card.
    static func pick(bands: [Band], level: Int, vocabulary: Int, index: KnownWordsIndex) -> [Word] {
        let judge = WordKnowledge(index: index, level: level, vocabulary: vocabulary)
        var result: [Word] = []
        func usable(_ word: String) -> Bool {
            if index.forms.contains(word) { return false }
            let tokens = autoreleasepool { NativeLookup.tokenize(word, charAt: 0).tokens }
            guard tokens.count == 1, let token = tokens.first, WordKnowledge.counted(token) else { return false }
            return judge.inDictionary(token)
        }
        for (number, band) in bands.enumerated() {
            var taken = 0
            for item in frequency.filter({ $0.rank >= band.from && $0.rank < band.to }).shuffled() where taken < 7 {
                let jlptLevel = HighlightData.jlptLevel(base: item.word, reading: item.reading)
                if jlptLevel > 0 && jlptLevel >= level { continue }
                let rank = HighlightData.bestRank(base: item.word, reading: item.reading, text: item.word) ?? item.rank
                guard rank >= band.from && rank < band.to, usable(item.word) else { continue }
                result.append(Word(id: result.count, word: item.word, reading: item.reading, kana: item.kana,
                                   band: number, level: nil))
                taken += 1
            }
        }
        for checked in [level, level - 1] where checked >= 1 && checked <= 5 {
            var taken = 0
            for item in jlpt.filter({ $0.level == checked }).shuffled() where taken < 7 {
                if let rank = HighlightData.bestRank(base: item.word, reading: item.reading, text: item.word),
                   rank <= vocabulary { continue }
                guard usable(item.word) else { continue }
                result.append(Word(id: result.count, word: item.word, reading: item.reading,
                                   kana: KnownWordsIndex.isKana(item.word), band: nil, level: checked))
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

    static func estimate(words: [Word], answers: [Int: Bool], bands: [Band], level: Int, vocabulary: Int) -> Result {
        var bandAnswers: [BandAnswer] = []
        for (number, band) in bands.enumerated() {
            let asked = words.filter { $0.band == number }
            guard !asked.isEmpty else { continue }
            let known = asked.filter { answers[$0.id] == true }.count
            bandAnswers.append(BandAnswer(id: number, band: band, known: known, asked: asked.count))
        }
        var levelAnswers: [LevelAnswer] = []
        for checked in [level, level - 1] where checked >= 1 && checked <= 5 {
            let asked = words.filter { $0.level == checked }
            guard !asked.isEmpty else { continue }
            levelAnswers.append(LevelAnswer(level: checked, known: asked.filter { answers[$0.id] == true }.count,
                                            asked: asked.count))
        }
        // the boundary: where the share of known words falls below one half (between the centers of two bands)
        var boundary = Double(vocabulary)
        var open = false
        if !bandAnswers.isEmpty {
            let fitted = decreasing(bandAnswers.map { (share: Double($0.known) / Double($0.asked), weight: Double($0.asked)) })
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
        }
        var suggested = level
        if let current = levelAnswers.first(where: { $0.level == level }), current.asked >= 4,
           Double(current.known) / Double(current.asked) < 0.6, level < 5 {
            suggested = level + 1
        } else if let harder = levelAnswers.first(where: { $0.level == level - 1 }), harder.asked >= 4,
                  Double(harder.known) / Double(harder.asked) >= 0.75 {
            suggested = level - 1
        }
        let rounded = max(300, Int((boundary / 100).rounded()) * 100)
        return Result(vocabulary: rounded, level: suggested, bands: bandAnswers, levels: levelAnswers, open: open)
    }
}

/// The calibration screen: about 75 words one by one, "know" or "don't know", then the new boundaries to apply.
@available(iOS 16.0, *)
struct CalibrationView: View {
    @AppStorage("ykUserLevel") private var userLevel = 5
    @AppStorage("ykVocabSure") private var vocabSure = 0
    @State private var words: [Calibration.Word] = []
    @State private var bands: [Calibration.Band] = []
    @State private var answers: [Int: Bool] = [:]
    @State private var position = 0
    @State private var loading = false
    @State private var result: Calibration.Result? = nil
    @State private var applied = false

    private var level: Int {
        (1 ... 5).contains(userLevel) ? userLevel : 5
    }

    private var vocabulary: Int {
        VideoLibraryStore.vocabulary(level: level)
    }

    var body: some View {
        Group {
            if let result {
                resultView(result)
            } else if loading {
                VStack(spacing: 12) {
                    ProgressView()
                    Text("Подбираю слова…").foregroundColor(.secondary)
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
        let now: String = "Сейчас знакомыми считаются слова JLPT до N" + String(level) + " и " + String(vocabulary)
            + " самых частых слов."
        return List {
            Section {
                Text(now)
                Text("Калибровка покажет около 75 слов вокруг этих границ: частые слова чуть реже и чуть чаще вашего числа и слова JLPT вашего и следующего уровня. Ваши зрелые карточки не показываются.")
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

    private func levelRow(_ item: Calibration.LevelAnswer) -> some View {
        HStack {
            Text("JLPT N" + String(item.level))
            Spacer()
            Text(String(item.known) + " из " + String(item.asked)).foregroundColor(.secondary)
        }
    }

    private func resultView(_ result: Calibration.Result) -> some View {
        let frequent: String = String(vocabulary) + " → " + String(result.vocabulary)
        let jlptLevels: String = "N" + String(level) + " → N" + String(result.level)
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
                Text(result.open
                     ? "Вы знаете больше половины слов даже в самой редкой группе: граница может быть дальше. Примените результат и пройдите калибровку ещё раз."
                     : "Граница — место в списке частотности, где вы знаете примерно половину слов: чаще неё слова в основном знакомы, реже — нет.")
            }
            Section {
                ForEach(result.bands) { item in
                    bandRow(item)
                }
                ForEach(result.levels) { item in
                    levelRow(item)
                }
            } header: {
                Text("Ответы")
            }
            Section {
                Button(applied ? "Применено" : "Применить") {
                    vocabSure = result.vocabulary
                    userLevel = result.level
                    applied = true
                }
                .disabled(applied)
                Button("Пройти ещё раз") {
                    self.result = nil
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
        answers[words[position].id] = known
        if position + 1 < words.count {
            position += 1
        } else {
            result = Calibration.estimate(words: words, answers: answers, bands: bands, level: level,
                                          vocabulary: vocabulary)
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
}
