
// MARK: - Satori v2.00: grammar decks N5–N1, reviews by FSRS

/// One sentence of a grammar point: the Japanese, its translation and the grammar in it ("|" between the pieces of a
/// split construction, e.g. ば|ほど).
struct GrammarExample: Codable, Hashable {
    let ja: String
    let ru: String
    let mark: String
}

/// A grammar point of a deck (res/grammar/n5.json … n1.json, written for Satori).
struct GrammarPoint: Codable, Identifiable, Hashable {
    let id: String
    let level: Int
    let pattern: String
    /// the meaning in a few words: the back of the card and the options of the level test
    let short: String
    let explanation: String
    var formation: String? = nil
    /// a regular expression that finds the construction in a line (the difficulty of the texts)
    var detect: String? = nil
    let examples: [GrammarExample]
}

/// The card of a point as FSRS sees it. New fields must be Optional: older files lack them.
struct GrammarCard: Codable {
    /// 0 new, 1 learning, 2 review, 3 relearning
    var state = 0
    var step = 0
    var stability = 0.0
    var difficulty = 0.0
    /// days, in review
    var interval = 0
    var due = Date.distantPast
    var last: Date? = nil
    var reps = 0
    var lapses = 0
    /// the example shown next time
    var example = 0
    /// answered right in the level test
    var tested: Bool? = nil
}

/// Progress of the grammar decks (Application Support/grammar.json). New fields must be Optional.
struct GrammarSave: Codable {
    var cards: [String: GrammarCard] = [:]
    /// levels whose test was passed: their grammar counts as known in the difficulty of the texts
    var passed: [Int] = []
    var newPerDay = 10
    /// the study day (it starts at 4:00) and the new cards begun on it, per level
    var day = ""
    var newToday: [String: Int] = [:]
    /// the last level test of each level, percent
    var tests: [String: Int] = [:]
}

enum GrammarFile {
    static var url: URL {
        FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("grammar.json")
    }

    static func read() -> GrammarSave {
        guard let data = try? Data(contentsOf: url) else { return GrammarSave() }
        if let saved = try? JSONDecoder().decode(GrammarSave.self, from: data) {
            return saved
        }
        // unreadable: put aside, so that an empty progress does not overwrite it
        let aside = url.deletingLastPathComponent().appendingPathComponent("grammar-unreadable.json")
        try? FileManager.default.removeItem(at: aside)
        try? FileManager.default.moveItem(at: url, to: aside)
        return GrammarSave()
    }

    static func write(_ save: GrammarSave) {
        guard let data = try? JSONEncoder().encode(save) else { return }
        try? FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        try? data.write(to: url, options: .atomic)
    }
}

/// The decks shipped with the app, read once.
enum GrammarLibrary {
    static let loaded: (points: [GrammarPoint], problems: [String]) = load()

    static var points: [GrammarPoint] {
        loaded.points
    }

    static let byId: [String: GrammarPoint] = {
        var map: [String: GrammarPoint] = [:]
        for point in loaded.points where map[point.id] == nil {
            map[point.id] = point
        }
        return map
    }()

    /// the compiled `detect` of each point
    static let detectors: [String: NSRegularExpression] = {
        var map: [String: NSRegularExpression] = [:]
        for point in loaded.points {
            guard let pattern = point.detect, let regex = try? NSRegularExpression(pattern: pattern) else { continue }
            map[point.id] = regex
        }
        return map
    }()

    static func level(_ level: Int) -> [GrammarPoint] {
        points.filter { $0.level == level }
    }

    private static func load() -> (points: [GrammarPoint], problems: [String]) {
        var points: [GrammarPoint] = []
        var problems: [String] = []
        for level in [5, 4, 3, 2, 1] {
            let name = "n" + String(level)
            guard let url = Bundle.main.url(forResource: name, withExtension: "json", subdirectory: "res/grammar") else {
                problems.append(name + ".json: нет в приложении")
                continue
            }
            do {
                let data = try Data(contentsOf: url)
                points += try JSONDecoder().decode([GrammarPoint].self, from: data)
            } catch {
                problems.append(name + ".json: " + String(describing: error))
            }
        }
        return (points, problems)
    }
}

/// FSRS-5 with its default parameters (the formulas of ts-fsrs), desired retention 90%.
enum FSRS {
    static let w: [Double] = [0.40255, 1.18385, 3.173, 15.69105, 7.1949, 0.5345, 1.4604, 0.0046, 1.54575, 0.1192,
                              1.01925, 1.9395, 0.11, 0.29605, 2.2698, 0.2315, 2.9898, 0.51655, 0.6621]
    static let decay = -0.5
    static let factor = 19.0 / 81.0
    static let retention = 0.9

    static func retrievability(days: Double, stability: Double) -> Double {
        pow(1 + factor * days / stability, decay)
    }

    static func initialStability(_ grade: Int) -> Double {
        max(w[grade - 1], 0.1)
    }

    static func initialDifficulty(_ grade: Int) -> Double {
        let value: Double = w[4] - exp(Double(grade - 1) * w[5]) + 1
        return min(max(value, 1), 10)
    }

    static func nextDifficulty(_ d: Double, _ grade: Int) -> Double {
        let delta: Double = -w[6] * Double(grade - 3)
        let damped: Double = d + delta * (10 - d) / 9
        let reverted: Double = w[7] * initialDifficulty(4) + (1 - w[7]) * damped
        return min(max(reverted, 1), 10)
    }

