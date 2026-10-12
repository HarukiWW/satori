# v1.43 (KSPlayer): frame interpolation for frames larger than the interpolation unit accepts.
# The low-latency interpolation of VideoToolbox has a frame size limit that depends on the device and the iOS version.
# Above it startSession still succeeds, but every process call fails with -19730 "Processor is not initialized"
# (1080p fails and 720p works on the tested iPhone). Larger frames are now interpolated on a smaller copy and the
# result is scaled back to the video size; the original frames keep their full size. The working size is found on
# the device step by step (full size, 1600x900, 1280x720, 960x540, 640x360) and kept per iOS version.
# The first process call of a new session waits 300 ms (as the interpolation test in the settings does).
# Runs after ksplayer_interp_patch.py, which creates MEPlayer/FrameInterpolator.swift. Replaces v142-ksplayer-fixes.py.
import pathlib, sys

ROOT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "spm/checkouts/KSPlayer/Sources/KSPlayer")
f = ROOT / "MEPlayer/FrameInterpolator.swift"
s = f.read_text(encoding="utf-8")


def once(text, old, new, label):
    assert text.count(old) == 1, "KSPlayer pattern not found exactly once: " + label
    return text.replace(old, new)


s = once(s, "    private var retryAfter: CFAbsoluteTime = 0\n", """    private var retryAfter: CFAbsoluteTime = 0
    private var sessionStarted: CFAbsoluteTime = 0
    private var sourceWidth = 0
    private var sourceHeight = 0
    /// ", кадр 1280×720" when the intermediate frames are made on a smaller copy (for the settings status).
    var sizeNote = ""

    /// The largest frame (in pixels) the interpolation unit accepted here, kept per iOS version.
    /// 0 (nothing saved): the full size is tried first; -1: even the smallest step was refused.
    private static let limitKey = "frameInterpolation.pixelLimit." + ProcessInfo.processInfo.operatingSystemVersionString
    private static let steps = [1600 * 900, 1280 * 720, 960 * 540, 640 * 360]

    /// The size the intermediate frames are made at: the video size, or a smaller copy with the same proportions.
    static func processingSize(width: Int, height: Int) -> (width: Int, height: Int) {
        let saved = UserDefaults.standard.integer(forKey: limitKey)
        if saved < 0 { return (0, 0) }
        let limit = saved > 0 ? saved : Int.max
        let pixels = width * height
        if pixels <= limit { return (width, height) }
        let scale = (Double(limit) / Double(pixels)).squareRoot()
        var w = Int((Double(width) * scale).rounded()) / 8 * 8
        var h = Int((Double(height) * scale).rounded()) / 8 * 8
        while w * h > limit && w > 8 && h > 8 {
            w -= 8
            h -= 8
        }
        return (w, h)
    }

    /// The unit refused frames of this size: the next attempt uses the next smaller step.
    static func lowerLimit(below pixels: Int) {
        let next = steps.first { $0 < pixels } ?? -1
        UserDefaults.standard.set(next, forKey: limitKey)
    }
""", "worker vars")

s = once(s, """        let created = VTFrameProcessor()
        try created.startSession(configuration: config)
        processor = created
        sessionWidth = width
        sessionHeight = height
""", """        let created = VTFrameProcessor()
        try created.startSession(configuration: config)
        processor = created
        sessionStarted = CFAbsoluteTimeGetCurrent()
        sessionWidth = width
        sessionHeight = height
""", "session start time")

s = once(s, """        let width = CVPixelBufferGetWidth(source)
        let height = CVPixelBufferGetHeight(source)
        guard CVPixelBufferGetWidth(previous) == width, CVPixelBufferGetHeight(previous) == height else { return nil }
        if processor == nil || width != sessionWidth || height != sessionHeight {
            try startSession(width: width, height: height)
        }
""", """        let width = CVPixelBufferGetWidth(source)
        let height = CVPixelBufferGetHeight(source)
        guard CVPixelBufferGetWidth(previous) == width, CVPixelBufferGetHeight(previous) == height else { return nil }
        // frames above the limit of the unit: the session works on a smaller copy (the pools have the session size,
        // so copying a frame into them scales it down)
        let target = Self.processingSize(width: width, height: height)
        guard target.width > 0, target.height > 0 else { return nil }
        if processor == nil || target.width != sessionWidth || target.height != sessionHeight
            || width != sourceWidth || height != sourceHeight {
            try startSession(width: target.width, height: target.height)
            sourceWidth = width
            sourceHeight = height
        }
""", "processing size")

s = once(s, """        try await activeProcessor.process(parameters: parameters)
        CVBufferPropagateAttachments(source, destination)
        let format = CVPixelBufferGetPixelFormatType(source)
        if format == CVPixelBufferGetPixelFormatType(destination) { return destination }
        return convert(destination, toFormat: format, like: source)
""", """        // a new session is still initializing for a moment: the first call waits for it
        let sinceStart = CFAbsoluteTimeGetCurrent() - sessionStarted
        if sinceStart < 0.3 {
            try? await Task.sleep(nanoseconds: UInt64((0.3 - sinceStart) * 1_000_000_000))
        }
        do {
            try await activeProcessor.process(parameters: parameters)
        } catch {
            // -19730 "Processor is not initialized": the frame is too large for the unit, a smaller copy is used next time
            let code = (error as NSError).code
            if code == -19730 || error.localizedDescription.lowercased().contains("not initialized") {
                Self.lowerLimit(below: sessionWidth * sessionHeight)
                activeProcessor.endSession()
                processor = nil
            }
            throw error
        }
        CVBufferPropagateAttachments(source, destination)
        sizeNote = (sessionWidth == width && sessionHeight == height) ? "" : ", кадр \\(sessionWidth)×\\(sessionHeight)"
        let format = CVPixelBufferGetPixelFormatType(source)
        let sameSize = CVPixelBufferGetWidth(destination) == width && CVPixelBufferGetHeight(destination) == height
        if sameSize && format == CVPixelBufferGetPixelFormatType(destination) { return destination }
        // back to the video size (and its pixel format)
        return convert(destination, toFormat: format, like: source)
""", "process, scale back")

s = once(s, 'Self.status = "работает: " + String(format: "%.1f", activeWorker.lastMs) + " мс на кадр"',
         'Self.status = "работает: " + String(format: "%.1f", activeWorker.lastMs) + " мс на кадр" + activeWorker.sizeNote',
         "status")
f.write_text(s, encoding="utf-8")
print("KSPlayer interpolation: smaller copy for large frames applied")
