
// MARK: - Satori v2.07: the statistics of the grammar, the lists and subtitles of a folder

/// One answer in the grammar decks (GrammarSave.log), for «Статистика → Грамматика».
struct GrammarReview: Codable {
    var time: Date
    var id: String
    /// 1 «Снова» … 4 «Легко»
    var grade: Int
    /// the card before the answer: 0 new, 1 learning, 2 review, 3 relearning
    var state: Int
    /// its interval in days before the answer (21 and more: mature)
    var interval: Int
    /// how long the card was on screen, at most a minute (as in Anki)
    var seconds: Double
}

struct GrammarRetentionRow: Identifiable {
    let title: String
    var youngRight = 0
    var youngAll = 0
    var matureRight = 0
    var matureAll = 0
    var id: String { title }
}

/// The parts of Anki's statistics that make sense for the grammar decks: today, the true retention, the difficulty
/// and the retrievability of the cards.
struct GrammarStats {
    var studied = 0
    var seconds = 0.0
    var again = 0
    var learned = 0
    var reviewed = 0
    var relearned = 0
    var matureRight = 0
    var matureAll = 0
    var retention: [GrammarRetentionRow] = []
    /// ten parts of 10% each, and the mean (0…1)
    var difficulty = [Int](repeating: 0, count: 10)
    var difficultyMean: Double? = nil
    var retrievability = [Int](repeating: 0, count: 10)
    var retrievabilityMean: Double? = nil

    @MainActor
    static func make(_ save: GrammarSave, level: Int?, now: Date = Date()) -> GrammarStats {
        var stats = GrammarStats()
        func counted(_ id: String) -> Bool {
            guard let level else { return true }
            return GrammarLibrary.byId[id]?.level == level
        }
        let log = (save.log ?? []).filter { counted($0.id) }
        let dayStart = GrammarStore.dayEnd(now).addingTimeInterval(-86_400)
        for review in log where review.time >= dayStart {
            stats.studied += 1
            stats.seconds += review.seconds
            if review.grade == 1 {
                stats.again += 1
            }
            if review.state == 2 {
                stats.reviewed += 1
            } else if review.state == 3 {
                stats.relearned += 1
            } else {
                stats.learned += 1
            }
            if review.state == 2 && review.interval >= 21 {
                stats.matureAll += 1
                if review.grade > 1 {
                    stats.matureRight += 1
                }
            }
        }
        // the true retention: the answers to cards in review, young (interval under 21 days) and mature
        let day: Double = 86_400
        let periods: [(title: String, from: Date, to: Date)] = [
            ("Сегодня", dayStart, .distantFuture),
            ("Вчера", dayStart.addingTimeInterval(-day), dayStart),
            ("Неделя", dayStart.addingTimeInterval(-6 * day), .distantFuture),
            ("Месяц", dayStart.addingTimeInterval(-29 * day), .distantFuture),
            ("Год", dayStart.addingTimeInterval(-364 * day), .distantFuture),
            ("Всё время", .distantPast, .distantFuture),
        ]
        for period in periods {
            var row = GrammarRetentionRow(title: period.title)
            for review in log where review.state == 2 && review.time >= period.from && review.time < period.to {
                let right = review.grade > 1 ? 1 : 0
                if review.interval >= 21 {
                    row.matureAll += 1
                    row.matureRight += right
                } else {
                    row.youngAll += 1
                    row.youngRight += right
                }
            }
            stats.retention.append(row)
        }
        var difficultySum = 0.0
        var difficultyCount = 0
        var recallSum = 0.0
        var recallCount = 0
        for (id, card) in save.cards where card.state != 0 && counted(id) {
            if card.difficulty > 0 {
                let part: Double = min(max((card.difficulty - 1) / 9, 0), 1)
                stats.difficulty[min(9, Int(part * 10))] += 1
                difficultySum += part
                difficultyCount += 1
            }
            if let last = card.last, card.stability > 0 {
                let days: Double = max(0, now.timeIntervalSince(last) / day)
                let recall: Double = FSRS.retrievability(days: days, stability: card.stability)
                stats.retrievability[min(9, Int(recall * 10))] += 1
                recallSum += recall
                recallCount += 1
            }
        }
        if difficultyCount > 0 {
            stats.difficultyMean = difficultySum / Double(difficultyCount)
        }
        if recallCount > 0 {
            stats.retrievabilityMean = recallSum / Double(recallCount)
        }
        return stats
    }
}

/// «Статистика → Грамматика».
@available(iOS 16.0, *)
struct GrammarStatsView: View {
    @ObservedObject private var store = GrammarStore.shared
    @AppStorage(AppAccent.key) private var accent = AppAccent.standard
    /// 0: all the decks
    @AppStorage("ykGrammarStatsLevel") private var level = 0