    static func recall(_ d: Double, _ s: Double, _ r: Double, _ grade: Int) -> Double {
        let hard: Double = grade == 2 ? w[15] : 1
        let easy: Double = grade == 4 ? w[16] : 1
        let base: Double = exp(w[8]) * (11 - d)
        let decayed: Double = pow(s, -w[9])
        let surprise: Double = exp((1 - r) * w[10]) - 1
        return s * (1 + base * decayed * surprise * hard * easy)
    }

    static func forget(_ d: Double, _ s: Double, _ r: Double) -> Double {
        let first: Double = w[11] * pow(d, -w[12])
        let second: Double = pow(s + 1, w[13]) - 1
        let third: Double = exp((1 - r) * w[14])
        let ceiling: Double = s / exp(w[17] * w[18])
        return max(0.01, min(first * second * third, ceiling))
    }

    /// a second answer on the same day
    static func shortTerm(_ s: Double, _ grade: Int) -> Double {
        let power: Double = w[17] * (Double(grade) - 3 + w[18])
        return max(0.01, s * exp(power))
    }

    /// days until recall falls to the retention (with these constants: the stability itself)
    static func interval(_ s: Double) -> Int {
        let days: Double = s / factor * (pow(retention, 1 / decay) - 1)
        return min(max(Int(days.rounded()), 1), 36_500)
    }

    /// Stability and difficulty after an answer (grade 1…4).
    static func memory(_ card: GrammarCard, grade: Int, now: Date) -> (stability: Double, difficulty: Double) {
        if card.state == 0 || card.stability <= 0 {
            return (initialStability(grade), initialDifficulty(grade))
        }
        let difficulty = nextDifficulty(card.difficulty, grade)
        let seconds = card.last.map { now.timeIntervalSince($0) } ?? 0
        let days = (seconds / 86_400).rounded(.down)
        if days < 1 {
            return (shortTerm(card.stability, grade), difficulty)
        }
        let r = retrievability(days: days, stability: card.stability)
        if grade == 1 {
            return (forget(card.difficulty, card.stability, r), difficulty)
        }
        return (recall(card.difficulty, card.stability, r, grade), difficulty)
    }
}

/// Anki's steps around FSRS: learning 1 and 10 minutes, relearning 10 minutes, then days from the stability.
enum GrammarScheduler {
    static let learning: [Double] = [1, 10]
    static let relearning: [Double] = [10]

    /// The card after each answer: again, hard, good, easy.
    static func outcomes(_ card: GrammarCard, now: Date) -> [GrammarCard] {
        var result: [GrammarCard] = []
        for grade in 1 ... 4 {
            result.append(answer(card, grade: grade, now: now))
        }
        // days in review keep their order: hard ≤ good < easy
        if result[1].state == 2 && result[2].state == 2 && result[1].interval > result[2].interval {
            schedule(&result[1], days: result[2].interval, now: now)
        }
        if result[1].state == 2 && result[2].state == 2 && result[2].interval <= result[1].interval {
            schedule(&result[2], days: result[1].interval + 1, now: now)
        }
        if result[2].state == 2 && result[3].state == 2 && result[3].interval <= result[2].interval {
            schedule(&result[3], days: result[2].interval + 1, now: now)
        }
        return result
    }

    static func labels(_ card: GrammarCard, now: Date) -> [String] {
        outcomes(card, now: now).map { label($0.due.timeIntervalSince(now)) }
    }

    private static func schedule(_ card: inout GrammarCard, days: Int, now: Date) {
        card.state = 2
        card.step = 0
        card.interval = max(1, days)
        card.due = now.addingTimeInterval(Double(card.interval) * 86_400)
    }

    private static func learn(_ card: inout GrammarCard, state: Int, step: Int, minutes: Double, now: Date) {
        card.state = state
        card.step = step
        card.interval = 0
        card.due = now.addingTimeInterval(minutes * 60)
    }

    private static func answer(_ card: GrammarCard, grade: Int, now: Date) -> GrammarCard {
        var next = card
        let memory = FSRS.memory(card, grade: grade, now: now)
        next.stability = memory.stability
        next.difficulty = memory.difficulty
        next.last = now
        next.reps += 1
        switch card.state {
        case 2:
            if grade == 1 {
                next.lapses += 1
                next.tested = nil
                learn(&next, state: 3, step: 0, minutes: relearning[0], now: now)
            } else {
                schedule(&next, days: FSRS.interval(memory.stability), now: now)
            }
        case 3:
            if grade == 1 {
                learn(&next, state: 3, step: 0, minutes: relearning[0], now: now)
            } else if grade == 2 {
                learn(&next, state: 3, step: card.step, minutes: relearning[0] * 1.5, now: now)
            } else {
                schedule(&next, days: FSRS.interval(memory.stability), now: now)
            }
        default:
            // new and learning: the steps, then days
            let step = card.state == 0 ? 0 : min(card.step, learning.count - 1)
            if grade == 1 {
                learn(&next, state: 1, step: 0, minutes: learning[0], now: now)
            } else if grade == 2 {
                let minutes: Double = step == 0 && learning.count > 1 ? (learning[0] + learning[1]) / 2 : learning[step]
                learn(&next, state: 1, step: step, minutes: minutes, now: now)
            } else if grade == 3 && step + 1 < learning.count {
                learn(&next, state: 1, step: step + 1, minutes: learning[step + 1], now: now)
            } else {
                schedule(&next, days: FSRS.interval(memory.stability), now: now)
            }
        }
        return next
    }

