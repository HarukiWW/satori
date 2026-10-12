# Moved out of build-ios-v141-player.yml, step "Interpolation test (VideoToolbox, iOS 26) in the player settings" (GitHub limits workflow files to 500 KB).
import pathlib

def replace_once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)

PROBE = r'''/// Test of the system frame interpolation (VideoToolbox, iOS 26). The step before every risky call is saved,
/// so after a crash the next start shows where it stopped.
enum InterpolationProbe {
    static let stepKey = "interpProbe.step"

    static func mark(_ step: String?) {
        let defaults = UserDefaults.standard
        if let step { defaults.set(step, forKey: stepKey) } else { defaults.removeObject(forKey: stepKey) }
        defaults.synchronize()
    }

    static func unfinishedStep() -> String? {
        UserDefaults.standard.string(forKey: stepKey)
    }

    static func fourCC(_ value: UInt32) -> String {
        let bytes = [UInt8((value >> 24) & 0xFF), UInt8((value >> 16) & 0xFF), UInt8((value >> 8) & 0xFF), UInt8(value & 0xFF)]
        let text = String(bytes: bytes, encoding: .ascii) ?? ""
        return text.trimmingCharacters(in: .controlCharacters).isEmpty ? String(format: "0x%08X", value) : text
    }

    /// Reads an Objective-C property by its name (the Swift names of these properties differ).
    static func value(_ object: NSObject, _ key: String) -> Any? {
        guard object.responds(to: NSSelectorFromString(key)) else { return nil }
        return object.value(forKey: key)
    }

    static func makeBuffer(_ width: Int, _ height: Int, _ format: OSType, _ attributes: [String: Any]) -> CVPixelBuffer? {
        var attrs = attributes
        attrs.removeValue(forKey: kCVPixelBufferPixelFormatTypeKey as String)
        attrs.removeValue(forKey: kCVPixelBufferWidthKey as String)
        attrs.removeValue(forKey: kCVPixelBufferHeightKey as String)
        if attrs[kCVPixelBufferIOSurfacePropertiesKey as String] == nil {
            attrs[kCVPixelBufferIOSurfacePropertiesKey as String] = [String: Any]()
        }
        var created: CVPixelBuffer?
        guard CVPixelBufferCreate(kCFAllocatorDefault, width, height, format, attrs as CFDictionary, &created) == kCVReturnSuccess,
              let buffer = created else { return nil }
        CVPixelBufferLockBaseAddress(buffer, [])
        defer { CVPixelBufferUnlockBaseAddress(buffer, []) }
        let planes = CVPixelBufferGetPlaneCount(buffer)
        if planes == 0 {
            if let base = CVPixelBufferGetBaseAddress(buffer) {
                memset(base, 0x80, CVPixelBufferGetBytesPerRow(buffer) * CVPixelBufferGetHeight(buffer))
            }
        } else {
            for plane in 0..<planes {
                if let base = CVPixelBufferGetBaseAddressOfPlane(buffer, plane) {
                    memset(base, 0x80, CVPixelBufferGetBytesPerRowOfPlane(buffer, plane) * CVPixelBufferGetHeightOfPlane(buffer, plane))
                }
            }
        }
        return buffer
    }

    static func reportText() async -> String {
        if #available(iOS 26.0, *) { return await report() }
        return "Нужна iOS 26 или новее"
    }

    static func measureText(_ width: Int, _ height: Int) async -> String {
        if #available(iOS 26.0, *) { return await measureSingle(width: width, height: height) }
        return "Нужна iOS 26 или новее"
    }

    /// Button 1: support, formats and buffer attributes of the configuration, a started session. No frame is processed.
    @available(iOS 26.0, *)
    static func report() async -> String {
        guard VTLowLatencyFrameInterpolationConfiguration.isSupported else {
            return "Интерполяция VideoToolbox: не поддерживается на этом устройстве"
        }
        var lines = ["Интерполяция VideoToolbox: поддерживается"]
        let made: VTLowLatencyFrameInterpolationConfiguration? =
            VTLowLatencyFrameInterpolationConfiguration(frameWidth: 1920, frameHeight: 1080, numberOfInterpolatedFrames: 1)
        guard let config = made else {
            lines.append("1920x1080: конфигурация не создана")
            return lines.joined(separator: "\n")
        }
        let formats = (value(config, "frameSupportedPixelFormats") as? [NSNumber]) ?? []
        lines.append("Форматы кадра: " + (formats.isEmpty ? "не получены" : formats.map { fourCC($0.uint32Value) }.joined(separator: ", ")))
        for key in ["sourcePixelBufferAttributes", "destinationPixelBufferAttributes"] {
            if let dictionary = value(config, key) as? [String: Any] {
                lines.append("\(key): " + dictionary.keys.sorted().joined(separator: ", "))
            }
        }
        mark("1080p: запуск сессии")
        let processor = VTFrameProcessor()
        let started = CFAbsoluteTimeGetCurrent()
        do {
            try processor.startSession(configuration: config)
            lines.append("Сессия 1080p запущена за \(Int((CFAbsoluteTimeGetCurrent() - started) * 1000)) мс")
            processor.endSession()
        } catch {
            lines.append("Сессия 1080p не запущена: \(error.localizedDescription)")
        }
        mark(nil)
        return lines.joined(separator: "\n")
    }

    /// Buttons 2 and 3: the time of one interpolation at one size (the buffers are made by the attributes of the configuration).
    @available(iOS 26.0, *)
    static func measureSingle(width: Int, height: Int) async -> String {
        let result = await measure(width: width, height: height)
        mark(nil)
        return result
    }

    @available(iOS 26.0, *)
    static func interpolateOnce(_ processor: VTFrameProcessor, _ previousBuffer: CVPixelBuffer, _ sourceBuffer: CVPixelBuffer,
                                _ destinationBuffer: CVPixelBuffer) async throws -> Bool {
        let previous: VTFrameProcessorFrame? = VTFrameProcessorFrame(buffer: previousBuffer, presentationTimeStamp: CMTime(value: 0, timescale: 48))
        let source: VTFrameProcessorFrame? = VTFrameProcessorFrame(buffer: sourceBuffer, presentationTimeStamp: CMTime(value: 2, timescale: 48))
        let destination: VTFrameProcessorFrame? = VTFrameProcessorFrame(buffer: destinationBuffer, presentationTimeStamp: CMTime(value: 1, timescale: 48))
        guard let previous, let source, let destination else { return false }
        let made: VTLowLatencyFrameInterpolationParameters? =
            VTLowLatencyFrameInterpolationParameters(sourceFrame: source, previousFrame: previous,
                                                     interpolationPhase: [0.5], destinationFrames: [destination])
        guard let parameters = made else { return false }
        try await processor.process(parameters: parameters)
        return true
    }

    @available(iOS 26.0, *)
    static func measure(width: Int, height: Int) async -> String {
        let name = "\(width)x\(height)"
        let made: VTLowLatencyFrameInterpolationConfiguration? =
            VTLowLatencyFrameInterpolationConfiguration(frameWidth: width, frameHeight: height, numberOfInterpolatedFrames: 1)
        guard let config = made else { return "\(name): конфигурация не создана" }
        guard let first = (value(config, "frameSupportedPixelFormats") as? [NSNumber])?.first else {
            return "\(name): формат кадра не определён, замер пропущен"
        }
        let format = OSType(truncating: first)
        let sourceAttributes = (value(config, "sourcePixelBufferAttributes") as? [String: Any]) ?? [:]
        let destinationAttributes = (value(config, "destinationPixelBufferAttributes") as? [String: Any]) ?? [:]

        mark("\(name): запуск сессии")
        let processor = VTFrameProcessor()
        let started = CFAbsoluteTimeGetCurrent()
        do {
            try processor.startSession(configuration: config)
        } catch {
            return "\(name): сессия не запущена (\(error.localizedDescription))"
        }
        let startMs = Int((CFAbsoluteTimeGetCurrent() - started) * 1000)

        mark("\(name): буферы \(fourCC(format))")
        guard let previousBuffer = makeBuffer(width, height, format, sourceAttributes),
              let sourceBuffer = makeBuffer(width, height, format, sourceAttributes),
              let destinationBuffer = makeBuffer(width, height, format, destinationAttributes) else {
            processor.endSession()
            return "\(name): буферы формата \(fourCC(format)) не созданы"
        }
        do {
            // the session may still be initializing right after startSession: wait and repeat the first call
            try? await Task.sleep(nanoseconds: 300_000_000)
            mark("\(name): первый вызов process, формат \(fourCC(format))")
            let firstStart = CFAbsoluteTimeGetCurrent()
            var ready = false
            var attempts = 0
            while !ready && attempts < 4 {
                attempts += 1
                do {
                    ready = try await interpolateOnce(processor, previousBuffer, sourceBuffer, destinationBuffer)
                    if !ready { break }
                } catch {
                    if attempts >= 4 || !error.localizedDescription.lowercased().contains("not initialized") { throw error }
                    try? await Task.sleep(nanoseconds: 500_000_000)
                }
            }
            guard ready else {
                processor.endSession()
                return "\(name): кадры или параметры не созданы"
            }
            let firstMs = Int((CFAbsoluteTimeGetCurrent() - firstStart) * 1000)
            mark("\(name): повторные вызовы process")
            let begin = CFAbsoluteTimeGetCurrent()
            for _ in 0..<10 {
                _ = try await interpolateOnce(processor, previousBuffer, sourceBuffer, destinationBuffer)
            }
            let ms = (CFAbsoluteTimeGetCurrent() - begin) * 1000 / 10
            processor.endSession()
            return "\(name): запуск \(startMs) мс, первый кадр \(firstMs) мс (попыток: \(attempts)), далее \(String(format: "%.1f", ms)) мс на кадр (бюджет 41 мс на 24→48), формат \(fourCC(format))"
        } catch {
            processor.endSession()
            return "\(name): ошибка обработки (\(error.localizedDescription))"
        }
    }
}

struct InterpolationProbeSection: View {
    @State private var text = ""
    @State private var busy = false

    var body: some View {
        Section("Интерполяция кадров (тест)") {
            Button(busy ? "Проверка..." : "1. Проверить поддержку") {
                start { await InterpolationProbe.reportText() }
            }
            Button(busy ? "Проверка..." : "2. Замер скорости 720p") {
                start { await InterpolationProbe.measureText(1280, 720) }
            }
            Button(busy ? "Проверка..." : "3. Замер скорости 1080p") {
                start { await InterpolationProbe.measureText(1920, 1080) }
            }
            if !text.isEmpty {
                Text(text).font(.footnote).foregroundColor(.secondary)
            }
        }
        .onAppear {
            if let step = InterpolationProbe.unfinishedStep(), text.isEmpty {
                text = "Прошлая проверка оборвалась на шаге: \(step)"
            }
        }
    }

    private func start(_ work: @escaping () async -> String) {
        guard !busy else { return }
        busy = true
        Task {
            let result = await work()
            text = result
            busy = false
        }
    }
}

'''

p = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = p.read_text(encoding="utf-8")
if "import VideoToolbox" not in s:
    s = "import VideoToolbox\nimport CoreVideo\nimport CoreMedia\n" + s
s = replace_once(s, "/// One folder of the video library", PROBE + "/// One folder of the video library", "probe block")
s = replace_once(s, '''                Section("Субтитры") {
                    Button("Найти японские субтитры на Jimaku") { searchJimaku() }''',
                 '''                InterpolationProbeSection()
                Section("Субтитры") {
                    Button("Найти японские субтитры на Jimaku") { searchJimaku() }''', "settings section")
p.write_text(s, encoding="utf-8")
print("probe added")
