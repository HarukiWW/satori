# Moved out of build-ios-v141-player.yml, step "Patch Swift (App Group sync, statistics tab, share sheet)" (GitHub limits workflow files to 500 KB).
import pathlib, re

root = pathlib.Path("src/safari")
tok = root / "YomikiriTokenizer/YomikiriTokenizer"

def replace_once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)

def regex_replace_once(text, pattern, new, label):
    m = re.search(pattern, text, re.S)
    assert m, "pattern not found: " + label
    return text[: m.start()] + new + text[m.end():]

# ---------- 1. App Group: find the group that this process can really access ----------
p = tok / "Utils.swift"
s = p.read_text()
s = regex_replace_once(s, r"public func getSharedDirectory\(\) throws -> URL \{.*?\n\}\n", '''/// App Groups that may be available to this process:
/// the one the app was built with, and the groups listed in the embedded provisioning profile.
private func candidateAppGroupIds() -> [String] {
    var ids: [String] = [APP_GROUP_ID]
    if let path = Bundle.main.path(forResource: "embedded", ofType: "mobileprovision"),
       let data = FileManager.default.contents(atPath: path),
       let text = String(data: data, encoding: .isoLatin1),
       let start = text.range(of: "<?xml"),
       let end = text.range(of: "</plist>"),
       start.lowerBound < end.upperBound,
       let xml = String(text[start.lowerBound ..< end.upperBound]).data(using: .utf8),
       let plist = (try? PropertyListSerialization.propertyList(from: xml, options: [], format: nil)) as? [String: Any],
       let entitlements = plist["Entitlements"] as? [String: Any],
       let groups = entitlements["com.apple.security.application-groups"] as? [String]
    {
        for group in groups.sorted() where !ids.contains(group) {
            ids.append(group)
        }
    }
    return ids
}

/// The first App Group that this process can access, if there is one.
let resolvedAppGroup: (id: String, url: URL)? = {
    for id in candidateAppGroupIds() {
        if let url = FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: id) {
            return (id: id, url: url)
        }
    }
    return nil
}()

/// Returns URL path to directory that all Yomikiri apps share
public func getSharedDirectory() throws -> URL {
    if let group = resolvedAppGroup {
        return group.url
    }
    // Fallback for builds without App Group access: the private folder of this process
    let fm = FileManager.default
    guard let dir = fm.urls(for: .applicationSupportDirectory, in: .userDomainMask).first else {
        throw YomikiriTokenizerError.CouldNotAccessDirectory
    }
    if !fm.fileExists(atPath: dir.path) {
        try fm.createDirectory(at: dir, withIntermediateDirectories: true)
    }
    return dir
}
''', "getSharedDirectory")
p.write_text(s)

# ---------- 2. shared UserDefaults + stats storage ----------
p = tok / "Storage.swift"
s = p.read_text()
s = replace_once(s, '    public static let dictSchemaVer = StorageProperty<Int>(key: "dict.schema_ver")\n',
                 '    public static let dictSchemaVer = StorageProperty<Int>(key: "dict.schema_ver")\n    /// Reading and mining statistics (JSON), shared between the extension and the app\n    public static let stats = StoragePropertyWithDefault<String>(key: "stats.v1", other: "null")\n', "stats property")
s = regex_replace_once(s, r"private func getSharedDefaults\(\) -> Result<UserDefaults, YomikiriTokenizerError> \{.*?\n\}\n", '''private func getSharedDefaults() -> Result<UserDefaults, YomikiriTokenizerError> {
    if let group = resolvedAppGroup, let shared = UserDefaults(suiteName: group.id) {
        return .success(shared)
    }
    return .success(UserDefaults.standard)
}
''', "getSharedDefaults")
p.write_text(s)

