# v2.08: faster and smoother, nothing else changes.
# - The live background (it runs at 30 frames a second on every screen, and now in the reader) draws only what is
#   lit: a row no patch reaches is skipped whole, a patch is not weighed where it adds nothing visible (beyond 1.8 of
#   its size), its angle is turned once a frame instead of once a letter, and a letter is resolved only when drawn.
# - The shared storage (the App Groups and the keychain, read on every lookup, list and badge) keeps the last value
#   of each key for a second, and a write updates it at once: a burst of reads costs one. The words of the
#   statistics are parsed once per change of the statistics, not on every call.
# - Motion: the answer of a grammar card unfolds, the next card slides in, a grade gives a light tap; the numbers of
#   «Статистика» roll when the period or the mode changes; the rows that a switch shows or hides in the settings and
#   the rows of the video list move instead of jumping; «Знаю» / «Игнор» in the lists give a tap.
import pathlib


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")

# --- the live background: only what is lit is computed
s = once(s, '''    private struct Blob {
        let x: Double
        let y: Double
        let rx: Double
        let ry: Double
        let angle: Double
    }
''', '''    private struct Blob {
        let x: Double
        let y: Double
        let rx: Double
        let ry: Double
        /// cos and sin of its angle
        let c: Double
        let s: Double
        /// farther than this (in screen widths) it adds nothing visible: exp(-2.2 * 1.8²) < 0.001
        let reach: Double
    }
''', "backdrop blob")
a = s.index("    private func draw(_ ctx: inout GraphicsContext, size: CGSize, time: Double) {")
b = s.index("    private static let fallback = [", a)
s = s[:a] + '''    private func draw(_ ctx: inout GraphicsContext, size: CGSize, time: Double) {
        guard size.width > 0, size.height > 0 else { return }
        let aspect: Double = size.height / size.width
        motion.step(time: time, count: count, aspect: aspect, speed: speed, scale: patchSize)
        let grow: Double = min(max(patchSize, 0.3), 3)
        var blobs: [Blob] = []
        for p in motion.patches {
            let rx: Double = p.size * grow * (1 + 0.15 * sin(time * 0.07 + p.seed * 5))
            let angle: Double = p.tilt + 0.25 * sin(time * 0.05 + p.seed * 3)
            blobs.append(Blob(x: p.x, y: p.y, rx: rx, ry: rx * 0.5, c: cos(angle), s: sin(angle), reach: rx * 1.8))
        }
        // a letter is resolved when it is first drawn: most of the screen stays dark
        var symbols = [GraphicsContext.ResolvedSymbol?](repeating: nil, count: glyphs.count)
        var resolved = [Bool](repeating: false, count: glyphs.count)
        let w = Self.cell.width
        let cols = Int(size.width / w) + 1
        let rows = Int(size.height / Self.cell.height) + 1
        for r in 0 ..< rows {
            let y: Double = (Double(r) + 0.5) * Self.cell.height
            let rowY: Double = y / size.width
            let near = blobs.filter { abs(rowY - $0.y) < $0.reach }
            guard !near.isEmpty else { continue }
            let stream = streams[r % streams.count]
            // every row slides to the left at its own pace, smoothly
            let pace: Double = 4.0 + Double((r * 7) % 5) * 1.5
            let travelled: Double = time * pace
            let steps = Int((travelled / w).rounded(.down))
            let shift: Double = travelled - Double(steps) * w
            for c in 0 ... cols {
                let x: Double = (Double(c) + 0.5) * w - shift
                let level = SatoriBackdrop.field(x / size.width, rowY, near)
                guard level > 0.015 else { continue }
                let index = stream[(c + steps) % stream.count]
                guard index >= 0 else { continue }
                if !resolved[index] {
                    symbols[index] = ctx.resolveSymbol(id: index)
                    resolved[index] = true
                }
                guard let symbol = symbols[index] else { continue }
                ctx.opacity = level * dim
                ctx.draw(symbol, at: CGPoint(x: x, y: y))
            }
        }
    }

    /// How bright the letters are at a point (in screen widths): soft edges, separate patches, a dim maximum.
    private static func field(_ x: Double, _ y: Double, _ blobs: [Blob]) -> Double {
        var sum = 0.0
        for b in blobs {
            let dx: Double = x - b.x
            guard abs(dx) < b.reach else { continue }
            let dy: Double = y - b.y
            let u: Double = (dx * b.c - dy * b.s) / b.rx
            let v: Double = (dx * b.s + dy * b.c) / b.ry
            sum += exp(-(u * u + v * v) * 2.2)
        }
        let level: Double = min(1, max(0, (sum - 0.3) / 0.6))
        return level * level * 0.3
    }

''' + s[b:]

