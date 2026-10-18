# v2.13 (KSPlayer): «Авто» for Anime4K and the time of the last frame drawn.
# - ykAnime4KPreset "auto": the kind goes down (L → M → S) when 15 frames take over 30 ms on average, and up when
#   the next kind would fit (it costs about 2–2.5 times more): not for a minute after it went down.
# - YKFrameWatch.lastFrame: when MetalPlayView took its last frame (the system layer and Metal alike); the app starts
#   a picture that stopped again. Without the place to mark it (another KSPlayer) it stays 0 and the app does nothing.
# Usage: python3 v213-anime4k.py   (in src/, after v212-anime4k.py)
import pathlib
import re


def once(text, old, new, label):
    assert text.count(old) == 1, "KSPlayer pattern not found exactly once: " + label
    return text.replace(old, new)


ROOT = pathlib.Path("spm/checkouts/KSPlayer/Sources/KSPlayer")
path = ROOT / "MEPlayer/YKVideoFilters.swift"
s = path.read_text(encoding="utf-8")
s = once(s, '''    /// The passes of the chosen kind (ykAnime4KPreset): S, or M / L when they converted.
    static var chosenPasses: [Pass] {
        switch UserDefaults.standard.string(forKey: "ykAnime4KPreset") {''', '''    /// «Авто»: 0 S, 1 M, 2 L (the strongest that keeps a frame under 30 ms).
    public static var autoLevel = 2
    private static var upAllowedAt: CFTimeInterval = 0

    private static var kinds: [[Pass]] {
        [passes, passesM, passesL]
    }

    /// The level of «Авто» after the average time of a frame.
    private static func adjust(_ average: Double) {
        let available = kinds.map { !$0.isEmpty }
        let now = CACurrentMediaTime()
        while autoLevel > 0 && !available[autoLevel] {
            autoLevel -= 1
        }
        if average > 30 {
            if autoLevel > 0 {
                autoLevel -= 1
                while autoLevel > 0 && !available[autoLevel] {
                    autoLevel -= 1
                }
                upAllowedAt = now + 60
            }
            return
        }
        guard now >= upAllowedAt, let next = (autoLevel + 1 ..< 3).first(where: { available[$0] }) else { return }
        // M costs about 2.5 times S, L about twice M
        let factor: Double = (autoLevel == 0 ? 2.5 : 1) * (next == 2 ? 2 : 1)
        if average * factor < 24 {
            autoLevel = next
            upAllowedAt = now + 3
        }
    }

    /// The passes of the chosen kind (ykAnime4KPreset): S, or M / L when they converted.
    static var chosenPasses: [Pass] {
        switch UserDefaults.standard.string(forKey: "ykAnime4KPreset") {
        case "auto":
            let chosen = kinds[min(max(autoLevel, 0), 2)]
            return chosen.isEmpty ? passes : chosen''', "auto passes")
s = once(s, '''    /// GPU time of the frame, shown in the settings (average of 30 frames).
    func finished(_ commandBuffer: MTLCommandBuffer, width: Int, height: Int) {
        gpuMs += max(0, commandBuffer.gpuEndTime - commandBuffer.gpuStartTime) * 1000
        frames += 1
        if frames >= 30 {
            Self.status = String(format: "работает: %.1f мс на кадр, %d×%d", gpuMs / Double(frames), width, height)
            frames = 0
            gpuMs = 0
        }
    }''', '''    /// GPU time of the frame, shown in the settings (average of 15 frames); «Авто» follows it.
    func finished(_ commandBuffer: MTLCommandBuffer, width: Int, height: Int) {
        gpuMs += max(0, commandBuffer.gpuEndTime - commandBuffer.gpuStartTime) * 1000
        frames += 1
        guard frames >= 15 else { return }
        let average = gpuMs / Double(frames)
        frames = 0
        gpuMs = 0
        let d = UserDefaults.standard
        var kind = ""
        if d.bool(forKey: "ykAnime4K"), d.string(forKey: "ykAnime4KPreset") == "auto" {
            Self.adjust(average)
            kind = " (авто: " + ["S", "M", "L"][min(max(Self.autoLevel, 0), 2)] + ")"
        }
        Self.status = "работает" + kind + String(format: ": %.1f мс на кадр, %d×%d", average, width, height)
    }''', "finished")
s = s.rstrip("\n") + '''

/// When the player took its last video frame to show (CACurrentMediaTime); 0 before the first one.
public enum YKFrameWatch {
    public static var lastFrame: CFTimeInterval = 0
}
'''
path.write_text(s, encoding="utf-8")

view = ROOT / "MEPlayer/MetalPlayView.swift"
v = view.read_text(encoding="utf-8")
v, count = re.subn(r"(?m)^(\s*)(renderSource\?\.setVideo\(time:)", r"\1YKFrameWatch.lastFrame = CACurrentMediaTime()\n\1\2", v)
if count == 1:
    view.write_text(v, encoding="utf-8")
    print("KSPlayer v2.13: auto Anime4K, frame watch marked")
else:
    print("KSPlayer v2.13: auto Anime4K; the frame watch is off (setVideo(time:) found " + str(count) + " times)")