    private func percent(_ right: Int, _ all: Int) -> String {
        guard all > 0 else { return "—" }
        let value: Int = Int((Double(right) * 100 / Double(all)).rounded())
        return String(value) + "%"
    }

    private func card<Content: View>(_ title: String, @ViewBuilder _ content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(title)
                .font(.headline)
            content()
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(14)
        .background(Color(.secondarySystemBackground))
        .cornerRadius(14)
    }

    /// The lines of «Сегодня», built in steps (one long expression is too slow for the type checker).
    private func todayLines(_ stats: GrammarStats) -> [String] {
        guard stats.studied > 0 else { return [] }
        let studied: String = String(stats.studied)
        let minutes: String = String(Int((stats.seconds / 60).rounded()))
        let each: String = String(Int((stats.seconds / Double(stats.studied)).rounded()))
        var first: String = "Изучено " + studied
        first += " за " + minutes + " мин"
        first += " (" + each + " с на карточку)"
        var second: String = "Снова: " + String(stats.again)
        second += " · правильно " + percent(stats.studied - stats.again, stats.studied)
        var third: String = "Изучение: " + String(stats.learned)
        third += " · повторение: " + String(stats.reviewed)
        third += " · переучивание: " + String(stats.relearned)
        var lines: [String] = [first, second, third]
        if stats.matureAll > 0 {
            var mature: String = "Зрелые: " + String(stats.matureRight)
            mature += " из " + String(stats.matureAll)
            mature += " (" + percent(stats.matureRight, stats.matureAll) + ")"
            lines.append(mature)
        }
        return lines
    }

    private func today(_ stats: GrammarStats) -> some View {
        let lines = todayLines(stats)
        return VStack(alignment: .leading, spacing: 6) {
            if lines.isEmpty {
                Text("Сегодня карточки не изучались.")
                    .foregroundColor(.secondary)
            }
            ForEach(lines, id: \.self) { line in
                Text(line)
            }
        }
        .font(.subheadline)
    }

    private func meanLine(_ mean: Double, _ total: Int) -> String {
        let share: String = String(Int((mean * 100).rounded()))
        var line: String = "В среднем: " + share + "%"
        line += " · карточек: " + String(total)
        return line
    }

    private func cell(_ right: Int, _ all: Int) -> some View {
        VStack(alignment: .trailing, spacing: 1) {
            Text(percent(right, all))
                .font(.subheadline.monospacedDigit())
            Text(String(all))
                .font(.caption2.monospacedDigit())
                .foregroundColor(.secondary)
        }
        .frame(maxWidth: .infinity, alignment: .trailing)
    }

    private func retention(_ rows: [GrammarRetentionRow]) -> some View {
        Grid(alignment: .leading, horizontalSpacing: 10, verticalSpacing: 8) {
            GridRow {
                Text("")
                Text("Молодые").frame(maxWidth: .infinity, alignment: .trailing)
                Text("Зрелые").frame(maxWidth: .infinity, alignment: .trailing)
                Text("Всего").frame(maxWidth: .infinity, alignment: .trailing)
            }
            .font(.caption.weight(.semibold))
            .foregroundColor(.secondary)
            ForEach(rows) { row in
                GridRow {
                    Text(row.title)
                        .font(.subheadline)
                    cell(row.youngRight, row.youngAll)
                    cell(row.matureRight, row.matureAll)
                    cell(row.youngRight + row.matureRight, row.youngAll + row.matureAll)
                }
            }
        }
    }

    private func bars(_ parts: [Int], mean: Double?) -> some View {
        let tallest = max(1, parts.max() ?? 1)
        let total = parts.reduce(0, +)
        return VStack(alignment: .leading, spacing: 6) {
            if total == 0 {
                Text("Нет начатых карточек.")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
            } else {
                HStack(alignment: .bottom, spacing: 4) {
                    ForEach(parts.indices, id: \.self) { i in
                        RoundedRectangle(cornerRadius: 3)
                            .fill(AppAccent.color(accent).opacity(0.45 + 0.055 * Double(i)))
                            .frame(height: max(2, 70 * CGFloat(parts[i]) / CGFloat(tallest)))
                            .frame(maxWidth: .infinity)
                    }
                }
                .frame(height: 74, alignment: .bottom)
                .animation(.easeInOut(duration: 0.3), value: parts)
                HStack {
                    Text("0%")
                    Spacer()
                    Text("50%")
                    Spacer()
                    Text("100%")
                }
                .font(.caption2)
                .foregroundColor(.secondary)
                if let mean {
                    Text(meanLine(mean, total))
                        .font(.subheadline)
                }
            }
        }
    }