# ---------- 3. extension handler: load / save statistics ----------
p = root / "iOS (Extension)/IOSWebExtensionHandler.swift"
s = p.read_text()
s = replace_once(s, '                case "iosVersion":\n',
                 '                case "loadStats":\n                    jsonResponse = try Storage.stats.get()\n                case "saveStats":\n                    try Storage.stats.set(request)\n                case "iosVersion":\n', "handler stats")
p.write_text(s)

# ---------- 4. statistics tab instead of Help ----------
(root / "iOS (App)/HelpView.swift").write_text('''//
//  HelpView.swift
//  Yomikiri (iOS)
//
//  Replaced by the statistics screen.
//

import SwiftUI
import YomikiriTokenizer

struct StatDay: Decodable {
    var mined: [String] = []
    var kanji: [String] = []
    var read = 0
    var time = 0
    var sentences = 0
    var words = 0

    enum CodingKeys: String, CodingKey {
        case mined, kanji, read, time, sentences, words
    }

    init() {}

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        mined = (try? c.decode([String].self, forKey: .mined)) ?? []
        kanji = (try? c.decode([String].self, forKey: .kanji)) ?? []
        read = (try? c.decode(Int.self, forKey: .read)) ?? 0
        time = (try? c.decode(Int.self, forKey: .time)) ?? 0
        sentences = (try? c.decode(Int.self, forKey: .sentences)) ?? 0
        words = (try? c.decode(Int.self, forKey: .words)) ?? 0
    }
}

struct StatFile: Decodable {
    var days: [String: StatDay]
}

struct StatSummary {
    var minedWords = 0
    var kanji = 0
    var read = 0
    var time = 0
    var sentences = 0
    var readWords = 0
}

struct StatBar: Identifiable {
    var id: String
    var label: String
    var read: Int
}

private let statDateFormatter: DateFormatter = {
    let formatter = DateFormatter()
    formatter.locale = Locale(identifier: "en_US_POSIX")
    formatter.dateFormat = "yyyy-MM-dd"
    return formatter
}()

private let statWeekdayFormatter: DateFormatter = {
    let formatter = DateFormatter()
    formatter.locale = Locale(identifier: "ru_RU")
    formatter.dateFormat = "E"
    return formatter
}()

private func statDate(daysAgo: Int) -> Date {
    return Calendar.current.date(byAdding: .day, value: -daysAgo, to: Date()) ?? Date()
}

private func statKey(daysAgo: Int) -> String {
    return statDateFormatter.string(from: statDate(daysAgo: daysAgo))
}

private func statNumber(_ n: Int) -> String {
    let formatter = NumberFormatter()
    formatter.numberStyle = .decimal
    formatter.locale = Locale(identifier: "ru_RU")
    return formatter.string(from: NSNumber(value: n)) ?? String(n)
}

private func statDuration(_ seconds: Int) -> String {
    if seconds <= 0 {
        return "—"
    }
    let minutes = Int((Double(seconds) / 60.0).rounded())
    if minutes < 60 {
        return String(minutes) + " мин"
    }
    return String(minutes / 60) + " ч " + String(minutes % 60) + " мин"
}

@MainActor
final class StatsViewModel: ObservableObject {
    @Published var days: [String: StatDay] = [:]

    func reload() {
        guard let json = try? Storage.stats.get(),
              let data = json.data(using: .utf8),
              let file = try? JSONDecoder().decode(StatFile.self, from: data)
        else {
            days = [:]
            return
        }
        days = file.days
    }

    func reset() {
        let token = UUID().uuidString
        _ = try? Storage.stats.set("{\\"days\\":{},\\"resetToken\\":\\"" + token + "\\"}")
        reload()
    }

    /// `lastDays`: number of last days including today. nil: all time.
    func summary(lastDays: Int?) -> StatSummary {
        var words = Set<String>()
        var kanji = Set<String>()
        var result = StatSummary()
        var keys: [String] = []
        if let n = lastDays {
            for i in 0 ..< n {
                keys.append(statKey(daysAgo: i))
            }
        } else {
            keys = Array(days.keys)
        }
        for key in keys {
            guard let day = days[key] else {
                continue
            }
            for w in day.mined {
                words.insert(w)
            }
            for k in day.kanji {
                kanji.insert(k)
            }
            result.read += day.read
            result.time += day.time
            result.sentences += day.sentences
            result.readWords += day.words
        }
        result.minedWords = words.count
        result.kanji = kanji.count
        return result
    }

    func streak() -> Int {
        func isActive(_ key: String) -> Bool {
            guard let day = days[key] else {
                return false
            }
            return day.read >= 50 || !day.mined.isEmpty
        }
        var i = isActive(statKey(daysAgo: 0)) ? 0 : 1
        var count = 0
        while i < 3650 && isActive(statKey(daysAgo: i)) {
            count += 1
            i += 1
        }
        return count
    }

    func bars() -> [StatBar] {
        var result: [StatBar] = []
        for i in (0 ..< 7).reversed() {
            let key = statKey(daysAgo: i)
            let label = statWeekdayFormatter.string(from: statDate(daysAgo: i))
            result.append(StatBar(id: key, label: label, read: days[key]?.read ?? 0))
        }
        return result
    }
}

struct StatCard: View {
    let title: String
    let value: String

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(value)
                .font(.system(size: 26, weight: .semibold, design: .rounded))
                .lineLimit(1)
                .minimumScaleFactor(0.6)
            Text(title)
                .font(.footnote)
                .foregroundColor(.secondary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(14)
        .background(Color(.secondarySystemBackground))
        .cornerRadius(14)
    }
}

struct HelpView: View {
    @StateObject private var model = StatsViewModel()
    @State private var period = 0
    @State private var confirmReset = false

    private var summary: StatSummary {
        if period == 0 {
            return model.summary(lastDays: 1)
        } else if period == 1 {
            return model.summary(lastDays: 7)
        } else {
            return model.summary(lastDays: nil)
        }
    }

    private func speed(_ s: StatSummary) -> String {
        if s.time < 60 || s.read == 0 {
            return "—"
        }
        return statNumber(Int((Double(s.read) / (Double(s.time) / 60.0)).rounded()))
    }

    var body: some View {
        let s = summary
        let bars = model.bars()
        let maxRead = max(1, bars.map { $0.read }.max() ?? 1)
        return ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Text("Статистика")
                    .font(.system(size: 30, weight: .bold))

                Picker("Период", selection: $period) {
                    Text("Сегодня").tag(0)
                    Text("7 дней").tag(1)
                    Text("Всё время").tag(2)
                }
                .pickerStyle(.segmented)

                LazyVGrid(
                    columns: [GridItem(.flexible(), spacing: 12), GridItem(.flexible(), spacing: 12)],
                    spacing: 12
                ) {
                    StatCard(title: "Слов в Anki", value: statNumber(s.minedWords))
                    StatCard(title: "Кандзи (уник.)", value: statNumber(s.kanji))
                    StatCard(title: "Прочитано предложений", value: statNumber(s.sentences))
                    StatCard(title: "Прочитано слов", value: statNumber(s.readWords))
                    StatCard(title: "Прочитано знаков", value: statNumber(s.read))
                    StatCard(title: "Время чтения", value: statDuration(s.time))
                    StatCard(title: "Скорость, зн./мин", value: speed(s))
                    StatCard(title: "Серия, дней подряд", value: statNumber(model.streak()))
                }

                VStack(alignment: .leading, spacing: 10) {
                    Text("Прочитано знаков за 7 дней")
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

                Button(role: .destructive) {
                    confirmReset = true
                } label: {
                    Text("Сбросить статистику")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.bordered)
            }
            .padding(16)
        }
        .onAppear {
            model.reload()
        }
        .onReceive(NotificationCenter.default.publisher(for: UIApplication.didBecomeActiveNotification)) { _ in
            model.reload()
        }
        .confirmationDialog("Удалить всю статистику?", isPresented: $confirmReset, titleVisibility: .visible) {
            Button("Удалить", role: .destructive) {
                model.reset()
            }
            Button("Отмена", role: .cancel) {}
        }
    }
}
''')

