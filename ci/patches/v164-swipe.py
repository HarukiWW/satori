# v1.64: after swipe seeking the file player keeps the state it had before the swipe. The swipe sends many quick
# seeks; KSPlayer can finish the last one early or report it as not finished, so its own "play after the seek" did not
# always happen and the video stayed paused. The state before the swipe is read from the player itself (the polled
# value lags up to 0.2 s), set again when the last seek completes, and checked twice more a moment later.
import pathlib


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")

s = once(s, """            swipeStart = position
            swipeWasPlaying = playing
""", """            swipeStart = position
            swipeWasPlaying = VideoSwipe.wasPlaying(coordinator.playerLayer, polled: playing)
""", "state before the swipe")
s = once(s, """        let layer = coordinator.playerLayer
        layer?.seek(time: target, autoPlay: true) { _ in
            layer?.player.isMuted = false
            if !wasPlaying {
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.2) {
                    layer?.pause()
                }
            }
        }
    }
""", """        let layer = coordinator.playerLayer
        VideoSwipe.intent = (wasPlaying, CACurrentMediaTime() + 1.5)
        layer?.seek(time: target, autoPlay: wasPlaying) { _ in
            VideoSwipe.restore(layer, playing: wasPlaying)
        }
        // the completion of the last seek can come early (an earlier seek finishing) or say "not finished"
        for delay in [0.5, 1.2] {
            DispatchQueue.main.asyncAfter(deadline: .now() + delay) {
                VideoSwipe.restore(layer, playing: wasPlaying)
            }
        }
    }
""", "restore after the swipe")
s = once(s, "/// An opening or an ending found in the chapters of a video.\n", """/// The state of the player after swipe seeking: the sound back on, playing or paused as before the swipe.
enum VideoSwipe {
    /// the state the last swipe restores, until when (a new swipe right after it keeps that state)
    static var intent: (playing: Bool, until: CFTimeInterval)?

    /// Playing before a swipe: during a seek the player itself says "not playing", so the state of the layer
    /// (buffering or playing) and the state a recent swipe is restoring count too.
    static func wasPlaying(_ layer: KSPlayerLayer?, polled: Bool) -> Bool {
        if let intent, CACurrentMediaTime() < intent.until {
            return intent.playing
        }
        guard let layer else { return polled }
        return layer.player.isPlaying || layer.state.isPlaying
    }

    /// called on the main thread (seek completions and timers)
    static func restore(_ layer: KSPlayerLayer?, playing: Bool) {
        guard let layer else { return }
        layer.player.isMuted = false
        if playing, !layer.player.isPlaying {
            layer.play()
        } else if !playing, layer.player.isPlaying {
            layer.pause()
        }
    }
}

/// An opening or an ending found in the chapters of a video.
""", "restore helper")
hv.write_text(s, encoding="utf-8")
print("v1.64 swipe applied")
