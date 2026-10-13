# v1.65: fixes from the code review.
# - "Добавить все" of the mining queue stayed on "Добавляю…" for good when a note was cancelled in AnkiMobile (no
#   x-success comes back): back in the app without the callback, the sending stops.
# - Resetting the statistics (in the app and in the Safari extension) also deleted the words imported from Anki: they
#   are kept now (coverage, check marks and Safari marks depend on them).
# - Closing the dictionary (or coming back from AnkiMobile) started the video even when it was paused before the
#   word was tapped: both players now play again only when they were playing.
# - The YouTube caption timer starts again if the screen appears again.
import pathlib


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")

# ---------- the mining queue: a note cancelled in AnkiMobile ----------
s = once(s, """    private let key = "miningQueue.v1"
    private var observer: NSObjectProtocol?
""", """    private let key = "miningQueue.v1"
    private var observer: NSObjectProtocol?
    private var activeObserver: NSObjectProtocol?
    /// the note opened in AnkiMobile, until its x-success callback comes back
    private var awaiting: UUID?
""", "queue state")
s = once(s, """            Task { @MainActor in
                self?.sentOne()
            }
        }
    }
""", """            Task { @MainActor in
                self?.sentOne()
            }
        }
        activeObserver = NotificationCenter.default.addObserver(forName: UIApplication.didBecomeActiveNotification,
                                                                object: nil, queue: .main) { [weak self] _ in
            Task { @MainActor in
                self?.checkCancelled()
            }
        }
    }

    /// Back in the app and no callback from AnkiMobile shortly after: the note was cancelled there, the sending
    /// stops (the note stays in the queue).
    private func checkCancelled() {
        guard let waiting = awaiting else { return }
        DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
            guard self.awaiting == waiting else { return }
            self.awaiting = nil
            self.sending = []
        }
    }
""", "queue cancel check")
s = once(s, """        UIApplication.shared.open(MiningFrame.returningToQueue(url))
    }
""", """        awaiting = next.id
        UIApplication.shared.open(MiningFrame.returningToQueue(url))
    }
""", "queue awaiting")
s = once(s, """        guard let done = sending.first else { return }
        MiningQueue.recordMined(MiningQueue.statsWord(of: done.url))
""", """        guard let done = sending.first else { return }
        awaiting = nil
        MiningQueue.recordMined(MiningQueue.statsWord(of: done.url))
""", "queue callback")

# ---------- resetting the statistics keeps the words imported from Anki ----------
s = once(s, """    func reset() {
        let token = UUID().uuidString
        _ = try? Storage.stats.set("{\\"days\\":{},\\"resetToken\\":\\"" + token + "\\"}")
        reload()
    }
""", """    /// Reading and mined words start again; the words imported from Anki stay (they are not statistics).
    func reset() {
        reload()
        var root: [String: Any] = ["days": [String: Any](), "resetToken": UUID().uuidString]
        if !known.isEmpty {
            root["known"] = known
        }
        guard let data = try? JSONSerialization.data(withJSONObject: root),
              let text = String(data: data, encoding: .utf8) else { return }
        _ = try? Storage.stats.set(text)
        reload()
    }
""", "app reset")

# ---------- the file player: after the lookup, playing only if it was playing ----------
s = once(s, "    @State private var ankiReturning = false\n",
         "    @State private var ankiReturning = false\n"
         "    /// playing when a word was tapped: closing the lookup goes on only then\n"
         "    @State private var lookupWasPlaying = false\n", "player lookup state")
s = once(s, """    private func openLookup() {
        lookupWord = line
        coordinator.playerLayer?.pause()
""", """    private func openLookup() {
        if !showLookup {
            lookupWasPlaying = coordinator.playerLayer?.player.isPlaying ?? playing
        }
        lookupWord = line
        coordinator.playerLayer?.pause()
""", "player open lookup")
s = once(s, """        .onChange(of: showLookup) { shown in
            if !shown {
                coordinator.playerLayer?.play()
            }
        }
""", """        .onChange(of: showLookup) { shown in
            if !shown, lookupWasPlaying {
                coordinator.playerLayer?.play()
            }
        }
""", "player close lookup")
s = once(s, """                    showLookup = false
                    if delay == 0.1 {
                        coordinator.playerLayer?.play()
""", """                    showLookup = false
                    guard lookupWasPlaying else { continue }
                    if delay == 0.1 {
                        coordinator.playerLayer?.play()
""", "player anki return")

# ---------- the YouTube player: the same, and the caption timer ----------
s = once(s, """    @State private var forcedLandscape = false
    /// kept by the view""", """    @State private var forcedLandscape = false
    @State private var lookupWasPlaying = false
    /// kept by the view""", "youtube lookup state")
s = once(s, """    private func openLookup() {
        lookupWord = player.line
        player.pause()
""", """    private func openLookup() {
        if !showLookup {
            lookupWasPlaying = player.playing
        }
        lookupWord = player.line
        player.pause()
""", "youtube open lookup")
s = once(s, """        .onChange(of: showLookup) { shown in
            if !shown {
                player.play()
            }
        }
""", """        .onChange(of: showLookup) { shown in
            if !shown, lookupWasPlaying {
                player.play()
            }
        }
""", "youtube close lookup")
s = once(s, """                    try? await Task.sleep(nanoseconds: UInt64(delay * 1_000_000_000))
                }
                player.play()
""", """                    try? await Task.sleep(nanoseconds: UInt64(delay * 1_000_000_000))
                }
                if lookupWasPlaying {
                    player.play()
                }
""", "youtube anki return")
s = once(s, """        // the line follows the video between the reports of the page (about five a second)
        timer = Timer.scheduledTimer(withTimeInterval: 0.1, repeats: true) { [weak self] _ in
            Task { @MainActor in
                self?.updateLine()
            }
        }
    }
""", """        startTimer()
    }

    /// The line follows the video between the reports of the page (about five a second).
    func startTimer() {
        guard timer == nil else { return }
        timer = Timer.scheduledTimer(withTimeInterval: 0.1, repeats: true) { [weak self] _ in
            Task { @MainActor in
                self?.updateLine()
            }
        }
    }
""", "youtube timer")
s = once(s, """    private func start() {
        guard !started else { return }
        started = true
        subDelay = UserDefaults.standard.double(forKey: "subdelay." + progressName)
""", """    private func start() {
        // the screen can appear again after onDisappear stopped the timer
        player.startTimer()
        guard !started else { return }
        started = true
        subDelay = UserDefaults.standard.double(forKey: "subdelay." + progressName)
""", "youtube start")
hv.write_text(s, encoding="utf-8")

# ---------- the Safari extension: resetting keeps the imported words ----------
st = pathlib.Path("src/main/src/extension/stats.ts")
t = st.read_text(encoding="utf-8")
t = once(t, """      const token = String(Date.now());
      await removeKeys(allBucketKeys());
      await setToken(token);
      await saveStats({ days: {}, resetToken: token });
""", """      const token = String(Date.now());
      // the words imported from Anki are not statistics: they stay
      const old = await loadStats();
      await removeKeys(allBucketKeys());
      await setToken(token);
      const fresh: StatsData = { days: {}, resetToken: token };
      if (old.known !== undefined) fresh.known = old.known;
      await saveStats(fresh);
""", "extension reset")
st.write_text(t, encoding="utf-8")
print("v1.65 fixes applied")