# ---------- 5. Russian tab and screen titles ----------
p = root / "iOS (App)/MainView.swift"
s = p.read_text()
s = replace_once(s, 'Label("Help", systemImage: "questionmark.circle")', 'Label("Статистика", systemImage: "chart.bar.fill")', "tab help")
s = replace_once(s, 'Label("Dictionary", systemImage: "character.book.closed.fill")', 'Label("Словарь", systemImage: "character.book.closed.fill")', "tab dictionary")
s = replace_once(s, 'Label("Settings", systemImage: "gearshape.fill")', 'Label("Настройки", systemImage: "gearshape.fill")', "tab settings")
p.write_text(s)

p = root / "iOS (App)/OptionsView.swift"
s = p.read_text()
s = replace_once(s, '.navigationTitle("Anki Template")', '.navigationTitle("Шаблон Anki")', "anki title")
s = replace_once(s, '.navigationTitle("Settings")', '.navigationTitle("Настройки")', "settings title")
p.write_text(s)

# ---------- 6. share sheet: valid url + open the link through the host app ----------
p = root / "Shared (iOS)/Globals.swift"
s = p.read_text()
s = replace_once(s, "func jsonSerialize<T: Encodable>(obj: T?) throws -> String {", '''/// `URL(string:)`. If the string is not a valid URL as it is, it is percent-encoded and tried again.
func makeUrl(_ urlString: String) -> URL? {
    if let url = URL(string: urlString) {
        return url
    }
    var allowed = CharacterSet.alphanumerics
    allowed.insert(charactersIn: "-._~:/?#&=+;@$,!*'()%")
    guard let encoded = urlString.addingPercentEncoding(withAllowedCharacters: allowed) else {
        return nil
    }
    return URL(string: encoded)
}

func jsonSerialize<T: Encodable>(obj: T?) throws -> String {''', "makeUrl")
p.write_text(s)

