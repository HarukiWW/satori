# Moved out of build-ios-v141-player.yml, step "Write the KSPlayer frame interpolation patch" (GitHub limits workflow files to 500 KB).
import pathlib, sys

ROOT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "spm/checkouts/KSPlayer/Sources/KSPlayer")
NEW_FILE = r'''//
//  FrameInterpolator.swift
//  Frame interpolation of the video with VideoToolbox (iOS 26): one intermediate frame between two decoded frames.
//  An intermediate frame is made for the pair (N+1, N+2) while the frame N is shown, so it has about 60 ms of time.
//
import CoreMedia
import CoreVideo
import Foundation
import VideoToolbox

public final class FrameInterpolationScheduler {
    public static let defaultsKey = "frameInterpolation"
    /// A short text for the settings screen.
    public static var status = "выключена"
    static var suspendedUntil: CFAbsoluteTime = 0

    private static let supported: Bool = {
        if #available(iOS 26.0, *) {
            return VTLowLatencyFrameInterpolationConfiguration.isSupported
        }
        return false
    }()

    public static var isActive: Bool {
        guard supported, UserDefaults.standard.bool(forKey: defaultsKey) else { return false }
        if ProcessInfo.processInfo.thermalState.rawValue >= ProcessInfo.ThermalState.serious.rawValue { return false }
        return CFAbsoluteTimeGetCurrent() >= suspendedUntil
    }

    private var generation = 0
    private var readyFrame: VideoVTBFrame?
    private var readyBase: Int64 = -1
    private var readyTime = 0.0
    private var readyDeadline = 0.0
    private var lastShown: Int64 = -1
    private var worker: AnyObject?
    private var pairs = 0
    private var misses = 0

    func reset() {
        generation += 1
        readyFrame = nil
        readyBase = -1
        lastShown = -1
    }

    /// The intermediate frame, if it is time to show it (called before the next original frame is taken).
    func intermediateFrame(item: MEPlayerItem) -> VideoVTBFrame? {
        guard let frame = readyFrame, readyBase == lastShown else { return nil }
        let clock = item.interpolationClock()
        if clock >= readyDeadline {
            readyFrame = nil
            return nil
        }
        if readyTime - clock <= 0.004 {
            readyFrame = nil
            return frame
        }
        return nil
    }

    /// An original frame is going to be shown: the next intermediate frame is prepared.
    func didShow(frame: VideoVTBFrame, item: MEPlayerItem) {
        lastShown = frame.timestamp
        pairs += 1
        if readyFrame == nil || readyBase != frame.timestamp {
            misses += 1
        }
        if readyFrame != nil, readyBase < frame.timestamp {
            readyFrame = nil
        }
        if pairs >= 48 {
            if misses * 4 > pairs {
                Self.suspendedUntil = CFAbsoluteTimeGetCurrent() + 20
                Self.status = "не успевает, отключена на 20 с"
                readyFrame = nil
            }
            pairs = 0
            misses = 0
        }
        if #available(iOS 26.0, *) {
            startJob(item: item)
        }
    }

    @available(iOS 26.0, *)
    private func startJob(item: MEPlayerItem) {
        guard Self.isActive else { return }
        guard let base = item.peekVideoFrame(0), let next = item.peekVideoFrame(1) else { return }
        guard let baseBuffer = base.corePixelBuffer?.cvPixelBuffer, let nextBuffer = next.corePixelBuffer?.cvPixelBuffer else {
            Self.status = "кадры без CVPixelBuffer (программное декодирование): интерполяция недоступна"
            return
        }
        let gap = next.seconds - base.seconds
        guard gap > 0.005, gap < 0.2 else { return }
        if readyFrame != nil, readyBase == base.timestamp { return }
        if worker == nil { worker = InterpolationWorker() }
        guard let activeWorker = worker as? InterpolationWorker else { return }
        let id = generation
        let due = base.seconds + gap / 2
        let deadline = next.seconds - 0.006
        activeWorker.interpolate(previous: baseBuffer, source: nextBuffer) { [weak self] result, failure in
            guard let self, self.generation == id else { return }
            if let failure {
                Self.status = "ошибка: \(failure)"
                return
            }
            guard let buffer = result else { return }
            let mid = VideoVTBFrame(fps: base.fps, isDovi: base.isDovi)
            mid.timebase = base.timebase
            mid.timestamp = base.timestamp + (next.timestamp - base.timestamp) / 2
            mid.position = base.position
            mid.duration = base.duration
            mid.size = base.size
            mid.edrMetaData = base.edrMetaData
            mid.corePixelBuffer = buffer
            self.readyFrame = mid
            self.readyBase = base.timestamp
            self.readyTime = due
            self.readyDeadline = deadline
            Self.status = "работает: " + String(format: "%.1f", activeWorker.lastMs) + " мс на кадр"
        }
    }
}

extension MEPlayerItem {
    /// A decoded frame that waits in the queue (offset 0 is the next one to show).
    func peekVideoFrame(_ offset: Int) -> VideoVTBFrame? {
        videoTrack?.outputRenderQueue.peek(offset: offset)
    }

    /// The same time the player uses to decide which frame to show.
    func interpolationClock() -> TimeInterval {
        mainClock().getTime() - options.videoDelay
    }
}

@available(iOS 26.0, *)
final class InterpolationWorker {
    struct Failure: Error, LocalizedError {
        let message: String
        var errorDescription: String? { message }
    }

    private var processor: VTFrameProcessor?
    private var sessionWidth = 0
    private var sessionHeight = 0
    private var sourcePool: CVPixelBufferPool?
    private var destinationPool: CVPixelBufferPool?
    private var resultPools = [OSType: CVPixelBufferPool]()
    private var transfer: VTPixelTransferSession?
    private var retryAfter: CFAbsoluteTime = 0
    var busy = false
    var lastMs = 0.0

    /// One job at a time. The completion is called on the main queue; nothing is called if a job is already running.
    func interpolate(previous: CVPixelBuffer, source: CVPixelBuffer, completion: @escaping (CVPixelBuffer?, String?) -> Void) {
        if busy || CFAbsoluteTimeGetCurrent() < retryAfter { return }
        busy = true
        Task.detached(priority: .userInitiated) {
            let started = CFAbsoluteTimeGetCurrent()
            var result: CVPixelBuffer?
            var failure: String?
            do {
                result = try await self.run(previous: previous, source: source)
            } catch {
                failure = error.localizedDescription
            }
            let milliseconds = (CFAbsoluteTimeGetCurrent() - started) * 1000
            DispatchQueue.main.async {
                self.busy = false
                self.lastMs = milliseconds
                if failure != nil { self.retryAfter = CFAbsoluteTimeGetCurrent() + 0.5 }
                completion(result, failure)
            }
        }
    }

    private func property(_ object: NSObject, _ key: String) -> Any? {
        guard object.responds(to: NSSelectorFromString(key)) else { return nil }
        return object.value(forKey: key)
    }

    private func startSession(width: Int, height: Int) throws {
        processor?.endSession()
        processor = nil
        resultPools.removeAll()
        let made: VTLowLatencyFrameInterpolationConfiguration? =
            VTLowLatencyFrameInterpolationConfiguration(frameWidth: width, frameHeight: height, numberOfInterpolatedFrames: 1)
        guard let config = made else { throw Failure(message: "конфигурация не создана") }
        let formats = (property(config, "frameSupportedPixelFormats") as? [NSNumber]) ?? []
        let format: OSType = formats.first.map { OSType(truncating: $0) } ?? kCVPixelFormatType_420YpCbCr8BiPlanarVideoRange
        let sourceAttributes = (property(config, "sourcePixelBufferAttributes") as? [String: Any]) ?? [:]
        let destinationAttributes = (property(config, "destinationPixelBufferAttributes") as? [String: Any]) ?? [:]
        sourcePool = makePool(width, height, format, sourceAttributes)
        destinationPool = makePool(width, height, format, destinationAttributes)
        guard sourcePool != nil, destinationPool != nil else { throw Failure(message: "пул буферов не создан") }
        let created = VTFrameProcessor()
        try created.startSession(configuration: config)
        processor = created
        sessionWidth = width
        sessionHeight = height
    }

    private func makePool(_ width: Int, _ height: Int, _ format: OSType, _ attributes: [String: Any]) -> CVPixelBufferPool? {
        var attrs = attributes
        attrs[kCVPixelBufferPixelFormatTypeKey as String] = Int(format)
        attrs[kCVPixelBufferWidthKey as String] = width
        attrs[kCVPixelBufferHeightKey as String] = height
        if attrs[kCVPixelBufferIOSurfacePropertiesKey as String] == nil {
            attrs[kCVPixelBufferIOSurfacePropertiesKey as String] = [String: Any]()
        }
        var pool: CVPixelBufferPool?
        guard CVPixelBufferPoolCreate(kCFAllocatorDefault, nil, attrs as CFDictionary, &pool) == kCVReturnSuccess else { return nil }
        return pool
    }

    private func makeBuffer(from pool: CVPixelBufferPool) -> CVPixelBuffer? {
        var created: CVPixelBuffer?
        guard CVPixelBufferPoolCreatePixelBuffer(kCFAllocatorDefault, pool, &created) == kCVReturnSuccess else { return nil }
        return created
    }

    private func transferSession() -> VTPixelTransferSession? {
        if transfer == nil {
            var created: VTPixelTransferSession?
            VTPixelTransferSessionCreate(allocator: kCFAllocatorDefault, pixelTransferSessionOut: &created)
            transfer = created
        }
        return transfer
    }

    /// A copy in the buffer of the pool: the geometry and the format are exactly what the processor wants.
    private func copy(_ buffer: CVPixelBuffer, into pool: CVPixelBufferPool) -> CVPixelBuffer? {
        guard let destination = makeBuffer(from: pool), let session = transferSession() else { return nil }
        guard VTPixelTransferSessionTransferImage(session, from: buffer, to: destination) == noErr else { return nil }
        return destination
    }

    /// The result in the pixel format of the original frames (for example 10 bit), so the display does not change.
    private func convert(_ buffer: CVPixelBuffer, toFormat format: OSType, like source: CVPixelBuffer) -> CVPixelBuffer? {
        if resultPools[format] == nil {
            resultPools[format] = makePool(CVPixelBufferGetWidth(source), CVPixelBufferGetHeight(source), format, [:])
        }
        guard let pool = resultPools[format], let result = makeBuffer(from: pool), let session = transferSession() else { return nil }
        guard VTPixelTransferSessionTransferImage(session, from: buffer, to: result) == noErr else { return nil }
        CVBufferPropagateAttachments(source, result)
        return result
    }

    private func run(previous: CVPixelBuffer, source: CVPixelBuffer) async throws -> CVPixelBuffer? {
        let width = CVPixelBufferGetWidth(source)
        let height = CVPixelBufferGetHeight(source)
        guard CVPixelBufferGetWidth(previous) == width, CVPixelBufferGetHeight(previous) == height else { return nil }
        if processor == nil || width != sessionWidth || height != sessionHeight {
            try startSession(width: width, height: height)
        }
        guard let activeProcessor = processor, let inputPool = sourcePool, let outputPool = destinationPool else { return nil }
        guard let previousCopy = copy(previous, into: inputPool),
              let sourceCopy = copy(source, into: inputPool),
              let destination = makeBuffer(from: outputPool) else {
            throw Failure(message: "буферы не созданы")
        }
        let previousFrame: VTFrameProcessorFrame? = VTFrameProcessorFrame(buffer: previousCopy, presentationTimeStamp: CMTime(value: 0, timescale: 48))
        let sourceFrame: VTFrameProcessorFrame? = VTFrameProcessorFrame(buffer: sourceCopy, presentationTimeStamp: CMTime(value: 2, timescale: 48))
        let destinationFrame: VTFrameProcessorFrame? = VTFrameProcessorFrame(buffer: destination, presentationTimeStamp: CMTime(value: 1, timescale: 48))
        guard let previousFrame, let sourceFrame, let destinationFrame else { throw Failure(message: "кадры не созданы") }
        let made: VTLowLatencyFrameInterpolationParameters? =
            VTLowLatencyFrameInterpolationParameters(sourceFrame: sourceFrame, previousFrame: previousFrame,
                                                     interpolationPhase: [0.5], destinationFrames: [destinationFrame])
        guard let parameters = made else { throw Failure(message: "параметры не созданы") }
        try await activeProcessor.process(parameters: parameters)
        CVBufferPropagateAttachments(source, destination)
        let format = CVPixelBufferGetPixelFormatType(source)
        if format == CVPixelBufferGetPixelFormatType(destination) { return destination }
        return convert(destination, toFormat: format, like: source)
    }
}
'''

