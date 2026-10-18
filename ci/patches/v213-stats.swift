
// MARK: - Satori v2.13: the progress (the words, the hours, the next two months)

/// One line of «Статистика → Прогресс»: values per day (0 is today, -n days ago) and what the pace of the last
/// 30 days gives in the next 60.
struct ProgressSeries {
    var points: [(day: Int, value: Double)] = []
    var forecast: [(day: Int, value: Double)] = []
    /// per day over the last 30 days (or over the days there are, from a week)
    var pace: Double = 0

    var now: Double {
        points.last?.value ?? 0
    }

    /// The value on a day: the last point on it or before it.
    func value(at day: Int) -> Double? {
        points.last { $0.day <= day }?.value
    }

    /// The forecast from the pace of the last month.
    mutating func project(days: Int = 60) {
        guard let first = points.first, let last = points.last else { return }
        let from: Int = max(first.day, last.day - 30)
        let span: Int = last.day - from
        guard span >= 7, let start = value(at: from) else { return }
        pace = max(0, (last.value - start) / Double(span))
        forecast = stride(from: 0, through: days, by: 5).map { (day: last.day + $0, value: last.value + pace * Double($0)) }
    }
}

enum ProgressData {
    private static func offset(_ key: String) -> Int? {
        guard let date = statDateFormatter.date(from: key) else { return nil }
        let calendar = Calendar.current
        return calendar.dateComponents([.day], from: calendar.startOfDay(for: Date()), to: calendar.startOfDay(for: date)).day
    }

    /// The words with a mature card, per day of the review log of Anki (kept by the last backup read).
    static func words() -> ProgressSeries {
        var series = ProgressSeries()
        guard let json = try? Storage.stats.get(), let data = json.data(using: .utf8),
              let root = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any],
              let history = root["matureHistory"] as? [[Any]] else { return series }
        for item in history {
            guard item.count == 2, let key = item[0] as? String, let count = (item[1] as? NSNumber)?.doubleValue,
                  let day = offset(key), day <= 0 else { continue }
            series.points.append((day: day, value: count))
        }
        series.points.sort { $0.day < $1.day }
        // the count stays until today
        if let last = series.points.last, last.day < 0 {
            series.points.append((day: 0, value: last.value))
        }
        series.project()
        return series
    }

    /// Hours with the language: reading, watching and the grammar cards, added up day by day.
    @MainActor
    static func hours(_ model: StatsViewModel) -> ProgressSeries {
        var seconds: [Int: Double] = [:]
        for (key, day) in model.days {
            if let at = offset(key), day.time > 0 {
                seconds[at, default: 0] += Double(day.time)
            }
        }
        for (key, day) in model.watch {
            if let at = offset(key), day.time > 0 {
                seconds[at, default: 0] += Double(day.time)
            }
        }
        for review in GrammarStore.shared.save.log ?? [] {
            if let at = offset(statDateFormatter.string(from: review.time)) {
                seconds[at, default: 0] += review.seconds
            }
        }
        var series = ProgressSeries()
        guard let first = seconds.keys.filter({ $0 <= 0 }).min() else { return series }
        var total = 0.0
        for day in first ... 0 {
            total += (seconds[day] ?? 0) / 3600
            series.points.append((day: day, value: total))
        }
        series.project()
        return series
    }
}

/// A line of values with its forecast: the past solid with the area under it, the next days dashed.
struct ProgressChart: View {
    let series: ProgressSeries
    let color: Color
    let unit: String

    private func label(_ value: Double) -> String {
        statNumber(Int(value.rounded())) + unit
    }

