# Moved out of build-ios-v141-player.yml, step "Build iOS app (unsigned)" (GitHub limits workflow files to 500 KB).
import pathlib
f = pathlib.Path("spm/checkouts/KSPlayer/Sources/KSPlayer/SwiftUI/KSVideoPlayerViewBuilder.swift")
s = f.read_text(encoding="utf-8")
old = '            Text(title)\n                .font(.title3)\n'
assert s.count(old) == 1, "KSPlayer title view changed: update the patch"
f.write_text(s.replace(old, '            Text("")\n'), encoding="utf-8")
print("KSPlayer: built-in title hidden (the app draws its own title)")
f2 = pathlib.Path("spm/checkouts/KSPlayer/Sources/KSPlayer/SwiftUI/KSVideoPlayerView.swift")
s2 = f2.read_text(encoding="utf-8")
old2 = '            if let image {\n                Spacer()\n                GeometryReader { geometry in'
assert s2.count(old2) == 1, "KSPlayer subtitle image view changed: update the patch"
f2.write_text(s2.replace(old2, '            if let image, false {\n                Spacer()\n                GeometryReader { geometry in'), encoding="utf-8")
print("KSPlayer: bitmap subtitles are not drawn (the app reads them itself)")
import pathlib
kp = pathlib.Path("spm/checkouts/KSPlayer/Sources/KSPlayer")
def konce(text, old, new, label):
    assert text.count(old) == 1, "KSPlayer pattern not found exactly once: " + label
    return text.replace(old, new)