# --- the words of the statistics: parsed once per change
s = once(s, '''    /// Dictionary forms of the words added to Anki: the same list the extension reads (stats.v1).
    static func minedWords() -> Set<String> {
        guard let json = (try? Storage.stats.get())?.data(using: .utf8),
              let root = (try? JSONSerialization.jsonObject(with: json)) as? [String: Any],
              let days = root["days"] as? [String: Any] else { return [] }
''', '''    /// The words of the last statistics parsed (a list asks for them on every redraw).
    private static var wordsCache: (json: String, mined: Set<String>, analysis: Set<String>)? = nil
    private static let wordsLock = NSLock()

    private static func statsWords() -> (mined: Set<String>, analysis: Set<String>) {
        let json: String = (try? Storage.stats.get()) ?? "null"
        wordsLock.lock()
        if let cached = wordsCache, cached.json == json {
            wordsLock.unlock()
            return (cached.mined, cached.analysis)
        }
        wordsLock.unlock()
        let mined = parseMined(json)
        let analysis = parseAnalysis(json, mined: mined)
        wordsLock.lock()
        wordsCache = (json, mined, analysis)
        wordsLock.unlock()
        return (mined, analysis)
    }

    /// Dictionary forms of the words added to Anki: the same list the extension reads (stats.v1).
    static func minedWords() -> Set<String> {
        statsWords().mined
    }

    private static func parseMined(_ text: String) -> Set<String> {
        guard let json = text.data(using: .utf8),
              let root = (try? JSONSerialization.jsonObject(with: json)) as? [String: Any],
              let days = root["days"] as? [String: Any] else { return [] }
''', "mined words")
s = once(s, '''    static func analysisWords() -> Set<String> {
        guard let json = (try? Storage.stats.get())?.data(using: .utf8),
              let root = (try? JSONSerialization.jsonObject(with: json)) as? [String: Any] else { return [] }
        if let mature = root["mature"] as? [String] {
            return Set(mature).union(WordMarks.all(root))
        }
        return root["known"] != nil ? minedWords() : WordMarks.all(root)
    }
''', '''    static func analysisWords() -> Set<String> {
        statsWords().analysis
    }

    private static func parseAnalysis(_ text: String, mined: Set<String>) -> Set<String> {
        guard let json = text.data(using: .utf8),
              let root = (try? JSONSerialization.jsonObject(with: json)) as? [String: Any] else { return [] }
        if let mature = root["mature"] as? [String] {
            return Set(mature).union(WordMarks.all(root))
        }
        return root["known"] != nil ? mined : WordMarks.all(root)
    }
''', "analysis words")

