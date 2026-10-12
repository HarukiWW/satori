# v1.46 (statistics): words imported from Anki count in "в Anki" and unique kanji for all time and are listed
# under "Из Anki" in the added words; a reading / watching switch with watching statistics (kept in the app only,
# key watch.v1, so the Safari extension never overwrites it).
import pathlib

p = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = p.read_text(encoding="utf-8")


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


s = once(s, "struct StatFile: Decodable {\n    var days: [String: StatDay]\n}\n", '''struct StatFile: Decodable {
    var days: [String: StatDay]
    /// words imported from Anki collections
    var known: [String]? = nil
}

/// Watching in the video player, per day (kept by the app only).
struct WatchDay: Codable {
    var time = 0
    var words = 0
}

enum WatchStats {
    static let key = "watch.v1"

    static func load() -> [String: WatchDay] {
        guard let data = UserDefaults.standard.data(forKey: key),
              let days = try? JSONDecoder().decode([String: WatchDay].self, from: data) else { return [:] }
        return days
    }

    static func add(seconds: Int, words: Int) {
        var days = load()
        let today = statKey(daysAgo: 0)
        var day = days[today] ?? WatchDay()
        day.time += seconds
        day.words += words
        days[today] = day
        if let data = try? JSONEncoder().encode(days) {
            UserDefaults.standard.set(data, forKey: key)
        }
    }
}

struct WatchSummary {
    var time = 0
    var words = 0
    var average = 0
}
''', "StatFile")

s = once(s, "    @Published var days: [String: StatDay] = [:]\n",
         "    @Published var days: [String: StatDay] = [:]\n    @Published var known: [String] = []\n    @Published var watch: [String: WatchDay] = [:]\n",
         "model vars")
s = once(s, "    func reload() {\n        guard let json = try? Storage.stats.get(),",
         "    func reload() {\n        watch = WatchStats.load()\n        guard let json = try? Storage.stats.get(),", "model reload")
s = once(s, "        days = file.days\n    }\n", "        days = file.days\n        known = file.known ?? []\n    }\n", "known")
s = once(s, "        result.minedWords = words.count\n        result.kanji = kanji.count\n        return result\n", '''        if lastDays == nil {
            // words imported from Anki count for all time
            for word in known {
                words.insert(word)
                for scalar in word.unicodeScalars where statIsKanji(scalar) {
                    kanji.insert(String(scalar))
                }
            }
        }
        result.minedWords = words.count
        result.kanji = kanji.count
        return result
    }

    func watchSummary(lastDays: Int?) -> WatchSummary {
        var result = WatchSummary()
        var dayCount = 0
        if let n = lastDays {
            for i in 0 ..< n {
                if let day = watch[statKey(daysAgo: i)] {
                    result.time += day.time
                    result.words += day.words
                }
            }
            dayCount = n
        } else {
            for day in watch.values {
                result.time += day.time
                result.words += day.words
            }
            if let first = watch.keys.min(), let date = statDateFormatter.date(from: first) {
                let calendar = Calendar.current
                let days = calendar.dateComponents([.day], from: calendar.startOfDay(for: date),
                                                   to: calendar.startOfDay(for: Date())).day ?? 0
                dayCount = max(1, days + 1)
            }
        }
        result.average = dayCount > 0 ? result.time / dayCount : 0
        return result
    }

    /// Days in a row with at least a minute of watching.
    func watchStreak() -> Int {
        func isActive(_ key: String) -> Bool {
            (watch[key]?.time ?? 0) >= 60
        }
        var i = isActive(statKey(daysAgo: 0)) ? 0 : 1
        var count = 0
        while i < 3650 && isActive(statKey(daysAgo: i)) {
            count += 1
            i += 1
        }
        return count
    }

    /// Minutes of watching for the last 7 days.
    func watchBars() -> [StatBar] {
        var result: [StatBar] = []
        for i in (0 ..< 7).reversed() {
            let key = statKey(daysAgo: i)
            let label = statWeekdayFormatter.string(from: statDate(daysAgo: i))
            result.append(StatBar(id: key, label: label, read: (watch[key]?.time ?? 0) / 60))
        }
        return result
''', "summary + watch")

