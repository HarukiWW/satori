
// MARK: - Satori v1.86: subtitles without the service text, word marks, the live background

/// The service text of subtitles for the deaf (SDH): who speaks （ルンゲ）, sounds ［銃声］ （笑い声）, ♪, the arrows of
/// a line that goes on, the marks of a voice from a phone ≪ ≫. Thoughts in （ ） stay: they are sentences with
/// hiragana, while names and sounds are written without it or end with 音 / 声.
enum SDHText {
    static func strip(_ text: String) -> String {
        text.components(separatedBy: "\n").map(stripLine).filter { !$0.isEmpty }.joined(separator: "\n")
    }

    private static let soundEnds = ["音", "声", "笑い", "息", "拍手", "悲鳴", "歓声", "咳", "ノック", "チャイム", "ベル",
                                    "サイレン", "足音", "鳴き声", "ため息"]

    private static func hasHiragana(_ text: String) -> Bool {
        text.unicodeScalars.contains { (0x3041 ... 0x3096).contains($0.value) }
    }

    private static func stripLine(_ raw: String) -> String {
        var s = raw
        // ［銃声］ [door opens]
        s = s.replacingOccurrences(of: "[［\\[][^［\\[\\]］]{0,40}[］\\]]", with: "", options: .regularExpression)
        // （ルンゲ）しかし… : the speaker before the words
        s = s.replacingOccurrences(of: "^\\s*[（(][^（()）ぁ-ゖ。、！？…!?]{1,12}[）)]\\s*(?=\\S)", with: "",
                                   options: .regularExpression)
        // a whole line in （ ）: a sound or a speaker alone, not a thought
        let trimmed = s.trimmingCharacters(in: .whitespaces)
        if trimmed.count >= 2, "（(".contains(trimmed.first!), "）)".contains(trimmed.last!) {
            let inner = String(trimmed.dropFirst().dropLast())
            if !inner.contains(where: { "（()）".contains($0) }),
               !hasHiragana(inner) || soundEnds.contains(where: { inner.hasSuffix($0) }) {
                return ""
            }
        }
        s = s.replacingOccurrences(of: "[♪♫♬]", with: "", options: .regularExpression)
        // ≪電話の声≫ ＜心の声＞: the marks go, the words stay; → of a line that goes on
        s = s.replacingOccurrences(of: "[≪≫《》＜＞→➡]", with: "", options: .regularExpression)
        s = s.trimmingCharacters(in: .whitespaces)
        // what is left of a song line
        if s.allSatisfy({ "～〜ー・ ".contains($0) }) {
            return ""
        }
        return s
    }
}

/// Words marked by hand: "Знаю" (known without a card) and "Игнор" (not a word to learn: a name, a sound, a wrong
/// split). Kept in the shared statistics (stats.v1: "manualKnown", "ignored"), apart from the words of Anki, so the
/// removal of imported words leaves them.
enum WordMarks {
    static func all(_ root: [String: Any]) -> Set<String> {
        Set(((root["manualKnown"] as? [String]) ?? []) + ((root["ignored"] as? [String]) ?? []))
    }

    private static func load() -> [String: Any]? {
        guard let json = try? Storage.stats.get(), let data = json.data(using: .utf8) else { return [:] }
        if json == "null" {
            return [:]
        }
        // unreadable statistics are not written over
        return (try? JSONSerialization.jsonObject(with: data)) as? [String: Any]
    }

    private static func save(_ root: [String: Any]) {
        guard let out = try? JSONSerialization.data(withJSONObject: root),
              let text = String(data: out, encoding: .utf8) else { return }
        _ = try? Storage.stats.set(text)
    }

    static func count() -> Int {
        guard let root = load() else { return 0 }
        return all(root).count
    }

    /// "known", "ignored", or nil to take the mark away.
    static func set(_ word: String, _ kind: String?) {
        guard !word.isEmpty, var root = load() else { return }
        var known = ((root["manualKnown"] as? [String]) ?? []).filter { $0 != word }
        var ignored = ((root["ignored"] as? [String]) ?? []).filter { $0 != word }
        if kind == "known" {
            known.append(word)
        } else if kind == "ignored" {
            ignored.append(word)
        }
        root["manualKnown"] = known
        root["ignored"] = ignored
        if root["days"] == nil {
            root["days"] = [String: Any]()
        }
        save(root)
    }