    /// "1 мин", "6 мин", "4 д", "1,5 мес", "1,2 г"
    static func label(_ seconds: Double) -> String {
        let minutes = seconds / 60
        if minutes < 59.5 {
            return String(max(1, Int(minutes.rounded()))) + " мин"
        }
        let hours = minutes / 60
        if hours < 23.5 {
            return String(Int(hours.rounded())) + " ч"
        }
        let days = hours / 24
        if days < 30 {
            return String(Int(days.rounded())) + " д"
        }
        if days < 365 {
            return tenths(days / 30) + " мес"
        }
        return tenths(days / 365) + " г"
    }

    private static func tenths(_ value: Double) -> String {
        let rounded = (value * 10).rounded() / 10
        if rounded == rounded.rounded() {
            return String(Int(rounded))
        }
        return String(format: "%.1f", rounded).replacingOccurrences(of: ".", with: ",")
    }

    #if DEBUG
    /// A new card: again 1 min, hard 6 min, good 10 min, easy 16 days; good twice graduates it.
    static func selfCheck() {
        let now = Date()
        let first = outcomes(GrammarCard(), now: now)
        assert(label(first[0].due.timeIntervalSince(now)) == "1 мин")
        assert(label(first[1].due.timeIntervalSince(now)) == "6 мин")
        assert(label(first[2].due.timeIntervalSince(now)) == "10 мин")
        assert(first[3].state == 2 && first[3].interval == 16)
        let graduated = outcomes(first[2], now: now.addingTimeInterval(600))[2]
        assert(graduated.state == 2 && graduated.interval >= 3)
    }
    #endif
}

/// The grammar the user does not know yet, for the difficulty of episodes and novels. Thread-safe: the analyses run
/// in the background.
enum GrammarDemand {
    private static let lock = NSLock()
    private static var saved: GrammarSave? = nil

    static func remember(_ save: GrammarSave) {
        lock.lock()
        saved = save
        lock.unlock()
    }

    /// Known: a level up to the JLPT level of the settings, a level whose test was passed, a point answered right in
    /// a test, a mature card (stability from 21 days).
    static func known(_ point: GrammarPoint, in save: GrammarSave, level: Int) -> Bool {
        if point.level >= level || save.passed.contains(point.level) {
            return true
        }
        guard let card = save.cards[point.id] else { return false }
        return card.tested == true || (card.state == 2 && card.stability >= 21)
    }

    /// The JLPT level of the settings (ykUserLevel), read here: VideoLibraryStore lives on the main actor.
    static var userLevel: Int {
        let stored = UserDefaults.standard.integer(forKey: "ykUserLevel")
        return (1 ... 5).contains(stored) ? stored : 5
    }

    /// The unknown points that can be found in a line, and a stamp that changes with that set (the saved analyses
    /// are counted again when it changes).
    static func unknown() -> (detectors: [(id: String, regex: NSRegularExpression)], stamp: Int) {
        lock.lock()
        if saved == nil {
            saved = GrammarFile.read()
        }
        let save = saved ?? GrammarSave()
        lock.unlock()
        let level = userLevel
        var list: [(id: String, regex: NSRegularExpression)] = []
        var stamp: UInt64 = 14_695_981_039_346_656_037
        for (index, point) in GrammarLibrary.points.enumerated() {
            guard let regex = GrammarLibrary.detectors[point.id], !known(point, in: save, level: level) else { continue }
            list.append((id: point.id, regex: regex))
            stamp = (stamp ^ UInt64(index + 1)) &* 1_099_511_628_211
        }
        return (list, Int(stamp % 9_973))
    }

    /// The unknown grammar of an analysis, the most frequent first.
    static func list(_ counts: [String: Int]) -> [GrammarCount] {
        var result: [GrammarCount] = []
        for (id, count) in counts {
            if let point = GrammarLibrary.byId[id] {
                result.append(GrammarCount(point: point, count: count))
            }
        }
        result.sort { first, second in
            first.count != second.count ? first.count > second.count : first.point.id < second.point.id
        }
        return result
    }
}

struct GrammarCount: Identifiable {
    let point: GrammarPoint
    let count: Int

    var id: String {
        point.id
    }
}

/// The grammar decks: the cards, the daily limit of new ones, the tests.
@MainActor
final class GrammarStore: ObservableObject {
    static let shared = GrammarStore()

    @Published private(set) var save: GrammarSave
    @Published private(set) var canUndo = false
    /// the card before the last answer, for «Отменить»
    private var undoStep: (id: String, card: GrammarCard?, newToday: [String: Int], day: String)? = nil

    init() {
        save = GrammarFile.read()
        GrammarDemand.remember(save)
        #if DEBUG
        GrammarScheduler.selfCheck()
        #endif
    }

    /// the study day: it starts at 4:00, as in Anki
    static func studyDay(_ date: Date) -> String {
        let parts = Calendar.current.dateComponents([.year, .month, .day], from: date.addingTimeInterval(-4 * 3600))
        return String(format: "%d-%d-%d", parts.year ?? 0, parts.month ?? 0, parts.day ?? 0)
    }

    /// reviews due before it are due today
    static func dayEnd(_ date: Date) -> Date {
        Calendar.current.startOfDay(for: date.addingTimeInterval(-4 * 3600)).addingTimeInterval(28 * 3600)
    }