def replace_once(text, old, new, label):
    assert text.count(old) == 1, "KSPlayer pattern not found exactly once: " + label
    return text.replace(old, new)

def edit(rel, fn):
    p = ROOT / rel
    p.write_text(fn(p.read_text(encoding="utf-8")), encoding="utf-8")

# 1. a peek into the queue of decoded frames (the search method removes the items, the peek does not)
edit("MEPlayer/CircularBuffer.swift", lambda s: replace_once(s,
    "    public func search(where predicate: (Item) -> Bool) -> [Item] {",
    """    /// The item at the offset from the head, without removing it.
    public func peek(offset: Int = 0) -> Item? {
        condition.lock()
        defer { condition.unlock() }
        guard !destroyed, offset >= 0, offset < _count else { return nil }
        return _buffer[Int((headIndex &+ UInt(offset)) & mask)]
    }

    public func search(where predicate: (Item) -> Bool) -> [Item] {""", "peek"))

# 2. the player item: the video track and the options are needed by the scheduler (same module)
def item(s):
    s = replace_once(s, "    private let options: KSOptions\n", "    let options: KSOptions\n", "item options")
    s = replace_once(s, "    private var videoTrack: SyncPlayerItemTrack<VideoVTBFrame>?\n",
                     "    var videoTrack: SyncPlayerItemTrack<VideoVTBFrame>?\n", "item videoTrack")
    return s