    static func clear() {
        guard var root = load() else { return }
        root["manualKnown"] = [String]()
        root["ignored"] = [String]()
        save(root)
    }
}

/// Swipe right "Знаю", left "Игнор" in a list of unknown words.
struct WordMarkSwipes: ViewModifier {
    let word: String
    let changed: () -> Void

    func body(content: Content) -> some View {
        content
            .swipeActions(edge: .leading, allowsFullSwipe: true) {
                Button {
                    WordMarks.set(word, "known")
                    changed()
                } label: {
                    Label("Знаю", systemImage: "checkmark")
                }
                .tint(.green)
            }
            .swipeActions(edge: .trailing, allowsFullSwipe: true) {
                Button {
                    WordMarks.set(word, "ignored")
                    changed()
                } label: {
                    Label("Игнор", systemImage: "eye.slash")
                }
                .tint(.gray)
            }
    }
}

/// Настройки → Anki: the marks "Знаю" and "Игнор" can be reset.
struct MarksResetRow: View {
    @State private var count = 0
    @State private var confirm = false

    var body: some View {
        Group {
            if count > 0 {
                Button("Сбросить отметки «Знаю» и «Игнор» (" + String(count) + ")", role: .destructive) {
                    confirm = true
                }
                .alert("Сбросить отметки?", isPresented: $confirm) {
                    Button("Сбросить", role: .destructive) {
                        WordMarks.clear()
                        count = 0
                    }
                    Button("Отмена", role: .cancel) {}
                } message: {
                    Text("Отмеченные слова снова будут считаться незнакомыми.")
                }
            }
        }
        .onAppear {
            count = WordMarks.count()
        }
    }
}

/// The background of the main screens: words and kanji of your cards in a dim grid, shown only inside soft patches
/// that drift slowly across the screen (Настройки → Внешний вид → «Живой фон»).
struct SatoriBackdrop: View {
    @AppStorage("ykBackdrop") private var on = true
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    /// the letters, each drawn once as a symbol
    @State private var glyphs: [Character] = []
    /// rows of letters (indexes into glyphs, -1 a space between words)
    @State private var streams: [[Int]] = []

    private static let cell = CGSize(width: 15, height: 19)

    private struct Blob {
        let x: Double
        let y: Double
        let rx: Double
        let ry: Double
        let angle: Double
    }

    var body: some View {
        ZStack {
            Color.black
            if on && !streams.isEmpty {
                TimelineView(.periodic(from: .now, by: reduceMotion ? 3600 : 1.0 / 15)) { context in
                    let time = context.date.timeIntervalSinceReferenceDate
                    Canvas { ctx, size in
                        draw(&ctx, size: size, time: time)
                    } symbols: {
                        ForEach(glyphs.indices, id: \.self) { i in
                            Text(String(glyphs[i]))
                                .font(.system(size: 12))
                                .foregroundColor(.white)
                                .tag(i)
                        }
                    }
                }
            }
        }
        .ignoresSafeArea()
        .allowsHitTesting(false)
        .onAppear(perform: load)
    }

    private func draw(_ ctx: inout GraphicsContext, size: CGSize, time: Double) {
        guard size.width > 0, size.height > 0 else { return }
        let symbols = glyphs.indices.map { ctx.resolveSymbol(id: $0) }
        let blobs = SatoriBackdrop.blobs(time)
        let aspect = size.height / size.width
        let cols = Int(size.width / Self.cell.width) + 1
        let rows = Int(size.height / Self.cell.height) + 1
        for r in 0 ..< rows {
            let y = (Double(r) + 0.5) * Self.cell.height
            let stream = streams[r % streams.count]
            // the words of a row move on by a few letters now and then, each row at its own time
            let shift = Int((time / 23 + Double(r) * 0.61).rounded(.down)) * 7
            for c in 0 ..< cols {
                let x = (Double(c) + 0.5) * Self.cell.width
                let level = SatoriBackdrop.field(x / size.width, y / size.height, aspect: aspect, blobs)
                guard level > 0.015 else { continue }
                let index = stream[(c + shift) % stream.count]
                guard index >= 0, let symbol = symbols[index] else { continue }
                ctx.opacity = level
                ctx.draw(symbol, at: CGPoint(x: x, y: y))
            }
        }
    }

