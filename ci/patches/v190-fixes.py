# v1.90:
# - The folder of the backups of AnkiMobile is chosen in the system picker of UIKit (the SwiftUI file importer
#   inside a row of the settings form opened, but never gave the folder back).
# - The live background: small patches as in 1.88, but nine of them and moving faster; the rows of letters slide
#   smoothly instead of jumping by a few letters; 30 frames a second.
import pathlib


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")

# ---------- the folder picker ----------
s = once(s, '''            .fileImporter(isPresented: $picking, allowedContentTypes: [.folder]) { result in
                if case .success(let url) = result {
                    sync.choose(url)
                }
            }
''', '''            .sheet(isPresented: $picking) {
                FolderPicker(onPick: { url in
                    picking = false
                    sync.choose(url)
                }, onCancel: {
                    picking = false
                })
                .ignoresSafeArea()
            }
''', "folder picker")
s = once(s, '''        UserDefaults.standard.set(data, forKey: bookmarkKey)
        UserDefaults.standard.removeObject(forKey: doneKey)
        objectWillChange.send()
        check()
''', '''        UserDefaults.standard.set(data, forKey: bookmarkKey)
        UserDefaults.standard.removeObject(forKey: doneKey)
        status = "Папка «" + folder.lastPathComponent + "» выбрана"
        objectWillChange.send()
        check()
''', "folder chosen status")

# ---------- the background ----------
start = s.index("@available(iOS 16.0, *)\nstruct SatoriBackdrop: View {")
end = s.index("\nextension View {\n    /// The live background under a list")
s = s[:start] + '''@available(iOS 16.0, *)
struct SatoriBackdrop: View {
    @AppStorage("ykBackdrop") private var on = true
    @Environment(\\.accessibilityReduceMotion) private var reduceMotion
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

    /// nine small tilted patches, each on its own path (one turn every 50 to 120 s)
    private static let paths: [(sx: Double, sy: Double, phase: Double, size: Double, tilt: Double)] = (0 ..< 9).map { i in
        (0.05 + 0.013 * Double((i * 5) % 7), 0.06 + 0.011 * Double((i * 3) % 7), Double(i) * 0.7 + 0.3,
         0.26 + 0.04 * Double((i * 2) % 4), -0.4 - 0.08 * Double(i % 4))
    }

    var body: some View {
        ZStack {
            Color.black
            if on && !streams.isEmpty {
                TimelineView(.animation(minimumInterval: 1.0 / 30, paused: reduceMotion)) { context in
                    let time = context.date.timeIntervalSinceReferenceDate
                    Canvas { ctx, size in
                        draw(&ctx, size: size, time: time)
                    } symbols: {
                        ForEach(glyphs.indices, id: \\.self) { i in
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
        let w = Self.cell.width
        let cols = Int(size.width / w) + 1
        let rows = Int(size.height / Self.cell.height) + 1
        for r in 0 ..< rows {
            let y = (Double(r) + 0.5) * Self.cell.height
            let stream = streams[r % streams.count]
            // every row slides to the left at its own pace, smoothly
            let travelled = time * (4.0 + Double((r * 7) % 5) * 1.5)
            let steps = Int((travelled / w).rounded(.down))
            let shift = travelled - Double(steps) * w
            for c in 0 ... cols {
                let x = (Double(c) + 0.5) * w - shift
                let level = SatoriBackdrop.field(x / size.width, y / size.height, aspect: aspect, blobs)
                guard level > 0.015 else { continue }
                let index = stream[(c + steps) % stream.count]
                guard index >= 0, let symbol = symbols[index] else { continue }
                ctx.opacity = level
                ctx.draw(symbol, at: CGPoint(x: x, y: y))
            }
        }
    }

    private static func blobs(_ t: Double) -> [Blob] {
        paths.map { p in
            Blob(x: 0.5 + 0.6 * sin(t * p.sx + p.phase),
                 y: 0.5 + 0.6 * sin(t * p.sy + p.phase * 1.9),
                 rx: p.size * (1 + 0.2 * sin(t * 0.07 + p.phase)),
                 ry: p.size * 0.5,
                 angle: p.tilt + 0.25 * sin(t * 0.05 + p.phase))
        }
    }

    /// How bright the letters are at a point (x and y from 0 to 1): soft edges, separate patches, a dim maximum.
    private static func field(_ x: Double, _ y: Double, aspect: Double, _ blobs: [Blob]) -> Double {
        var sum = 0.0
        for b in blobs {
            let dx = x - b.x
            let dy = (y - b.y) * aspect
            let c = cos(b.angle)
            let s = sin(b.angle)
            let u = (dx * c - dy * s) / b.rx
            let v = (dx * s + dy * c) / b.ry
            sum += exp(-(u * u + v * v) * 2.2)
        }
        let level = min(1, max(0, (sum - 0.3) / 0.6))
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
''' + s[end:]

s = s.rstrip("\n") + '''

/// The system picker of a folder: the folder stays where it is (its URL is security-scoped).
struct FolderPicker: UIViewControllerRepresentable {
    let onPick: (URL) -> Void
    let onCancel: () -> Void

    func makeCoordinator() -> Coordinator { Coordinator(onPick: onPick, onCancel: onCancel) }

    func makeUIViewController(context: Context) -> UIDocumentPickerViewController {
        let picker = UIDocumentPickerViewController(forOpeningContentTypes: [.folder], asCopy: false)
        picker.allowsMultipleSelection = false
        picker.delegate = context.coordinator
        return picker
    }

    func updateUIViewController(_ controller: UIDocumentPickerViewController, context: Context) {}

    final class Coordinator: NSObject, UIDocumentPickerDelegate {
        let onPick: (URL) -> Void
        let onCancel: () -> Void

        init(onPick: @escaping (URL) -> Void, onCancel: @escaping () -> Void) {
            self.onPick = onPick
            self.onCancel = onCancel
        }

        func documentPicker(_ controller: UIDocumentPickerViewController, didPickDocumentsAt urls: [URL]) {
            if let url = urls.first {
                onPick(url)
            }
        }

        func documentPickerWasCancelled(_ controller: UIDocumentPickerViewController) {
            onCancel()
        }
    }
}
'''
hv.write_text(s, encoding="utf-8")
print("v1.90 fixes applied")