    func card(_ id: String) -> GrammarCard {
        save.cards[id] ?? GrammarCard()
    }

    func example(_ point: GrammarPoint) -> GrammarExample? {
        guard !point.examples.isEmpty else { return nil }
        return point.examples[card(point.id).example % point.examples.count]
    }

    func newLeft(_ level: Int, now: Date = Date()) -> Int {
        let begun = save.day == GrammarStore.studyDay(now) ? (save.newToday[String(level)] ?? 0) : 0
        return max(0, save.newPerDay - begun)
    }

    func counts(level: Int, now: Date = Date()) -> (new: Int, learning: Int, review: Int) {
        let end = GrammarStore.dayEnd(now)
        var unseen = 0
        var learning = 0
        var review = 0
        for point in GrammarLibrary.level(level) {
            let card = self.card(point.id)
            if card.state == 0 {
                unseen += 1
            } else if card.due < end {
                if card.state == 2 {
                    review += 1
                } else {
                    learning += 1
                }
            }
        }
        return (min(unseen, newLeft(level, now: now)), learning, review)
    }

    /// Anki's order: learning cards that are due, reviews of today, new cards up to the limit, then learning cards
    /// due in the next 20 minutes.
    func next(level: Int, now: Date = Date()) -> GrammarPoint? {
        let end = GrammarStore.dayEnd(now)
        var learning: GrammarPoint? = nil
        var learningDue = Date.distantFuture
        var review: GrammarPoint? = nil
        var reviewDue = Date.distantFuture
        var fresh: GrammarPoint? = nil
        for point in GrammarLibrary.level(level) where !point.examples.isEmpty {
            let card = self.card(point.id)
            switch card.state {
            case 0:
                if fresh == nil {
                    fresh = point
                }
            case 2:
                if card.due < end && card.due < reviewDue {
                    review = point
                    reviewDue = card.due
                }
            default:
                if card.due < learningDue {
                    learning = point
                    learningDue = card.due
                }
            }
        }
        if let learning, learningDue <= now {
            return learning
        }
        if let review {
            return review
        }
        if let fresh, newLeft(level, now: now) > 0 {
            return fresh
        }
        if let learning, learningDue <= now.addingTimeInterval(20 * 60) {
            return learning
        }
        return nil
    }

    /// When the next learning card of the level comes back today.
    func laterToday(level: Int, now: Date = Date()) -> Date? {
        let end = GrammarStore.dayEnd(now)
        var soonest: Date? = nil
        for point in GrammarLibrary.level(level) {
            let card = self.card(point.id)
            guard card.state == 1 || card.state == 3, card.due < end else { continue }
            if let current = soonest, current <= card.due {
                continue
            }
            soonest = card.due
        }
        return soonest
    }

    func answer(_ point: GrammarPoint, grade: Int, now: Date = Date()) {
        let today = GrammarStore.studyDay(now)
        if save.day != today {
            save.day = today
            save.newToday = [:]
        }
        let old = save.cards[point.id]
        undoStep = (id: point.id, card: old, newToday: save.newToday, day: save.day)
        var card = old ?? GrammarCard()
        if card.state == 0 {
            save.newToday[String(point.level), default: 0] += 1
        }
        card = GrammarScheduler.outcomes(card, now: now)[min(max(grade, 1), 4) - 1]
        card.example = (card.example + 1) % max(point.examples.count, 1)
        save.cards[point.id] = card
        canUndo = true
        persist()
    }

    /// Takes the last answer back; the point to show again.
    func undo() -> GrammarPoint? {
        guard let step = undoStep, let point = GrammarLibrary.byId[step.id] else { return nil }
        save.cards[step.id] = step.card
        save.newToday = step.newToday
        save.day = step.day
        undoStep = nil
        canUndo = false
        persist()
        return point
    }

    func setNewPerDay(_ value: Int) {
        save.newPerDay = min(max(value, 0), 100)
        persist()
    }

    /// The end of a level test: the points answered right are known (in review, checked by FSRS in 5–15 days); the
    /// level is passed from 85%.
    func finishTest(level: Int, right: [String], missed: [String], percent: Int, now: Date = Date()) {
        for id in right {
            var card = self.card(id)
            card.tested = true
            if card.state == 0 {
                card.state = 2
                card.stability = 10
                card.difficulty = FSRS.initialDifficulty(3)
                card.last = now
                card.interval = Int.random(in: 5 ... 15)
                card.due = now.addingTimeInterval(Double(card.interval) * 86_400)
            }
            save.cards[id] = card
        }
        for id in missed {
            if var card = save.cards[id] {
                card.tested = nil
                save.cards[id] = card
            }
        }
        save.tests[String(level)] = percent
        save.passed.removeAll { $0 == level }
        if percent >= 85 {
            save.passed.append(level)
        }
        undoStep = nil
        canUndo = false
        persist()
    }

    func status(_ point: GrammarPoint, now: Date = Date()) -> String {
        let card = self.card(point.id)
        switch card.state {
        case 0:
            return "новая"
        case 2:
            let test = card.tested == true ? " · тест" : ""
            if card.due <= now {
                return "повторить" + test
            }
            return "через " + GrammarScheduler.label(card.due.timeIntervalSince(now)) + test
        default:
            return "изучаю"
        }
    }

    private func persist() {
        GrammarFile.write(save)
        GrammarDemand.remember(save)
    }
}

