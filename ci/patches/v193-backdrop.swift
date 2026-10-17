/// The patches of the live background: each wanders on its own, keeps away from the others and from the edges (now
/// and then two meet or one touches an edge), so they spread over the whole screen. Places are in screen widths:
/// x from 0 to 1, y from 0 to the height divided by the width.
final class BackdropMotion {
    struct Patch {
        var x: Double
        var y: Double
        var vx: Double = 0
        var vy: Double = 0
        /// the radius across, in screen widths
        let size: Double
        let tilt: Double
        let seed: Double
    }

    private(set) var patches: [Patch] = []
    private var last: Double = 0

    /// The patches spread over the screen at the start (a grid with a little shake).
    private func spread(_ count: Int, aspect: Double) {
        let columns = max(1, Int((Double(count) / max(aspect, 0.5)).squareRoot().rounded()))
        let rows = max(1, (count + columns - 1) / columns)
        var made: [Patch] = []
        for i in 0 ..< count {
            let k = Double(i)
            let column = Double(i % columns)
            let row = Double(i / columns)
            let x: Double = (column + 0.5 + 0.3 * sin(k * 2.3)) / Double(columns)
            let y: Double = (row + 0.5 + 0.3 * cos(k * 1.7)) / Double(rows) * aspect
            let size: Double = 0.26 + 0.04 * Double((i * 2) % 4)
            made.append(Patch(x: x, y: y, size: size, tilt: -0.4 - 0.08 * Double(i % 4), seed: k * 0.618))
        }
        patches = made
    }

    /// The push of an edge at `distance` from it: none farther than `margin`, strong at the edge.
    private static func edge(_ distance: Double, _ margin: Double) -> Double {
        guard distance < margin else { return 0 }
        let inside: Double = (margin - distance) / margin
        return inside * inside * 0.35
    }

    func step(time: Double, count: Int, aspect: Double, speed: Double, scale: Double) {
        let wanted = min(max(count, 1), 20)
        if patches.count != wanted {
            spread(wanted, aspect: aspect)
            last = time
            return
        }
        // a frame after a pause (another tab, the app in the background) moves as one short frame
        let dt: Double = min(0.1, max(0, time - last))
        last = time
        guard dt > 0 else { return }
        let pace: Double = min(max(speed, 0), 5)
        let cruise: Double = 0.05 * pace
        let grow: Double = min(max(scale, 0.3), 3)
        let margin: Double = 0.14
        let old = patches
        for i in patches.indices {
            var p = old[i]
            // a heading that turns slowly, its own for every patch
            let heading: Double = p.seed * 6.28 + 1.3 * sin(time * 0.11 + p.seed * 9) + 0.8 * sin(time * 0.067 + p.seed * 4)
            var ax: Double = (cos(heading) * cruise - p.vx) * 0.8
            var ay: Double = (sin(heading) * cruise - p.vy) * 0.8
            // the others push it away while they overlap
            for j in old.indices where j != i {
                let q = old[j]
                let dx: Double = p.x - q.x
                let dy: Double = p.y - q.y
                let distance: Double = max(0.001, (dx * dx + dy * dy).squareRoot())
                let reach: Double = (p.size + q.size) * grow * 0.9
                guard distance < reach else { continue }
                let overlap: Double = 1 - distance / reach
                let push: Double = overlap * overlap * 0.3 * max(pace, 0.3)
                ax += dx / distance * push
                ay += dy / distance * push
            }
            // the edges push it back in
            ax += (BackdropMotion.edge(p.x, margin) - BackdropMotion.edge(1 - p.x, margin)) * max(pace, 0.3)
            ay += (BackdropMotion.edge(p.y, margin) - BackdropMotion.edge(aspect - p.y, margin)) * max(pace, 0.3)
            p.vx += ax * dt
            p.vy += ay * dt
            let fastest: Double = cruise * 3 + 0.01
            let moving: Double = (p.vx * p.vx + p.vy * p.vy).squareRoot()
            if moving > fastest {
                p.vx *= fastest / moving
                p.vy *= fastest / moving
            }
            p.x = min(max(p.x + p.vx * dt, -0.1), 1.1)
            p.y = min(max(p.y + p.vy * dt, -0.1), aspect + 0.1)
            patches[i] = p
        }
    }
}

@available(iOS 16.0, *)
struct SatoriBackdrop: View {
    @AppStorage("ykBackdrop") private var on = true
    @AppStorage("ykBackdropCount") private var count = 9
    @AppStorage("ykBackdropSize") private var patchSize = 1.0
    @AppStorage("ykBackdropSpeed") private var speed = 1.0
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    /// the letters, each drawn once as a symbol
    @State private var glyphs: [Character] = []
    /// rows of letters (indexes into glyphs, -1 a space between words)
    @State private var streams: [[Int]] = []
    @State private var motion = BackdropMotion()
    /// only the background on screen is drawn (every tab has its own)
    @State private var visible = false

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
                TimelineView(.animation(minimumInterval: 1.0 / 30, paused: reduceMotion || !visible)) { context in
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
        .onAppear {
            load()
            visible = true
        }
        .onDisappear {
            visible = false
        }
    }

    private func draw(_ ctx: inout GraphicsContext, size: CGSize, time: Double) {
        guard size.width > 0, size.height > 0 else { return }
        let aspect: Double = size.height / size.width
        motion.step(time: time, count: count, aspect: aspect, speed: speed, scale: patchSize)
        let grow: Double = min(max(patchSize, 0.3), 3)
        var blobs: [Blob] = []
        for p in motion.patches {
            let rx: Double = p.size * grow * (1 + 0.15 * sin(time * 0.07 + p.seed * 5))
            let angle: Double = p.tilt + 0.25 * sin(time * 0.05 + p.seed * 3)
            blobs.append(Blob(x: p.x, y: p.y, rx: rx, ry: rx * 0.5, angle: angle))
        }
        let symbols = glyphs.indices.map { ctx.resolveSymbol(id: $0) }
        let w = Self.cell.width
        let cols = Int(size.width / w) + 1
        let rows = Int(size.height / Self.cell.height) + 1
        for r in 0 ..< rows {
            let y: Double = (Double(r) + 0.5) * Self.cell.height
            let stream = streams[r % streams.count]
            // every row slides to the left at its own pace, smoothly
            let pace: Double = 4.0 + Double((r * 7) % 5) * 1.5
            let travelled: Double = time * pace
            let steps = Int((travelled / w).rounded(.down))
            let shift: Double = travelled - Double(steps) * w
            for c in 0 ... cols {
                let x: Double = (Double(c) + 0.5) * w - shift
                let level = SatoriBackdrop.field(x / size.width, y / size.width, blobs)
                guard level > 0.015 else { continue }
                let index = stream[(c + steps) % stream.count]
                guard index >= 0, let symbol = symbols[index] else { continue }
                ctx.opacity = level
                ctx.draw(symbol, at: CGPoint(x: x, y: y))
            }
        }
    }

    /// How bright the letters are at a point (in screen widths): soft edges, separate patches, a dim maximum.
    private static func field(_ x: Double, _ y: Double, _ blobs: [Blob]) -> Double {
        var sum = 0.0
        for b in blobs {
            let dx: Double = x - b.x
            let dy: Double = y - b.y
            let c: Double = cos(b.angle)
            let s: Double = sin(b.angle)
            let u: Double = (dx * c - dy * s) / b.rx
            let v: Double = (dx * s + dy * c) / b.ry
            sum += exp(-(u * u + v * v) * 2.2)
        }
        let level: Double = min(1, max(0, (sum - 0.3) / 0.6))
        return level * level * 0.3
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