p = root / "Shared (iOS)/YomikiriWebView.swift"
s = p.read_text()
s = replace_once(s, '''                guard let url = URL(string: urlString) else {
                    throw "'openLink' url is not valid: \\(urlString)"''', '''                guard let url = makeUrl(urlString) else {
                    throw "'openLink' url is not valid: \\(urlString)"''', "webview openLink")
p.write_text(s)

p = root / "Yomikiri Action/ActionViewController.swift"
s = p.read_text()
s = replace_once(s, '''                    guard let url = URL(string: urlString) else {
                        throw "'openLink' url is not valid: \\(urlString)"''', '''                    guard let url = makeUrl(urlString) else {
                        throw "'openLink' url is not valid: \\(urlString)"''', "action openLink")
s = regex_replace_once(s, r"    func openURL\(_ url: URL\) \{.*?\n    \}\n", '''    func openURL(_ url: URL) {
        if let ctx = self.extensionContext {
            ctx.open(url, completionHandler: nil)
        }
        // A share extension cannot open another app by itself: ask the host application to do it.
        let selector = NSSelectorFromString("openURL:options:completionHandler:")
        typealias OpenFunction = @convention(c) (AnyObject, Selector, URL, [UIApplication.OpenExternalURLOptionsKey: Any], ((Bool) -> Void)?) -> Void
        var responder: UIResponder? = self
        while let current = responder {
            if current.responds(to: selector), let imp = current.method(for: selector) {
                let function = unsafeBitCast(imp, to: OpenFunction.self)
                function(current, selector, url, [:], nil)
                return
            }
            responder = current.next
        }
    }
''', "action openURL")
p.write_text(s)
print("swift patch OK")