    /// Four soft tilted patches on slow paths (one turn every one to two minutes).
    private static func blobs(_ t: Double) -> [Blob] {
        let paths: [(sx: Double, sy: Double, phase: Double, size: Double, tilt: Double)] = [
            (0.011, 0.017, 0.0, 0.42, -0.5), (0.013, 0.009, 2.1, 0.36, -0.7),
            (0.007, 0.012, 4.2, 0.48, -0.4), (0.015, 0.011, 5.3, 0.30, -0.6),
        ]
        return paths.map { p in
            Blob(x: 0.5 + 0.45 * sin(t * p.sx + p.phase),
                 y: 0.5 + 0.45 * sin(t * p.sy + p.phase * 1.7),
                 rx: p.size * (1 + 0.25 * sin(t * 0.02 + p.phase)),
                 ry: p.size * 0.45,
                 angle: p.tilt + 0.15 * sin(t * 0.01 + p.phase))
        }
    }

    /// How bright the letters are at a point (x and y from 0 to 1): soft edges, a dim maximum.
    private static func field(_ x: Double, _ y: Double, aspect: Double, _ blobs: [Blob]) -> Double {
        var sum = 0.0
        for b in blobs {
            let dx = x - b.x
            let dy = (y - b.y) * aspect
            let c = cos(b.angle)
            let s = sin(b.angle)
            let u = (dx * c - dy * s) / b.rx
            let v = (dx * s + dy * c) / b.ry
            sum += exp(-(u * u + v * v) * 2)
        }
        let level = min(1, max(0, (sum - 0.25) / 0.75))
        return level * level * 0.26
    }

    private static let fallback = [
        "日本語", "言葉", "漢字", "勉強", "物語", "世界", "時間", "記憶", "未来", "心", "夢", "空", "光", "影", "声",
        "道", "風", "海", "星", "雨", "桜", "季節", "約束", "名前", "ことば", "よむ", "きく", "みる", "かく", "はなす",
        "わかる", "おもう", "まなぶ", "ひかり", "しずか", "やさしい", "たのしい", "ゆめ", "そら", "こころ",
    ]

    private func load() {
        guard streams.isEmpty else { return }
        var words = HighlightData.minedWords().map { KnownWordsIndex.clean($0) }
            .filter { (1 ... 6).contains($0.count) && $0.unicodeScalars.allSatisfy { KnownWordsIndex.isJapanese($0) } }
        words.shuffle()
        // a few hundred letters at most: every one is a symbol of the canvas
        words = Array(words.prefix(150))
        if words.count < 40 {
            words += SatoriBackdrop.fallback.shuffled()
        }
        var index: [Character: Int] = [:]
        var letters: [Character] = []
        var made: [[Int]] = []
        for r in 0 ..< 24 {
            var row: [Int] = []
            var k = r * 7
            while row.count < 160 {
                for letter in words[k % words.count] {
                    if index[letter] == nil {
                        index[letter] = letters.count
                        letters.append(letter)
                    }
                    row.append(index[letter]!)
                }
                row.append(-1)
                if k % 3 == 0 {
                    row.append(-1)
                }
                k += 1
            }
            made.append(row)
        }
        glyphs = letters
        streams = made
    }
}

extension View {
    /// The live background under a list: the list itself turns transparent (iOS 16 and newer).
    @ViewBuilder
    func satoriBackdrop() -> some View {
        if #available(iOS 16.0, *) {
            scrollContentBackground(.hidden)
                .background(SatoriBackdrop())
        } else {
            self
        }
    }
}