edit("MEPlayer/MEPlayerItem.swift", item)

# 3. video clock: with interpolation a frame is released at its time, not half a frame earlier
def options(s):
    s = replace_once(s, "        if diff >= 1 / fps / 2 {\n",
                     "        if diff >= (FrameInterpolationScheduler.isActive ? 0.004 : 1 / fps / 2) {\n", "clock sync")
    # the display link runs at the full refresh rate (120 Hz): frames are shown at an even rhythm
    s = replace_once(s, "    static var preferredFrame = true\n", "    static var preferredFrame = false\n", "preferredFrame")
    return s
edit("AVPlayer/KSOptions.swift", options)

# 4. the display: an intermediate frame is shown between two original frames
def view(s):
    s = replace_once(s, "    private let metalView = MetalView()\n",
                     "    private let metalView = MetalView()\n    private let interpolator = FrameInterpolationScheduler()\n", "interpolator property")
    s = replace_once(s, "    public func flush() {\n        pixelBuffer = nil\n",
                     "    public func flush() {\n        interpolator.reset()\n        pixelBuffer = nil\n", "flush")
    s = replace_once(s, """            guard let frame = renderSource?.getVideoOutputRender(force: force) else {
                return
            }
""", """            var picked: VideoVTBFrame?
            if !force, FrameInterpolationScheduler.isActive, let item = renderSource as? MEPlayerItem {
                picked = interpolator.intermediateFrame(item: item)
            }
            if picked == nil {
                picked = renderSource?.getVideoOutputRender(force: force)
                if let shown = picked, !force, FrameInterpolationScheduler.isActive, let item = renderSource as? MEPlayerItem {
                    interpolator.didShow(frame: shown, item: item)
                }
            }
            guard let frame = picked else {
                return
            }
""", "draw")
    return s
edit("MEPlayer/MetalPlayView.swift", view)

(ROOT / "MEPlayer/FrameInterpolator.swift").write_text(NEW_FILE, encoding="utf-8")
print("KSPlayer: frame interpolation hook added")