# --- motion
s = once(s, '''struct StatCard: View {
    let title: String
    let value: String

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(value)
                .font(.system(size: 26, weight: .semibold, design: .rounded))
''', '''/// The digits of a number roll to the new value (iOS 16 and newer).
struct RollingNumber: ViewModifier {
    func body(content: Content) -> some View {
        if #available(iOS 16.0, *) {
            content.contentTransition(.numericText())
        } else {
            content
        }
    }
}

struct StatCard: View {
    let title: String
    let value: String

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(value)
                .font(.system(size: 26, weight: .semibold, design: .rounded))
                .modifier(RollingNumber())
''', "stat card rolling")
s = once(s, '''            .animation(.easeInOut(duration: 0.25), value: mode)
''', '''            .animation(.easeInOut(duration: 0.25), value: mode)
            .animation(.easeInOut(duration: 0.25), value: period)
''', "stats period animation")
s = once(s, '''        .id(accent)
''', '''        .id(accent)
        .animation(.default, value: backdrop)
''', "settings animation")
s = once(s, '''            if !status.isEmpty {
                Text(status)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
        }
    }
}
''', '''            if !status.isEmpty {
                Text(status)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
        }
        .animation(.default, value: sync.connected)
    }
}
''', "backup row animation")
s = once(s, '''                    WordMarks.set(word, "known")
''', '''                    WordMarks.set(word, "known")
                    UIImpactFeedbackGenerator(style: .light).impactOccurred()
''', "known tap")
s = once(s, '''                    WordMarks.set(word, "ignored")
''', '''                    WordMarks.set(word, "ignored")
                    UIImpactFeedbackGenerator(style: .light).impactOccurred()
''', "ignored tap")
s = once(s, '''        // the confirmation sits on its own view, apart from the other dialogs of the list
        .background(''', '''        .animation(.default, value: library.items.map { $0.id })
        // the confirmation sits on its own view, apart from the other dialogs of the list
        .background(''', "video list animation")

# the grammar cards
s = once(s, '''                ScrollView {
                    face(point)
                }
                .contentShape(Rectangle())
                .onTapGesture {
                    if !shown {
                        shown = true
                    }
                }''', '''                ScrollView {
                    face(point)
                        .id(point.id)
                        .transition(.asymmetric(insertion: .move(edge: .trailing).combined(with: .opacity),
                                                removal: .opacity))
                }
                .contentShape(Rectangle())
                .onTapGesture {
                    if !shown {
                        withAnimation(.easeOut(duration: 0.22)) {
                            shown = true
                        }
                    }
                }''', "grammar reveal tap")
s = once(s, '''                Button {
                    shown = true
                } label: {
                    Text("Показать ответ")''', '''                Button {
                    withAnimation(.easeOut(duration: 0.22)) {
                        shown = true
                    }
                } label: {
                    Text("Показать ответ")''', "grammar reveal button")
s = once(s, '''            store.answer(point, grade: value)
            advance()''', '''            store.answer(point, grade: value)
            UIImpactFeedbackGenerator(style: .light).impactOccurred()
            withAnimation(.easeInOut(duration: 0.25)) {
                advance()
            }''', "grammar grade motion")
# --- subtitle files: parsed once while the file and the setting of the service text stay the same
s = once(s, '''    /// Cues of an external file (.srt, .vtt, .ass, .ssa).
    static func cues(fromFile url: URL) -> [Cue] {
''', '''    private static let parsedFiles: NSCache<NSString, CueFileBox> = {
        let cache = NSCache<NSString, CueFileBox>()
        cache.countLimit = 80
        return cache
    }()

    /// Cues of an external file (.srt, .vtt, .ass, .ssa). A file is read again only when it changed (or the setting
    /// of the service text did): the lists, the analysis and the notes of a folder read the same files many times.
    static func cues(fromFile url: URL) -> [Cue] {
        let values = try? url.resourceValues(forKeys: [.contentModificationDateKey, .fileSizeKey])
        let stamp: Double = values?.contentModificationDate?.timeIntervalSince1970 ?? 0
        let strip: Bool = UserDefaults.standard.object(forKey: "ykStripSDH") as? Bool ?? true
        let key: String = url.path + "|" + String(stamp) + "|" + String(values?.fileSize ?? -1) + (strip ? "|s" : "|k")
        if let saved = parsedFiles.object(forKey: key as NSString) {
            return saved.cues
        }
        let cues = parseCues(fromFile: url)
        parsedFiles.setObject(CueFileBox(cues), forKey: key as NSString)
        return cues
    }

    private static func parseCues(fromFile url: URL) -> [Cue] {
''', "cue cache")
s = s.rstrip("\n") + '''

/// The cues of one subtitle file in EmbeddedSubtitles' cache.
final class CueFileBox {
    let cues: [EmbeddedSubtitles.Cue]

    init(_ cues: [EmbeddedSubtitles.Cue]) {
        self.cues = cues
    }
}

/// Whether the text has one of these characters (a regular expression that needs one of them is skipped without).
func hasAnyScalar(_ text: String, of marks: String) -> Bool {
    text.unicodeScalars.contains { marks.unicodeScalars.contains($0) }
}
'''

