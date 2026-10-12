# v1.42 (KSPlayer): frame interpolation during playback. A new VideoToolbox session is still initializing for a
# moment, so the first process call waits 300 ms (as the interpolation test in the settings does). When the session
# keeps answering "not initialized", it is ended and a new one is started on the next frame.
# Runs after ksplayer_interp_patch.py, which creates MEPlayer/FrameInterpolator.swift.
import pathlib, sys

ROOT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "spm/checkouts/KSPlayer/Sources/KSPlayer")
f = ROOT / "MEPlayer/FrameInterpolator.swift"
s = f.read_text(encoding="utf-8")


def once(text, old, new, label):
    assert text.count(old) == 1, "KSPlayer pattern not found exactly once: " + label
    return text.replace(old, new)


s = once(s, "    private var retryAfter: CFAbsoluteTime = 0\n",
         "    private var retryAfter: CFAbsoluteTime = 0\n"
         "    private var sessionStarted: CFAbsoluteTime = 0\n"
         "    private var notReadyFailures = 0\n", "worker vars")
s = once(s, "        processor = created\n        sessionWidth = width\n",
         "        processor = created\n"
         "        sessionStarted = CFAbsoluteTimeGetCurrent()\n"
         "        notReadyFailures = 0\n"
         "        sessionWidth = width\n", "session start time")
s = once(s, "        try await activeProcessor.process(parameters: parameters)\n",
         "        // a new session is still initializing for a moment: the first call waits for it\n"
         "        let sinceStart = CFAbsoluteTimeGetCurrent() - sessionStarted\n"
         "        if sinceStart < 0.3 {\n"
         "            try? await Task.sleep(nanoseconds: UInt64((0.3 - sinceStart) * 1_000_000_000))\n"
         "        }\n"
         "        do {\n"
         "            try await activeProcessor.process(parameters: parameters)\n"
         "            notReadyFailures = 0\n"
         "        } catch {\n"
         "            // \"not initialized\" again and again: this session does not recover, a new one is started next time\n"
         "            if error.localizedDescription.lowercased().contains(\"not initialized\") {\n"
         "                notReadyFailures += 1\n"
         "                if notReadyFailures >= 3 {\n"
         "                    activeProcessor.endSession()\n"
         "                    processor = nil\n"
         "                    notReadyFailures = 0\n"
         "                }\n"
         "            }\n"
         "            throw error\n"
         "        }\n", "process with warm-up")
f.write_text(s, encoding="utf-8")
print("KSPlayer interpolation warm-up applied")
