/// The 2000 main kanji (the most frequent by Jiten) and how many of them your cards have; the new ones of the last
/// four weeks give the usual pace.
@available(iOS 16.0, *)
enum KanjiProgress {
    static let goal = 2000
    private(set) static var main: [String] = []

    @MainActor
    static func load() {
        guard main.isEmpty else { return }
        for line in KanjiData.text.split(separator: "\n") {
            let parts = line.split(separator: "\t")
            if parts.count >= 3, parts[0] == "c" {
                main.append(String(parts[2]))
            }
            if main.count >= goal {
                break
            }
        }
    }

    private static func kanji(of words: [String]) -> Set<String> {
        var result = Set<String>()
        for word in words {
            for scalar in word.unicodeScalars where statIsKanji(scalar) {
                result.insert(String(scalar))
            }
        }
        return result
    }

    /// The main kanji of the cards (imported and added from Satori), and how many new ones a week the words added
    /// in the last four weeks brought (since the first word added, when that was less than four weeks ago).
    @MainActor
    static func measure() -> (learned: Int, perWeek: Int)? {
        load()
        guard !main.isEmpty else { return nil }
        let mainSet = Set(main)
        guard let json = (try? Storage.stats.get())?.data(using: .utf8),
              let root = (try? JSONSerialization.jsonObject(with: json)) as? [String: Any] else { return (0, 0) }
        var minedByDay: [(day: String, words: [String])] = []
        var allMined = Set<String>()
        for (key, value) in (root["days"] as? [String: Any]) ?? [:] {
            guard let day = value as? [String: Any], let words = day["mined"] as? [String], !words.isEmpty else { continue }
            minedByDay.append((day: key, words: words))
            allMined.formUnion(words)
        }
        let imported = Set((root["known"] as? [String]) ?? [])
        let learned = kanji(of: Array(imported.union(allMined))).intersection(mainSet)
        let start = statKey(daysAgo: 27)
        // known before the four weeks: the deck words not added from Satori, and the words added earlier
        var before = kanji(of: Array(imported.subtracting(allMined)))
        var recent: [String] = []
        for item in minedByDay {
            if item.day < start {
                before.formUnion(kanji(of: item.words))
            } else {
                recent += item.words
            }
        }
        let fresh = kanji(of: recent).subtracting(before).intersection(mainSet)
        var span = 28
        if let first = minedByDay.map({ $0.day }).min(), first >= start, let date = statDateFormatter.date(from: first) {
            let calendar = Calendar.current
            let days = calendar.dateComponents([.day], from: calendar.startOfDay(for: date),
                                               to: calendar.startOfDay(for: Date())).day ?? 0
            span = max(7, days + 1)
        }
        let perWeek = Int((Double(fresh.count) * 7 / Double(span)).rounded())
        return (learned.count, perWeek)
    }
}

/// The bar of the main kanji in the statistics: learned, and lighter, the usual new ones of a week.
@available(iOS 16.0, *)
struct KanjiProgressCard: View {
    @State private var learned = 0
    @State private var perWeek = 0
    @State private var ready = false

    private func fraction(_ count: Int) -> CGFloat {
        CGFloat(min(1, Double(count) / Double(KanjiProgress.goal)))
    }

    private var trend: String {
        perWeek > 0 ? "Обычно +" + String(perWeek) + " новых в неделю — светлая часть" : "За последние недели новых кандзи не было"
    }

    var body: some View {
        Group {
            if ready {
                VStack(alignment: .leading, spacing: 8) {
                    HStack {
                        Text("Кандзи из 2000 основных")
                            .font(.footnote)
                            .foregroundColor(.secondary)
                        Spacer()
                        Text(String(learned))
                            .font(.footnote.bold())
                    }
                    GeometryReader { geometry in
                        ZStack(alignment: .leading) {
                            Capsule()
                                .fill(Color(.tertiarySystemFill))
                            Capsule()
                                .fill(Color.accentColor.opacity(0.35))
                                .frame(width: geometry.size.width * fraction(learned + perWeek))
                            Capsule()
                                .fill(Color.accentColor)
                                .frame(width: geometry.size.width * fraction(learned))
                        }
                    }
                    .frame(height: 10)
                    Text(trend)
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                .padding(14)
                .background(Color(.secondarySystemBackground))
                .cornerRadius(14)
            } else {
                Color.clear.frame(height: 0)
            }
        }
        .onAppear {
            guard let measured = KanjiProgress.measure() else { return }
            learned = measured.learned
            perWeek = measured.perWeek
            ready = true
        }
    }
}