/// The sentences are read by the voice of the dictionary settings (tts.voice), else by the best Japanese voice.
enum GrammarVoice {
    static func speak(_ text: String) {
        guard !text.isEmpty else { return }
        if synthesizer.isSpeaking {
            synthesizer.stopSpeaking(at: .immediate)
        }
        try? ttsSpeak(voice: chosen(), text: text)
    }

    private static func chosen() -> TTSVoice? {
        if let json = try? Storage.config.get(), let data = json.data(using: .utf8),
           let config = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any],
           let voice = config["tts.voice"] as? [String: Any], let id = voice["id"] as? String {
            return TTSVoice(id: id, name: "", quality: 0)
        }
        return japaneseTtsVoices().max { $0.quality < $1.quality }
    }
}

enum GrammarText {
    /// The sentence with its grammar bold and in the colour (pieces split by "|", found in order).
    static func marked(_ text: String, _ mark: String, _ color: Color) -> AttributedString {
        var result = AttributedString(text)
        var from = result.startIndex
        for piece in mark.split(separator: "|") {
            guard let range = result[from...].range(of: piece) else { continue }
            result[range][AttributeScopes.SwiftUIAttributes.ForegroundColorAttribute.self] = color
            result[range].inlinePresentationIntent = .stronglyEmphasized
            from = range.upperBound
        }
        return result
    }
}

/// Opens the grammar decks over the dictionary tab (the page asks with "openGrammar").
@MainActor
final class GrammarPresenter: ObservableObject {
    static let shared = GrammarPresenter()
    @Published var open = false
}

/// The decks N5–N1 with today's counts, as in Anki: new (blue), learning (red), to review (green).
@available(iOS 16.0, *)
struct GrammarHome: View {
    @ObservedObject private var store = GrammarStore.shared
    @Environment(\.dismiss) private var dismiss
    @AppStorage("ykGrammarAutoPlay") private var autoPlay = true
    @AppStorage(AppAccent.key) private var accent = AppAccent.standard

    var body: some View {
        NavigationStack {
            List {
                Section {
                    ForEach([5, 4, 3, 2, 1], id: \.self) { level in
                        NavigationLink {
                            GrammarDeckView(level: level)
                        } label: {
                            deckRow(level)
                        }
                    }
                } footer: {
                    Text(GrammarHome.about)
                }
                Section {
                    Stepper(value: Binding(get: { store.save.newPerDay }, set: { store.setNewPerDay($0) }),
                            in: 0 ... 50, step: 5) {
                        Text("Новых в день: " + String(store.save.newPerDay))
                    }
                    Toggle("Озвучивать предложение сразу", isOn: $autoPlay)
                } header: {
                    Text("Настройки")
                } footer: {
                    Text("Лимит новых — на каждую колоду. День начинается в 4:00. Голос — из настроек озвучки словаря.")
                }
                if !GrammarLibrary.loaded.problems.isEmpty {
                    Section {
                        ForEach(GrammarLibrary.loaded.problems, id: \.self) { problem in
                            Text(problem)
                                .font(.caption)
                        }
                    } header: {
                        Text("Колоды не прочитаны")
                    }
                }
            }
            .navigationTitle("Грамматика")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Закрыть") {
                        dismiss()
                    }
                }
            }
            .satoriBackdrop()
        }
        .tint(AppAccent.color(accent))
        .preferredColorScheme(.dark)
    }

    static let about: String = "Колода — грамматика уровня JLPT: конструкция и предложение, на обороте значение, "
        + "перевод и пояснение. Повторение по FSRS, как в Anki: синие — новые, красные — изучаемые, зелёные — к повторению."

    private func deckRow(_ level: Int) -> some View {
        let counts = store.counts(level: level)
        var note = "единиц: " + String(GrammarLibrary.level(level).count)
        if let test = store.save.tests[String(level)] {
            note += " · тест " + String(test) + "%"
        }
        return HStack {
            VStack(alignment: .leading, spacing: 3) {
                Text("N" + String(level))
                    .font(.title2.weight(.bold))
                Text(note)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            Spacer()
            HStack(spacing: 10) {
                Text(String(counts.new))
                    .foregroundColor(.blue)
                Text(String(counts.learning))
                    .foregroundColor(.red)
                Text(String(counts.review))
                    .foregroundColor(.green)
            }
            .font(.headline.monospacedDigit())
        }
        .padding(.vertical, 4)
    }
}

/// A deck: today's counts, «Учить», the level test and the points.
@available(iOS 16.0, *)
struct GrammarDeckView: View {
    let level: Int
    @ObservedObject private var store = GrammarStore.shared