# --- regular expressions only where they can match (the same result, without compiling them for nothing)
s = once(s, r'''        out = out.replacingOccurrences(of: "\\{[^}]*\\}", with: "", options: .regularExpression)
        out = out.replacingOccurrences(of: "<[^>]+>", with: "", options: .regularExpression)
''', r'''        if hasAnyScalar(out, of: "{") {
            out = out.replacingOccurrences(of: "\\{[^}]*\\}", with: "", options: .regularExpression)
        }
        if hasAnyScalar(out, of: "<") {
            out = out.replacingOccurrences(of: "<[^>]+>", with: "", options: .regularExpression)
        }
''', "cue clean")
s = once(s, r'''        s = s.replacingOccurrences(of: "[［\\[][^［\\[\\]］]{0,40}[］\\]]", with: "", options: .regularExpression)
''', r'''        if hasAnyScalar(s, of: "［[") {
            s = s.replacingOccurrences(of: "[［\\[][^［\\[\\]］]{0,40}[］\\]]", with: "", options: .regularExpression)
        }
''', "sdh brackets")
s = once(s, r'''        s = s.replacingOccurrences(of: "^\\s*[（(][^（()）ぁ-ゖ。、！？…!?]{1,12}[）)]\\s*(?=\\S)", with: "",
                                   options: .regularExpression)
''', r'''        if hasAnyScalar(s, of: "（(") {
            s = s.replacingOccurrences(of: "^\\s*[（(][^（()）ぁ-ゖ。、！？…!?]{1,12}[）)]\\s*(?=\\S)", with: "",
                                       options: .regularExpression)
        }
''', "sdh speaker")
s = once(s, '''        s = s.replacingOccurrences(of: "[♪♫♬]", with: "", options: .regularExpression)
''', '''        if hasAnyScalar(s, of: "♪♫♬") {
            s = s.replacingOccurrences(of: "[♪♫♬]", with: "", options: .regularExpression)
        }
''', "sdh notes")
s = once(s, '''        s = s.replacingOccurrences(of: "[≪≫《》＜＞→➡]", with: "", options: .regularExpression)
''', '''        if hasAnyScalar(s, of: "≪≫《》＜＞→➡") {
            s = s.replacingOccurrences(of: "[≪≫《》＜＞→➡]", with: "", options: .regularExpression)
        }
''', "sdh marks")
s = once(s, r'''    static func clean(_ text: String) -> String {
        var s = text.replacingOccurrences(of: "<[^>]+>", with: "", options: .regularExpression)
        s = s.replacingOccurrences(of: "\\[[^\\]]*\\]", with: "", options: .regularExpression)
        s = s.replacingOccurrences(of: "&nbsp;", with: "")
        return s.components(separatedBy: .whitespacesAndNewlines).joined()
    }
''', r'''    static func clean(_ text: String) -> String {
        var s = text
        if hasAnyScalar(s, of: "<") {
            s = s.replacingOccurrences(of: "<[^>]+>", with: "", options: .regularExpression)
        }
        if hasAnyScalar(s, of: "[") {
            s = s.replacingOccurrences(of: "\\[[^\\]]*\\]", with: "", options: .regularExpression)
        }
        if hasAnyScalar(s, of: "&") {
            s = s.replacingOccurrences(of: "&nbsp;", with: "")
        }
        guard s.unicodeScalars.contains(where: { CharacterSet.whitespacesAndNewlines.contains($0) }) else { return s }
        return s.components(separatedBy: .whitespacesAndNewlines).joined()
    }
''', "known words clean")
s = once(s, r'''        word = word.replacingOccurrences(of: "<[^>]*>", with: "", options: .regularExpression)
        word = word.replacingOccurrences(of: "\\[[^\\]]*\\]", with: "", options: .regularExpression)
        return word.components(separatedBy: .whitespacesAndNewlines).joined()
''', r'''        if hasAnyScalar(word, of: "<") {
            word = word.replacingOccurrences(of: "<[^>]*>", with: "", options: .regularExpression)
        }
        if hasAnyScalar(word, of: "[") {
            word = word.replacingOccurrences(of: "\\[[^\\]]*\\]", with: "", options: .regularExpression)
        }
        return word.components(separatedBy: .whitespacesAndNewlines).joined()
''', "queue stats word")