fp = kp / 'MEPlayer/VideoToolboxDecode.swift'
s = fp.read_text(encoding="utf-8")
s = konce(s, 'class VideoToolboxDecode: DecodeProtocol {\n', '/// Counts frames the hardware decoder lost in a row. After the app was in the background the session has no\n/// reference frames: every following frame is dropped or fails until the next key frame (a scene change).\nprivate final class VTDecodeHealth {\n    private let lock = NSLock()\n    private var sessionNumber = 0\n    private var badRun = 0\n    private var goodRun = 0\n    private var attempts = 0\n    private var lastRequest = TimeInterval(0)\n\n    var generation: Int {\n        lock.lock()\n        defer { lock.unlock() }\n        return sessionNumber\n    }\n\n    func newSession() {\n        lock.lock()\n        sessionNumber += 1\n        lock.unlock()\n    }\n\n    func good() {\n        lock.lock()\n        badRun = 0\n        goodRun += 1\n        if goodRun >= 100 {\n            attempts = 0\n        }\n        lock.unlock()\n    }\n\n    /// Counts a lost frame. True when many frames in a row were lost: playback must restart from the nearest key frame.\n    func bad() -> Bool {\n        lock.lock()\n        defer { lock.unlock() }\n        goodRun = 0\n        badRun += 1\n        guard badRun >= 12 else { return false }\n        badRun = 0\n        let now = ProcessInfo.processInfo.systemUptime\n        guard attempts < 3, now - lastRequest > 3 else { return false }\n        attempts += 1\n        lastRequest = now\n        return true\n    }\n}\n\nclass VideoToolboxDecode: DecodeProtocol {\n', 'vt class')
s = konce(s, '    private var needReconfig = false\n', '    private var needReconfig = false\n    private let health = VTDecodeHealth()\n\n    /// New decoder session and a restart of reading from the nearest key frame (KSMEPlayer listens).\n    private func requestRecovery() {\n        needReconfig = true\n        NotificationCenter.default.post(name: Notification.Name("ksplayer.videoDecoderStalled"), object: nil)\n    }\n', 'vt vars')
s = konce(s, '            session = DecompressionSession(assetTrack: session.assetTrack, options: options)!\n            doFlushCodec()\n            needReconfig = false\n', '            session = DecompressionSession(assetTrack: session.assetTrack, options: options)!\n            doFlushCodec()\n            needReconfig = false\n            health.newSession()\n', 'vt reconfig')
s = konce(s, '            let size = corePacket.size\n', '            let size = corePacket.size\n            let generation = health.generation\n', 'vt generation')
s = konce(s, '                guard let self, !infoFlags.contains(.frameDropped) else {\n                    return\n                }\n                guard status == noErr else {\n', '                guard let self else {\n                    return\n                }\n                if infoFlags.contains(.frameDropped) {\n                    if self.health.bad() {\n                        self.requestRecovery()\n                    }\n                    return\n                }\n                guard status == noErr else {\n                    if self.health.bad() {\n                        self.requestRecovery()\n                    }\n', 'vt dropped')
s = konce(s, '                            // 解决从后台切换到前台，解码失败的问题\n                            self.needReconfig = true\n', '                            // 解决从后台切换到前台，解码失败的问题\n                            if generation == self.health.generation {\n                                self.needReconfig = true\n                            }\n', 'vt cb reconfig')
s = konce(s, '                self.lastPosition += frame.duration\n                completionHandler(.success(frame))\n', '                self.lastPosition += frame.duration\n                self.health.good()\n                completionHandler(.success(frame))\n', 'vt success')
s = konce(s, '                    // 解决从后台切换到前台，解码失败的问题\n                    needReconfig = true\n', '                    // 解决从后台切换到前台，解码失败的问题\n                    if health.bad() {\n                        requestRecovery()\n                    } else {\n                        needReconfig = true\n                    }\n', 'vt sync reconfig')
fp.write_text(s, encoding="utf-8")
fp = kp / 'MEPlayer/KSMEPlayer.swift'
s = fp.read_text(encoding="utf-8")
s = konce(s, '    public required init(url: URL, options: KSOptions) {\n', '    private var decoderRecoveryPending = false\n\n    /// The hardware decoder lost its reference frames (back from another app): read again from the nearest\n    /// key frame, without changing the playback state, so the picture returns at once.\n    @objc private func videoDecoderStalled() {\n        DispatchQueue.main.async { [weak self] in\n            guard let self else { return }\n            guard self.playbackState == .playing else {\n                // paused (lookup window): restart as soon as the video plays again\n                self.decoderRecoveryPending = true\n                return\n            }\n            self.restartFromKeyFrame()\n        }\n    }\n\n    private func restartFromKeyFrame() {\n        KSLog("video decoder stalled, restart from the nearest key frame")\n        playerItem.seek(time: currentPlaybackTime) { [weak self] result in\n            guard let self, result else { return }\n            self.audioOutput.flush()\n            runOnMainThread { [weak self] in\n                guard let self else { return }\n                if let controlTimebase = self.videoOutput?.displayLayer.controlTimebase {\n                    CMTimebaseSetTime(controlTimebase, time: CMTimeMake(value: Int64(self.currentPlaybackTime), timescale: 1))\n                }\n            }\n        }\n    }\n\n    public required init(url: URL, options: KSOptions) {\n', 'me func')
s = konce(s, '        videoOutput?.displayLayerDelegate = self\n        #if !os(macOS)\n', '        videoOutput?.displayLayerDelegate = self\n        NotificationCenter.default.addObserver(self, selector: #selector(videoDecoderStalled), name: Notification.Name("ksplayer.videoDecoderStalled"), object: nil)\n        #if !os(macOS)\n', 'me observer')
s = konce(s, '        KSLog("play \\(self)")\n        playbackState = .playing\n', '        KSLog("play \\(self)")\n        playbackState = .playing\n        if decoderRecoveryPending {\n            decoderRecoveryPending = false\n            DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) { [weak self] in\n                guard let self, self.playbackState == .playing else { return }\n                self.restartFromKeyFrame()\n            }\n        }\n', 'me play')
fp.write_text(s, encoding="utf-8")
fp = kp / 'MEPlayer/MEPlayerItem.swift'
s = fp.read_text(encoding="utf-8")
s = konce(s, '    func mainClock() -> KSClock {\n        isAudioStalled ? videoClock : audioClock\n    }\n', '    func mainClock() -> KSClock {\n        if isAudioStalled {\n            return videoClock\n        }\n        var clock = audioClock\n        // The audio clock is not updated while the sound is paused or restarting (for example back from another app).\n        // getTime() would keep counting and run seconds ahead of the video: every frame looks late, the player drops\n        // a whole group of frames and the picture stays on one frame until the next scene change.\n        // After a long silence the clock stands at the last audio position and waits for the sound.\n        if CACurrentMediaTime() - clock.lastMediaTime > 1.0 {\n            let lastTime = clock.time\n            clock.time = lastTime\n        }\n        return clock\n    }\n', 'main clock')
fp.write_text(s, encoding="utf-8")
print("KSPlayer decoder recovery and audio clock guard applied")
import pathlib
kp = pathlib.Path("spm/checkouts/KSPlayer/Sources/KSPlayer")
def konce(text, old, new, label):
    assert text.count(old) == 1, "KSPlayer pattern not found exactly once: " + label
    return text.replace(old, new)