    var body: some View {
        let counts = store.counts(level: level)
        let points = GrammarLibrary.level(level)
        List {
            Section {
                HStack {
                    tally("Новые", counts.new, .blue)
                    tally("Изучаю", counts.learning, .red)
                    tally("Повторить", counts.review, .green)
                }
                NavigationLink {
                    GrammarReviewView(level: level)
                } label: {
                    Label("Учить", systemImage: "rectangle.stack.fill")
                }
                .disabled(points.isEmpty)
                NavigationLink {
                    GrammarTestView(level: level)
                } label: {
                    Label("Тест уровня", systemImage: "checkmark.seal")
                }
                .disabled(points.isEmpty)
            } footer: {
                Text(testNote())
            }
            Section {
                ForEach(points) { point in
                    NavigationLink {
                        GrammarPointView(point: point)
                    } label: {
                        HStack {
                            VStack(alignment: .leading, spacing: 2) {
                                Text(point.pattern)
                                Text(point.short)
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
                            Spacer()
                            Text(store.status(point))
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                    }
                }
            } header: {
                Text("Единицы: " + String(points.count))
            }
        }
        .navigationTitle("N" + String(level))
        .satoriBackdrop()
    }

    private func tally(_ title: String, _ value: Int, _ color: Color) -> some View {
        VStack(spacing: 2) {
            Text(String(value))
                .font(.title2.weight(.bold))
                .foregroundColor(color)
            Text(title)
                .font(.caption)
                .foregroundColor(.secondary)
        }
        .frame(maxWidth: .infinity)
    }

    private func testNote() -> String {
        let note: String = "Тест уровня: 20 вопросов (30, если результат на границе), пара минут. От 85% грамматика "
            + "уровня считается знакомой в оценке сложности серий и ранобэ."
        guard let last = store.save.tests[String(level)] else { return note }
        let passed: String = store.save.passed.contains(level) ? " — пройден" : ""
        let result: String = "Последний тест: " + String(last) + "%"
        return result + passed + ". " + note
    }
}

/// Anki's review: the point and a sentence, «Показать ответ», then the meaning, the translation, the explanation and
/// four answers with their intervals.
@available(iOS 16.0, *)
struct GrammarReviewView: View {
    let level: Int
    @ObservedObject private var store = GrammarStore.shared
    @AppStorage("ykGrammarAutoPlay") private var autoPlay = true
    @AppStorage(AppAccent.key) private var accent = AppAccent.standard
    @State private var current: GrammarPoint? = nil
    @State private var shown = false
    @State private var started = false
    @State private var lookup: LineLookup? = nil

    var body: some View {
        VStack(spacing: 0) {
            if let point = current {
                countsBar
                ScrollView {
                    face(point)
                }
                .contentShape(Rectangle())
                .onTapGesture {
                    if !shown {
                        shown = true
                    }
                }
                answers(point)
            } else if started {
                done
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background {
            SatoriBackdrop()
        }
        .navigationTitle("N" + String(level))
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .primaryAction) {
                Button {
                    if let point = store.undo() {
                        show(point)
                    }
                } label: {
                    Image(systemName: "arrow.uturn.backward")
                }
                .disabled(!store.canUndo)
            }
        }
        .sheet(item: $lookup) { item in
            WordLookupSheet(text: item.text, charAt: item.charAt)
        }
        .onAppear {
            if !started {
                started = true
                advance()
            }
        }
    }

    private var countsBar: some View {
        let counts = store.counts(level: level)
        return HStack(spacing: 14) {
            Text(String(counts.new))
                .foregroundColor(.blue)
            Text(String(counts.learning))
                .foregroundColor(.red)
            Text(String(counts.review))
                .foregroundColor(.green)
        }
        .font(.subheadline.monospacedDigit().weight(.semibold))
        .padding(.vertical, 8)
    }

    private func face(_ point: GrammarPoint) -> some View {
        let example = store.example(point)
        let tint = AppAccent.color(accent)
        return VStack(spacing: 18) {
            Text(point.pattern)
                .font(.system(size: 32, weight: .bold))
                .multilineTextAlignment(.center)
            if let example {
                sentence(example, tint: tint)
            }
            if shown {
                Divider()
                Text(point.short)
                    .font(.title3.weight(.semibold))
                    .foregroundColor(tint)
                    .multilineTextAlignment(.center)
                if let example {
                    Text(example.ru)
                        .multilineTextAlignment(.center)
                }
                Text(point.explanation)
                    .font(.callout)
                    .foregroundColor(.secondary)
                    .frame(maxWidth: .infinity, alignment: .leading)
                if let formation = point.formation {
                    Text(formation)
                        .font(.callout.monospaced())
                        .foregroundColor(.secondary)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
            }
        }
        .padding(22)
        .frame(maxWidth: .infinity)
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 24, style: .continuous))
        .padding(16)
    }

    private func sentence(_ example: GrammarExample, tint: Color) -> some View {
        VStack(spacing: 10) {
            Text(GrammarText.marked(example.ja, example.mark, tint))
                .font(.system(size: 24))
                .multilineTextAlignment(.center)
            HStack(spacing: 24) {
                Button {
                    GrammarVoice.speak(example.ja)
                } label: {
                    Image(systemName: "speaker.wave.2.fill")
                }
                Button {
                    lookup = LineLookup(text: example.ja, charAt: 0)
                } label: {
                    Image(systemName: "character.book.closed")
                }
            }
            .font(.title3)
            .buttonStyle(.borderless)
        }
    }

    private func answers(_ point: GrammarPoint) -> some View {
        Group {
            if shown {
                let labels = GrammarScheduler.labels(store.card(point.id), now: Date())
                HStack(spacing: 8) {
                    grade("Снова", labels[0], .red, 1, point)
                    grade("Трудно", labels[1], .orange, 2, point)
                    grade("Хорошо", labels[2], .green, 3, point)
                    grade("Легко", labels[3], .blue, 4, point)
                }
            } else {
                Button {
                    shown = true
                } label: {
                    Text("Показать ответ")
                        .font(.headline)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 8)
                }
                .buttonStyle(.borderedProminent)
            }
        }
        .padding(.horizontal, 16)
        .padding(.bottom, 12)
    }