# --- file names of the video rows: parsed once per name (every redraw of a list asked again)
s = once(s, '''    static func parse(_ file: String) -> Parsed {
        let s = clean(file)
''', '''    private static let namesLock = NSLock()
    private static var parsedNames: [String: Parsed] = [:]
    private static var tags: [String: String?] = [:]

    /// The title and the episode of a file name, kept per name.
    static func parse(_ file: String) -> Parsed {
        namesLock.lock()
        let saved = parsedNames[file]
        namesLock.unlock()
        if let saved {
            return saved
        }
        let result = parseName(file)
        namesLock.lock()
        if parsedNames.count > 4000 {
            parsedNames.removeAll()
        }
        parsedNames[file] = result
        namesLock.unlock()
        return result
    }

    private static func parseName(_ file: String) -> Parsed {
        let s = clean(file)
''', "names cache")
s = once(s, '''    static func episodeTag(_ file: String) -> String? {
        guard let episode = parse(file).episode else { return nil }
''', '''    static func episodeTag(_ file: String) -> String? {
        namesLock.lock()
        let saved = tags[file]
        namesLock.unlock()
        if let saved {
            return saved
        }
        let tag = makeTag(file)
        namesLock.lock()
        if tags.count > 4000 {
            tags.removeAll()
        }
        tags[file] = tag
        namesLock.unlock()
        return tag
    }

    private static func makeTag(_ file: String) -> String? {
        guard let episode = parse(file).episode else { return nil }
''', "tags cache")

# --- the titles of the days of «Добавленные слова»: one formatter
s = once(s, '''    let formatter = DateFormatter()
    formatter.locale = Locale(identifier: "ru_RU")
    formatter.dateFormat = "d MMMM yyyy"
    return formatter.string(from: date)
''', '''    return statDayTitleFormatter.string(from: date)
''', "day title formatter")
s = once(s, '''private let statWeekdayFormatter: DateFormatter = {''', '''private let statDayTitleFormatter: DateFormatter = {
    let formatter = DateFormatter()
    formatter.locale = Locale(identifier: "ru_RU")
    formatter.dateFormat = "d MMMM yyyy"
    return formatter
}()

private let statWeekdayFormatter: DateFormatter = {''', "day title formatter declaration")
hv.write_text(s, encoding="utf-8")

# --- the shared storage: the last value of each key for a second
ut = pathlib.Path("src/safari/YomikiriTokenizer/YomikiriTokenizer/Utils.swift")
u = ut.read_text(encoding="utf-8")
u = once(u, '''func sharedStoreRead(_ key: String) -> String? {
    var best: SharedValue?
''', '''/// The last value of each key read or written by this process, and when (uptime): reads within a second take it.
private let sharedReadLock = NSLock()
private var sharedReadCache: [String: (value: String?, time: Double)] = [:]

private func sharedRemember(_ key: String, _ value: String?) {
    sharedReadLock.lock()
    sharedReadCache[key] = (value: value, time: ProcessInfo.processInfo.systemUptime)
    sharedReadLock.unlock()
}

func sharedStoreRead(_ key: String) -> String? {
    sharedReadLock.lock()
    let cached = sharedReadCache[key]
    sharedReadLock.unlock()
    if let cached, ProcessInfo.processInfo.systemUptime - cached.time < 1 {
        return cached.value
    }
    let value = sharedStoreNewest(key)
    sharedRemember(key, value)
    return value
}

private func sharedStoreNewest(_ key: String) -> String? {
    var best: SharedValue?
''', "shared read cache")
u = once(u, '''func sharedStoreWrite(_ key: String, _ value: String?) {
    let ts = Date().timeIntervalSince1970
''', '''func sharedStoreWrite(_ key: String, _ value: String?) {
    sharedRemember(key, value)
    let ts = Date().timeIntervalSince1970
''', "shared write cache")
ut.write_text(u, encoding="utf-8")
print("v2.08 speed and motion applied")
