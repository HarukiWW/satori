# v1.91: the live background can be set up (Настройки → Внешний вид, under «Живой фон»): the number of patches, their
# size and their speed. The background behind the settings shows a change at once.
import pathlib


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")

s = once(s, '''    @AppStorage("ykBackdrop") private var on = true
''', '''    @AppStorage("ykBackdrop") private var on = true
    @AppStorage("ykBackdropCount") private var count = 9
    @AppStorage("ykBackdropSize") private var patchSize = 1.0
    @AppStorage("ykBackdropSpeed") private var speed = 1.0
''', "backdrop settings state")

s = once(s, '''    /// nine small tilted patches, each on its own path (one turn every 50 to 120 s)
    private static let paths: [Path] = {
        var made: [Path] = []
        for i in 0 ..< 9 {
''', '''    /// small tilted patches, each on its own path (one turn every 50 to 120 s at the usual speed)
    private static func paths(_ count: Int) -> [Path] {
        var made: [Path] = []
        for i in 0 ..< min(max(count, 1), 20) {
''', "backdrop paths count")
s = once(s, '''            made.append(Path(sx: sx, sy: sy, phase: k * 0.7 + 0.3, size: size, tilt: tilt))
        }
        return made
    }()
''', '''            made.append(Path(sx: sx, sy: sy, phase: k * 0.7 + 0.3, size: size, tilt: tilt))
        }
        return made
    }
''', "backdrop paths end")

s = once(s, '''    private static func blobs(_ t: Double) -> [Blob] {
        var made: [Blob] = []
        for p in paths {
            let x: Double = 0.5 + 0.6 * sin(t * p.sx + p.phase)
            let y: Double = 0.5 + 0.6 * sin(t * p.sy + p.phase * 1.9)
            let rx: Double = p.size * (1 + 0.2 * sin(t * 0.07 + p.phase))
            let angle: Double = p.tilt + 0.25 * sin(t * 0.05 + p.phase)
            made.append(Blob(x: x, y: y, rx: rx, ry: p.size * 0.5, angle: angle))
        }
        return made
    }
''', '''    private static func blobs(_ t: Double, count: Int, scale: Double, speed: Double) -> [Blob] {
        var made: [Blob] = []
        let pace: Double = t * min(max(speed, 0), 5)
        let grow: Double = min(max(scale, 0.3), 3)
        for p in paths(count) {
            let x: Double = 0.5 + 0.6 * sin(pace * p.sx + p.phase)
            let y: Double = 0.5 + 0.6 * sin(pace * p.sy + p.phase * 1.9)
            let size: Double = p.size * grow
            let rx: Double = size * (1 + 0.2 * sin(pace * 0.07 + p.phase))
            let angle: Double = p.tilt + 0.25 * sin(pace * 0.05 + p.phase)
            made.append(Blob(x: x, y: y, rx: rx, ry: size * 0.5, angle: angle))
        }
        return made
    }
''', "backdrop blobs")
s = once(s, '''        let blobs = SatoriBackdrop.blobs(time)
''', '''        let blobs = SatoriBackdrop.blobs(time, count: count, scale: patchSize, speed: speed)
''', "backdrop draw")

# ---------- Настройки → Внешний вид ----------
s = once(s, '''    @AppStorage("ykBackdrop") private var backdrop = true
''', '''    @AppStorage("ykBackdrop") private var backdrop = true
    @AppStorage("ykBackdropCount") private var backdropCount = 9
    @AppStorage("ykBackdropSize") private var backdropSize = 1.0
    @AppStorage("ykBackdropSpeed") private var backdropSpeed = 1.0
''', "settings backdrop state")
s = once(s, '''                Toggle("Живой фон", isOn: $backdrop)
''', '''                Toggle("Живой фон", isOn: $backdrop)
                if backdrop {
                    Stepper(value: $backdropCount, in: 1 ... 20) {
                        HStack {
                            Text("Пятен")
                            Spacer()
                            Text(String(backdropCount)).foregroundColor(.secondary)
                        }
                    }
                    HStack {
                        Text("Размер")
                        Slider(value: $backdropSize, in: 0.4 ... 2.5, step: 0.1)
                        Text(String(format: "%.1f×", backdropSize))
                            .foregroundColor(.secondary)
                            .frame(width: 44, alignment: .trailing)
                    }
                    HStack {
                        Text("Скорость")
                        Slider(value: $backdropSpeed, in: 0.2 ... 4, step: 0.1)
                        Text(String(format: "%.1f×", backdropSpeed))
                            .foregroundColor(.secondary)
                            .frame(width: 44, alignment: .trailing)
                    }
                    Button("Как было") {
                        backdropCount = 9
                        backdropSize = 1.0
                        backdropSpeed = 1.0
                    }
                    .disabled(backdropCount == 9 && backdropSize == 1.0 && backdropSpeed == 1.0)
                }
''', "settings backdrop controls")
hv.write_text(s, encoding="utf-8")
print("v1.91 backdrop applied")