    var body: some View {
        let stats = GrammarStats.make(store.save, level: level == 0 ? nil : level)
        VStack(alignment: .leading, spacing: 16) {
            Picker("Колода", selection: $level) {
                Text("Все").tag(0)
                ForEach([5, 4, 3, 2, 1], id: \.self) { value in
                    Text("N" + String(value)).tag(value)
                }
            }
            .pickerStyle(.segmented)
            card("Сегодня") {
                today(stats)
            }
            card("Истинное удержание") {
                retention(stats.retention)
            }
            card("Сложность карточек") {
                bars(stats.difficulty, mean: stats.difficultyMean)
            }
            card("Извлекаемость карточек") {
                bars(stats.retrievability, mean: stats.retrievabilityMean)
            }
        }
    }
}

@available(iOS 16.0, *)
extension VideoLibraryStore {
    /// The videos of a folder and of its folders, in the order of their names.
    static func videos(in folder: URL) -> [URL] {
        guard let walker = FileManager.default.enumerator(at: folder, includingPropertiesForKeys: nil,
                                                          options: [.skipsHiddenFiles]) else { return [] }
        var found: [URL] = []
        for case let url as URL in walker where isVideo(url.lastPathComponent) {
            found.append(url)
        }
        return found.sorted { $0.path.localizedStandardCompare($1.path) == .orderedAscending }
    }

    /// The subtitles of several series taken as one text (the list of a folder), with the speech speed of all.
    nonisolated static func analyze(files: [URL], index: KnownWordsIndex, level: Int, vocabulary: Int) -> EpisodeAnalysis? {
        var lines: [String] = []
        var seconds: Double = 0
        for file in files {
            let cues = EmbeddedSubtitles.cues(fromFile: file)
            lines += cues.map { $0.text }
            seconds += speechSeconds(cues)
        }
        guard var result = TextAnalysis.analyze(lines: lines, index: index, level: level, vocabulary: vocabulary) else {
            return nil
        }
        if seconds >= 60, result.morae > 0 {
            let speed: Double = Double(result.morae) / (seconds / 60)
            result.speed = speed
            if result.difficulty != nil {
                result.difficulty = classify(known: result.knownShare, clear: result.clearShare, speed: speed)
            }
        }
        return result
    }

    /// Jimaku for every video of a folder (and of its folders) that has no subtitles from it yet, one after another;
    /// the row of the folder shows how far it is.
    func findSubtitles(inFolder folder: URL) {
        let name = folder.lastPathComponent
        guard JimakuKeychain.read() != nil else {
            status[name] = "нужен ключ Jimaku («+» → «Ключ Jimaku»)"
            return
        }
        let videos = VideoLibraryStore.videos(in: folder).filter { VideoLibraryStore.jimakuFile(for: $0) == nil }
        guard !videos.isEmpty else {
            status[name] = "у всех видео уже есть субтитры Jimaku"
            return
        }
        Task { @MainActor in
            var found = 0
            let all: String = String(videos.count)
            for (i, video) in videos.enumerated() {
                let step: String = String(i + 1)
                status[name] = "Jimaku: " + step + " из " + all + "…"
                progress[name] = Double(i) / Double(videos.count)
                if await JimakuFinder.run(video, report: { _ in }) != nil {
                    found += 1
                }
            }
            progress[name] = nil
            let done: String = String(found)
            status[name] = "Jimaku: найдено " + done + " из " + all
            reload()
        }
    }
}

@available(iOS 16.0, *)
extension ListMining {
    /// The clearest line with the word in all these series, and its series.
    static func bestLine(for word: String, in pairs: [(video: URL, file: URL)],
                         judge: WordKnowledge) -> (video: URL, line: Line)? {
        var best: (score: Double, video: URL, line: Line)? = nil
        for pair in pairs {
            guard let found = scoredLine(for: word, file: pair.file, judge: judge) else { continue }
            if let current = best, current.score <= found.score {
                continue
            }
            best = (score: found.score, video: pair.video, line: found.line)
        }
        guard let best else { return nil }
        return (video: best.video, line: best.line)
    }
}

@available(iOS 16.0, *)
extension QueueMiningHooks {
    /// ⊕ queues the note under this video (in the list of a folder: the series of the line shown).
    @MainActor
    static func queue(into name: String) {
        yomikiriOpenLinkHook = { link in
            guard MiningFrame.isAddNote(link) else { return link }
            MiningQueue.shared.add(MiningFrame.attach(to: link), video: name)
            UINotificationFeedbackGenerator().notificationOccurred(.success)
            return nil
        }
    }
}