# the screen: common metrics, then the reading / watching switch
s = once(s, "    @State private var period = 0\n", "    @State private var period = 0\n    @State private var mode = 0\n", "mode state")
s = once(s, "        let bars = model.bars()\n", "        let bars = mode == 0 ? model.bars() : model.watchBars()\n", "bars")
start = s.index("                LazyVGrid(\n")
end = s.index("                Button(role: .destructive) {\n                    confirmReset = true\n")
s = s[:start] + '''                LazyVGrid(
                    columns: [GridItem(.flexible(), spacing: 12), GridItem(.flexible(), spacing: 12)],
                    spacing: 12
                ) {
                    StatCard(title: "Слов в Anki", value: statNumber(s.minedWords))
                    StatCard(title: "Кандзи (уник.)", value: statNumber(s.kanji))
                }

                Picker("Режим", selection: $mode) {
                    Text("Чтение").tag(0)
                    Text("Просмотр").tag(1)
                }
                .pickerStyle(.segmented)

                if mode == 0 {
                    LazyVGrid(
                        columns: [GridItem(.flexible(), spacing: 12), GridItem(.flexible(), spacing: 12)],
                        spacing: 12
                    ) {
                        StatCard(title: "Прочитано предложений", value: statNumber(s.sentences))
                        StatCard(title: "Прочитано слов", value: statNumber(s.readWords))
                        StatCard(title: "Прочитано знаков", value: statNumber(s.read))
                        StatCard(title: "Время чтения", value: statDuration(s.time))
                        StatCard(title: "Скорость, зн./мин", value: speed(s))
                        StatCard(title: "Серия, дней подряд", value: statNumber(model.streak()))
                    }
                } else {
                    let w = model.watchSummary(lastDays: period == 0 ? 1 : (period == 1 ? 7 : nil))
                    LazyVGrid(
                        columns: [GridItem(.flexible(), spacing: 12), GridItem(.flexible(), spacing: 12)],
                        spacing: 12
                    ) {
                        StatCard(title: "Слов из субтитров", value: statNumber(w.words))
                        StatCard(title: "Время просмотра", value: statDuration(w.time))
                        StatCard(title: "Дней подряд", value: statNumber(model.watchStreak()))
                        StatCard(title: "В среднем за день", value: statDuration(w.average))
                    }
                }

                VStack(alignment: .leading, spacing: 10) {
                    Text(mode == 0 ? "Прочитано знаков за 7 дней" : "Время просмотра за 7 дней, мин")
                        .font(.footnote)
                        .foregroundColor(.secondary)
                    HStack(alignment: .bottom, spacing: 8) {
                        ForEach(bars) { bar in
                            VStack(spacing: 4) {
                                RoundedRectangle(cornerRadius: 4)
                                    .fill(Color.orange)
                                    .frame(height: max(3, 90 * CGFloat(bar.read) / CGFloat(maxRead)))
                                Text(bar.label)
                                    .font(.caption2)
                                    .foregroundColor(.secondary)
                            }
                            .frame(maxWidth: .infinity)
                        }
                    }
                    .frame(height: 120, alignment: .bottom)
                }
                .padding(14)
                .background(Color(.secondarySystemBackground))
                .cornerRadius(14)

''' + s[end:]

# the added words: "Из Anki" at the very bottom
s = once(s, '    @State private var query = ""\n', '''    @State private var query = ""

    private var importedWords: [String] {
        model.known.filter { query.isEmpty || $0.localizedCaseInsensitiveContains(query) }
    }

    @ViewBuilder
    private var importedSection: some View {
        if !importedWords.isEmpty {
            Section(header: Text("Из Anki · " + statNumber(importedWords.count))) {
                ForEach(importedWords, id: \\.self) { word in
                    Text(word)
                        .font(.system(size: 20))
                        .padding(.vertical, 4)
                        .contextMenu {
                            Button {
                                UIPasteboard.general.string = word
                            } label: {
                                Label("Копировать", systemImage: "doc.on.doc")
                            }
                        }
                }
            }
        }
    }
''', "imported list")
s = once(s, '            }\n            .listStyle(.insetGrouped)\n            .searchable(text: $query, prompt: "Поиск")',
         '                importedSection\n            }\n            .listStyle(.insetGrouped)\n            .searchable(text: $query, prompt: "Поиск")',
         "imported section in list")
s = once(s, "                    if sections.isEmpty {\n", "                    if sections.isEmpty && importedWords.isEmpty {\n", "empty overlay")

p.write_text(s, encoding="utf-8")
print("v1.46 statistics patch applied")