dp = kp / "MEPlayer/MetalPlayView.swift"
s = dp.read_text(encoding="utf-8")
s = konce(s, "                if KSOptions.preferredFrame {\n",
          "                if options.smoothPacing {\n"
          "                    // smooth pacing: request a fixed rate (the display maximum; 60 Hz in energy saving mode)\n"
          "                    if #available(iOS 15.0, tvOS 15.0, macOS 14.0, *) {\n"
          "                        displayLink.preferredFrameRateRange = CAFrameRateRange(minimum: 120, maximum: 120, __preferred: 120)\n"
          "                    }\n"
          "                }\n"
          "                if KSOptions.preferredFrame && !options.smoothPacing {\n", "displayrate")
dp.write_text(s, encoding="utf-8")
print("KSPlayer fixed display rate for smooth pacing applied")
PACING_FUNC_TEXT = '    /// Video clock that runs at real time and is reset to the audio clock only when they drift apart by more\n    /// than 40 ms. The audio clock advances in steps, which makes the frame choice uneven.\n    func pacingClockNow() -> KSClock {\n        let audioTime = mainClock().getTime()\n        if !pacingClockReady || abs(pacingClock.getTime() - audioTime) > 0.04 {\n            pacingClock.time = CMTime(seconds: audioTime, preferredTimescale: 1000)\n            pacingClockReady = true\n        }\n        return pacingClock\n    }\n\n'

kp = pathlib.Path("spm/checkouts/KSPlayer/Sources/KSPlayer")
def konce(text, old, new, label):
    assert text.count(old) == 1, "KSPlayer pattern not found exactly once: " + label
    return text.replace(old, new)
op = kp / "AVPlayer/KSOptions.swift"
s = op.read_text(encoding="utf-8")
s = konce(s, "    public var asynchronousDecompression = KSOptions.asynchronousDecompression\n",
          "    public var asynchronousDecompression = KSOptions.asynchronousDecompression\n    /// Smooth frame pacing: show frames on the display rhythm instead of the audio clock (set by the app).\n    public var smoothPacing = false\n", "options")
op.write_text(s, encoding="utf-8")
mp = kp / "MEPlayer/MEPlayerItem.swift"
s = mp.read_text(encoding="utf-8")
s = konce(s, "    private var videoClock = KSClock()\n",
          "    private var videoClock = KSClock()\n    private var pacingClock = KSClock()\n    private var pacingClockReady = false\n", "vars")
s = konce(s, "    func mainClock() -> KSClock {\n", PACING_FUNC_TEXT + "    func mainClock() -> KSClock {\n", "func")
s = konce(s, "videoClockSync(main: self.mainClock(), nextVideoTime: frame.seconds",
          "videoClockSync(main: self.options.smoothPacing ? self.pacingClockNow() : self.mainClock(), nextVideoTime: frame.seconds", "predicate")
mp.write_text(s, encoding="utf-8")
print("KSPlayer smooth pacing patch applied")
