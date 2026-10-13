# v1.63: YouTube captions follow the video while it plays (the line was computed by a timer made inside the view's
# body, which started again on every redraw; the page now reports the time of the video element and the controller
# moves the line itself between the reports); landscape draws the captions and the controls over the picture like
# the file player, with a rotate button; the subtitle delay buttons work after the first tap.
import pathlib


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


here = pathlib.Path(__file__).resolve().parent
hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")

# ---------- the screen ----------
start = "/// A YouTube video in the app: the official player, the Japanese captions under it"
end = "/// A YouTube link typed or pasted."
assert s.count(start) == 1, "youtube screen start"
a = s.index(start)
b = s.index(end, a)
s = s[:a] + (here / "v163-youtube-player.swift").read_text(encoding="utf-8") + s[b:]

# ---------- the controller: the line and the time between the reports ----------
s = once(s, '    @Published var status = "Загружаю видео…"\n', '''    @Published var status = "Загружаю видео…"
    /// the caption at the current time (with the delay)
    @Published var line = ""
    /// subtitle delay, seconds
    var delay: Double = 0
    private var reportedAt: CFTimeInterval = 0
    private var timer: Timer?
''', "line state")
s = once(s, """        proxy.target = self
    }
""", """        proxy.target = self
        // the line follows the video between the reports of the page (about five a second)
        timer = Timer.scheduledTimer(withTimeInterval: 0.1, repeats: true) { [weak self] _ in
            Task { @MainActor in
                self?.updateLine()
            }
        }
    }

    /// The time now: the last report of the page and, while playing, the time since then.
    var currentTime: Double {
        playing ? time + min(CACurrentMediaTime() - reportedAt, 1) : time
    }

    func stopTimer() {
        timer?.invalidate()
        timer = nil
    }

    private func updateLine() {
        let t = currentTime - delay
        let next = cues.filter { $0.start <= t && t < $0.end }.map { $0.text }.joined(separator: "\\n")
        if next != line {
            line = next
        }
    }
""", "timer")
s = once(s, """        time = seconds
        ended = false
""", """        time = seconds
        reportedAt = CACurrentMediaTime()
        ended = false
""", "seek time")
s = once(s, """        case "tick":
            time = (body["t"] as? NSNumber)?.doubleValue ?? time
            let length = (body["d"] as? NSNumber)?.doubleValue ?? 0
            if length > 0 {
                duration = length
            }
            let state = (body["s"] as? NSNumber)?.intValue ?? -1
            playing = state == 1 || state == 3
            ended = state == 0
""", """        case "tick":
            // values are set only when they change: every change redraws the screen
            let now = (body["t"] as? NSNumber)?.doubleValue ?? time
            reportedAt = CACurrentMediaTime()
            if now != time {
                time = now
            }
            let length = (body["d"] as? NSNumber)?.doubleValue ?? 0
            if length > 0, length != duration {
                duration = length
            }
            let state = (body["s"] as? NSNumber)?.intValue ?? -1
            if (state == 1) != playing {
                playing = state == 1
            }
            if (state == 0) != ended {
                ended = state == 0
            }
""", "tick")

# ---------- the page: the time of the video element ----------
s = once(s, """        post({ type: 'tick', t: p.getCurrentTime() || 0, d: p.getDuration() || 0, s: s, title: title });
""", """        // the video element has the exact time while playing; the player API can lag behind
        var v = document.querySelector('video');
        var t = v && !isNaN(v.currentTime) ? v.currentTime : (p.getCurrentTime() || 0);
        var d = p.getDuration() || (v && isFinite(v.duration) ? v.duration : 0);
        if (v && s !== 0 && s !== 3) s = v.paused ? 2 : 1;
        post({ type: 'tick', t: t, d: d, s: s, title: title });
""", "page time")
hv.write_text(s, encoding="utf-8")
print("v1.63 YouTube applied")