    private func grade(_ title: String, _ interval: String, _ color: Color, _ value: Int, _ point: GrammarPoint) -> some View {
        Button {
            store.answer(point, grade: value)
            advance()
        } label: {
            VStack(spacing: 3) {
                Text(interval)
                    .font(.caption2)
                    .foregroundColor(.secondary)
                Text(title)
                    .font(.subheadline.weight(.semibold))
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 6)
        }
        .buttonStyle(.bordered)
        .tint(color)
    }

    private var done: some View {
        VStack(spacing: 14) {
            Image(systemName: "checkmark.seal.fill")
                .font(.system(size: 54))
                .foregroundColor(.green)
            Text("На сегодня всё")
                .font(.title2.weight(.bold))
            if let later = store.laterToday(level: level) {
                Text("Изучаемые карточки вернутся через " + GrammarScheduler.label(max(later.timeIntervalSinceNow, 60)))
                    .foregroundColor(.secondary)
                Button("Проверить ещё раз") {
                    advance()
                }
                .buttonStyle(.bordered)
            } else {
                Text("Новые карточки — завтра: " + String(store.save.newPerDay) + " в день.")
                    .foregroundColor(.secondary)
            }
        }
        .multilineTextAlignment(.center)
        .padding(32)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private func advance() {
        if let point = store.next(level: level) {
            show(point)
        } else {
            current = nil
            shown = false
        }
    }

    private func show(_ point: GrammarPoint) {
        current = point
        shown = false
        if autoPlay, let example = store.example(point) {
            GrammarVoice.speak(example.ja)
        }
    }
}

struct GrammarQuestion {
    let point: GrammarPoint
    let example: GrammarExample
    let options: [String]
    let answer: Int
}

/// The level test: the meaning of the marked grammar in a sentence, four options or «Не знаю». 20 questions, 30 when
/// the result is near a line; guesses are taken out (a wrong answer costs a third of a right one).
@available(iOS 16.0, *)
struct GrammarTestView: View {
    let level: Int
    @ObservedObject private var store = GrammarStore.shared
    @AppStorage(AppAccent.key) private var accent = AppAccent.standard
    @Environment(\.dismiss) private var dismiss
    @State private var questions: [GrammarQuestion] = []
    @State private var started = false
    @State private var index = 0
    @State private var chosen: Int? = nil
    @State private var right: [String] = []
    @State private var missed: [String] = []
    @State private var wrong = 0
    @State private var extended = false
    @State private var percent: Int? = nil