    var body: some View {
        let first: Int = min(series.points.first?.day ?? -30, -7)
        let last: Int = max(series.forecast.last?.day ?? 0, 7)
        let top: Double = max(1, max(series.now, series.forecast.last?.value ?? 0) * 1.12)
        GeometryReader { geo in
            let width: CGFloat = geo.size.width - 44
            let height: CGFloat = geo.size.height - 20
            let x = { (day: Int) -> CGFloat in 44 + width * CGFloat(day - first) / CGFloat(max(1, last - first)) }
            let y = { (value: Double) -> CGFloat in height - height * CGFloat(value / top) }
            ZStack(alignment: .topLeading) {
                ForEach(0 ..< 4, id: \.self) { i in
                    let value: Double = top * Double(i) / 3
                    Path { path in
                        path.move(to: CGPoint(x: 44, y: y(value)))
                        path.addLine(to: CGPoint(x: geo.size.width, y: y(value)))
                    }
                    .stroke(Color.secondary.opacity(0.18), lineWidth: 1)
                    Text(statNumber(Int(value.rounded())))
                        .font(.caption2.monospacedDigit())
                        .foregroundColor(.secondary)
                        .frame(width: 40, alignment: .trailing)
                        .position(x: 20, y: y(value))
                }
                Path { path in
                    path.move(to: CGPoint(x: x(0), y: 0))
                    path.addLine(to: CGPoint(x: x(0), y: height))
                }
                .stroke(Color.secondary.opacity(0.5), style: StrokeStyle(lineWidth: 1, dash: [3, 3]))
                Text("сегодня")
                    .font(.caption2)
                    .foregroundColor(.secondary)
                    .position(x: x(0), y: height + 11)
                if let start = series.points.first {
                    Path { path in
                        path.move(to: CGPoint(x: x(start.day), y: height))
                        for point in series.points {
                            path.addLine(to: CGPoint(x: x(point.day), y: y(point.value)))
                        }
                        path.addLine(to: CGPoint(x: x(series.points.last?.day ?? 0), y: height))
                        path.closeSubpath()
                    }
                    .fill(color.opacity(0.12))
                    Path { path in
                        path.move(to: CGPoint(x: x(start.day), y: y(start.value)))
                        for point in series.points {
                            path.addLine(to: CGPoint(x: x(point.day), y: y(point.value)))
                        }
                    }
                    .stroke(color, style: StrokeStyle(lineWidth: 2.5, lineCap: .round, lineJoin: .round))
                    Text(String(-start.day) + " д назад")
                        .font(.caption2)
                        .foregroundColor(.secondary)
                        .position(x: x(start.day) + 26, y: height + 11)
                }
                if let end = series.forecast.last, let begin = series.forecast.first {
                    Path { path in
                        path.move(to: CGPoint(x: x(begin.day), y: y(begin.value)))
                        for point in series.forecast {
                            path.addLine(to: CGPoint(x: x(point.day), y: y(point.value)))
                        }
                    }
                    .stroke(color, style: StrokeStyle(lineWidth: 2.5, lineCap: .round, dash: [7, 5]))
                    Text("~" + label(end.value))
                        .font(.caption2.weight(.semibold))
                        .foregroundColor(color)
                        .position(x: min(x(end.day) - 22, geo.size.width - 30), y: max(8, y(end.value) - 12))
                    Text("+" + String(end.day) + " д")
                        .font(.caption2)
                        .foregroundColor(.secondary)
                        .position(x: geo.size.width - 18, y: height + 11)
                }
                Circle()
                    .fill(color)
                    .frame(width: 8, height: 8)
                    .position(x: x(0), y: y(series.now))
                Text(label(series.now))
                    .font(.caption2.weight(.semibold))
                    .foregroundColor(color)
                    .position(x: x(0) - 24, y: max(8, y(series.now) - 12))
            }
        }
        .frame(height: 200)
    }
}

/// «Статистика → Прогресс».
@available(iOS 16.0, *)
struct ProgressStatsView: View {
    @ObservedObject var model: StatsViewModel
    @AppStorage(AppAccent.key) private var accent = AppAccent.standard
    @State private var words = ProgressSeries()
    @State private var hours = ProgressSeries()

    /// The words of a JLPT level, as for the known words of the analysis (VideoLibraryStore.vocabulary).
    private static let levels: [(name: String, words: Double)] = [
        ("N5", 800), ("N4", 1500), ("N3", 3700), ("N2", 6000), ("N1", 10000),
    ]

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

    private func paceText(_ series: ProgressSeries, _ unit: String, digits: Int) -> String {
        guard series.pace > 0 else { return "темп появится через неделю" }
        let pace: String = String(format: "%." + String(digits) + "f", series.pace)
        let after: String = statNumber(Int((series.forecast.last?.value ?? series.now).rounded()))
        var text: String = "За месяц: " + pace + unit + " в день"
        text += " · через 60 дней ~" + after
        return text
    }

    /// The next JLPT level by the words and the days to it at this pace.
    private func nextLevel() -> String? {
        guard let next = ProgressStatsView.levels.first(where: { $0.words > words.now }) else { return nil }
        let left: Double = next.words - words.now
        var text: String = "До " + next.name + " (" + statNumber(Int(next.words)) + " слов): "
        if words.pace > 0 {
            text += "~" + statNumber(Int((left / words.pace).rounded(.up))) + " дн. при этом темпе"
        } else {
            text += statNumber(Int(left)) + " слов"
        }
        return text
    }

    var body: some View {
        let tint = AppAccent.color(accent)
        VStack(alignment: .leading, spacing: 16) {
            LazyVGrid(columns: [GridItem(.flexible(), spacing: 12), GridItem(.flexible(), spacing: 12)], spacing: 12) {
                StatCard(title: "Слов в зрелых карточках", value: words.points.isEmpty ? "—" : statNumber(Int(words.now)))
                StatCard(title: "Часов с языком", value: statNumber(Int(hours.now.rounded())))
            }
            card("Словарный запас") {
                if words.points.isEmpty {
                    Text("Нет истории: прочитайте бэкап AnkiMobile ещё раз (Настройки → Anki).")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                } else {
                    ProgressChart(series: words, color: tint, unit: "")
                    Text(paceText(words, " слов", digits: 0))
                        .font(.subheadline)
                    if let level = nextLevel() {
                        Text(level)
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                    }
                }
            }
            card("Часы с языком") {
                if hours.points.isEmpty {
                    Text("Пока нет времени чтения и просмотра.")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                } else {
                    ProgressChart(series: hours, color: .orange, unit: " ч")
                    Text(paceText(hours, " ч", digits: 1))
                        .font(.subheadline)
                }
            }
        }
        .onAppear {
            words = ProgressData.words()
            hours = ProgressData.hours(model)
        }
    }
}