    var body: some View {
        Group {
            if let percent {
                result(percent)
            } else if index < questions.count {
                question(questions[index])
            } else if started {
                Text("В колоде пока нет единиц.")
                    .foregroundColor(.secondary)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background {
            SatoriBackdrop()
        }
        .navigationTitle("Тест N" + String(level))
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            if !started {
                started = true
                questions = GrammarTestView.make(level: level, count: 20, excluding: [])
            }
        }
    }

    static func make(level: Int, count: Int, excluding: Set<String>) -> [GrammarQuestion] {
        let all = GrammarLibrary.level(level)
        var result: [GrammarQuestion] = []
        for point in all.shuffled() where !excluding.contains(point.id) {
            guard let example = point.examples.randomElement() else { continue }
            var options: [String] = [point.short]
            for other in all.shuffled() where !options.contains(other.short) {
                options.append(other.short)
                if options.count == 4 {
                    break
                }
            }
            options.shuffle()
            let answer = options.firstIndex(of: point.short) ?? 0
            result.append(GrammarQuestion(point: point, example: example, options: options, answer: answer))
            if result.count == count {
                break
            }
        }
        return result
    }

    static func score(right: Int, wrong: Int, asked: Int) -> Double {
        guard asked > 0 else { return 0 }
        return max(0, Double(right) - Double(wrong) / 3) / Double(asked)
    }

    private func question(_ item: GrammarQuestion) -> some View {
        let tint = AppAccent.color(accent)
        return ScrollView {
            VStack(spacing: 16) {
                ProgressView(value: Double(index), total: Double(max(questions.count, 1)))
                Text(String(format: "Вопрос %d из %d", index + 1, questions.count))
                    .font(.caption)
                    .foregroundColor(.secondary)
                VStack(spacing: 10) {
                    Text(GrammarText.marked(item.example.ja, item.example.mark, tint))
                        .font(.system(size: 24))
                        .multilineTextAlignment(.center)
                    Button {
                        GrammarVoice.speak(item.example.ja)
                    } label: {
                        Image(systemName: "speaker.wave.2.fill")
                            .font(.title3)
                    }
                    .buttonStyle(.borderless)
                    if chosen != nil {
                        Text(item.point.pattern + " — " + item.example.ru)
                            .font(.callout)
                            .foregroundColor(.secondary)
                            .multilineTextAlignment(.center)
                    }
                }
                .padding(20)
                .frame(maxWidth: .infinity)
                .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 22, style: .continuous))
                Text("Что значит выделенное?")
                    .font(.headline)
                ForEach(Array(item.options.enumerated()), id: \.offset) { pair in
                    option(pair.element, pair.offset, item)
                }
                Button("Не знаю") {
                    choose(-1, item)
                }
                .disabled(chosen != nil)
                if let picked = chosen, picked != item.answer {
                    Button {
                        next()
                    } label: {
                        Text("Дальше")
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 6)
                    }
                    .buttonStyle(.borderedProminent)
                }
            }
            .padding(16)
        }
    }

    private func option(_ text: String, _ number: Int, _ item: GrammarQuestion) -> some View {
        let color: Color
        if chosen == nil {
            color = AppAccent.color(accent)
        } else if number == item.answer {
            color = .green
        } else if number == chosen {
            color = .red
        } else {
            color = .gray
        }
        return Button {
            choose(number, item)
        } label: {
            Text(text)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.vertical, 6)
        }
        .buttonStyle(.bordered)
        .tint(color)
    }

    private func choose(_ number: Int, _ item: GrammarQuestion) {
        guard chosen == nil else { return }
        chosen = number
        if number == item.answer {
            right.append(item.point.id)
            let at = index
            Task { @MainActor in
                try? await Task.sleep(nanoseconds: 700_000_000)
                if index == at && chosen != nil {
                    next()
                }
            }
        } else {
            if number >= 0 {
                wrong += 1
            }
            missed.append(item.point.id)
        }
    }

    private func next() {
        chosen = nil
        index += 1
        guard index >= questions.count else { return }
        let score = GrammarTestView.score(right: right.count, wrong: wrong, asked: questions.count)
        if !extended && score >= 0.6 && score < 0.85 {
            extended = true
            var seen = Set<String>()
            for item in questions {
                seen.insert(item.point.id)
            }
            let more = GrammarTestView.make(level: level, count: 10, excluding: seen)
            if !more.isEmpty {
                questions += more
                return
            }
        }
        let value = Int((score * 100).rounded())
        store.finishTest(level: level, right: right, missed: missed, percent: value)
        percent = value
    }

    private func summary() -> String {
        let count: String = String(format: "Верно: %d из %d. ", right.count, questions.count)
        let rules: String = "Угаданное вычитается: неверный ответ стоит трети верного, «Не знаю» — ничего. "
        let later: String = "Отвеченное верно не придёт новыми карточками: FSRS проверит его через 5–15 дней."
        return count + rules + later
    }

    private func result(_ percent: Int) -> some View {
        let verdict: String
        if percent >= 85 {
            verdict = "Грамматику N" + String(level) + " вы знаете: в оценке сложности она теперь знакомая."
        } else if percent >= 60 {
            verdict = "Почти: пройдите пропущенное в колоде N" + String(level) + "."
        } else {
            verdict = "Стоит пройти колоду N" + String(level) + "."
        }
        let missedPoints = missed.compactMap { GrammarLibrary.byId[$0] }
        return List {
            Section {
                VStack(spacing: 8) {
                    Text(String(percent) + "%")
                        .font(.system(size: 54, weight: .bold))
                    Text(verdict)
                        .multilineTextAlignment(.center)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 10)
            } footer: {
                Text(summary())
            }
            if !missedPoints.isEmpty {
                Section {
                    ForEach(missedPoints) { point in
                        NavigationLink {
                            GrammarPointView(point: point)
                        } label: {
                            VStack(alignment: .leading, spacing: 2) {
                                Text(point.pattern)
                                Text(point.short)
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
                        }
                    }
                } header: {
                    Text("Не знаю или ошибка: " + String(missedPoints.count))
                }
            }
            Section {
                Button("Готово") {
                    dismiss()
                }
            }
        }
        .scrollContentBackground(.hidden)
    }
}

/// A point with all its sentences.
@available(iOS 16.0, *)
struct GrammarPointView: View {
    let point: GrammarPoint
    @ObservedObject private var store = GrammarStore.shared
    @AppStorage(AppAccent.key) private var accent = AppAccent.standard
    @State private var lookup: LineLookup? = nil

    var body: some View {
        let tint = AppAccent.color(accent)
        List {
            Section {
                VStack(alignment: .leading, spacing: 8) {
                    Text(point.pattern)
                        .font(.title.weight(.bold))
                    Text(point.short)
                        .font(.headline)
                        .foregroundColor(tint)
                    Text(point.explanation)
                    if let formation = point.formation {
                        Text(formation)
                            .font(.callout.monospaced())
                            .foregroundColor(.secondary)
                    }
                }
                .padding(.vertical, 4)
            } footer: {
                Text("N" + String(point.level) + " · " + store.status(point))
            }
            Section {
                ForEach(point.examples, id: \.self) { example in
                    HStack(alignment: .top, spacing: 12) {
                        VStack(alignment: .leading, spacing: 4) {
                            Text(GrammarText.marked(example.ja, example.mark, tint))
                                .font(.title3)
                            Text(example.ru)
                                .font(.subheadline)
                                .foregroundColor(.secondary)
                        }
                        Spacer()
                        Button {
                            GrammarVoice.speak(example.ja)
                        } label: {
                            Image(systemName: "speaker.wave.2.fill")
                        }
                        .buttonStyle(.borderless)
                        Button {
                            lookup = LineLookup(text: example.ja, charAt: 0)
                        } label: {
                            Image(systemName: "character.book.closed")
                        }
                        .buttonStyle(.borderless)
                    }
                }
            } header: {
                Text("Примеры")
            }
        }
        .navigationTitle(point.pattern)
        .navigationBarTitleDisplayMode(.inline)
        .sheet(item: $lookup) { item in
            WordLookupSheet(text: item.text, charAt: item.charAt)
        }
        .satoriBackdrop()
    }
}
