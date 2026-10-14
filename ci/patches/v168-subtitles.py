# v1.68: subtitle lines keep up with the video, and words waiting in the mining queue are not highlighted.
# - A line was tokenized on the main thread when it appeared (and once more for the watching statistics): a short
#   stall each time. Lines are now tokenized once (SubtitleTokenCache, v168-token-cache.swift), and both players
#   prepare the next line in the background.
# - The YouTube caption timer ran in the default run loop mode, which stops while a finger is on the screen; it runs
#   in .common now. The page reports the time every 0.1 s instead of 0.2 s.
# - The highlight skipped the words of the statistics only: notes in the mining queue are not there any more (since
#   1.60), so their words stayed highlighted. The queue is checked too; the file player sets the queue hook when it
#   opens, not at the first lookup.
import pathlib


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


def times(text, old, new, count, label):
    assert text.count(old) == count, "pattern not found " + str(count) + " times: " + label
    return text.replace(old, new)


here = pathlib.Path(__file__).resolve().parent
hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")
s = s.rstrip("\n") + "\n" + (here / "v168-token-cache.swift").read_text(encoding="utf-8")

# ---------- the subtitle bar and the watching statistics use the cache ----------
s = once(s, r'''        let clean = text.replacingOccurrences(of: "\\N", with: " ")
            .replacingOccurrences(of: "\n", with: " ")
            .trimmingCharacters(in: .whitespaces)
        var result = NativeLookup.tokenize(clean, charAt: 0).tokens
''', r'''        let clean = SubtitleTokenCache.clean(text)
        var result = SubtitleTokenCache.shared.tokens(clean)
''', "subtitle bar")
s = times(s, "watchWords += NativeLookup.tokenize(line, charAt: 0).tokens.filter { token in",
          "watchWords += SubtitleTokenCache.shared.tokens(SubtitleTokenCache.clean(line)).filter { token in", 2,
          "watching words")

# ---------- the next line is prepared ahead ----------
s = once(s, r'''            next = source.filter { $0.start <= t && t < $0.end }.map { $0.text }.joined(separator: "\n")
        }
        if next != line {
            line = next
        }
''', r'''            next = source.filter { $0.start <= t && t < $0.end }.map { $0.text }.joined(separator: "\n")
        }
        if next != line {
            line = next
            SubtitleTokenCache.prefetch(source.first { $0.start > t }?.text)
        }
''', "file player prefetch")
s = once(s, r'''        let next = cues.filter { $0.start <= t && t < $0.end }.map { $0.text }.joined(separator: "\n")
        if next != line {
            line = next
        }
''', r'''        let next = cues.filter { $0.start <= t && t < $0.end }.map { $0.text }.joined(separator: "\n")
        if next != line {
            line = next
            SubtitleTokenCache.prefetch(cues.first { $0.start > t }?.text)
        }
''', "youtube prefetch")

# ---------- the YouTube timer and the page reports ----------
s = once(s, """        guard timer == nil else { return }
        timer = Timer.scheduledTimer(withTimeInterval: 0.1, repeats: true) { [weak self] _ in
            Task { @MainActor in
                self?.updateLine()
            }
        }
""", """        guard timer == nil else { return }
        let ticker = Timer(timeInterval: 0.1, repeats: true) { [weak self] _ in
            Task { @MainActor in
                self?.updateLine()
            }
        }
        // .common: the timer runs while a finger is on the screen too (the default mode stops then)
        RunLoop.main.add(ticker, forMode: .common)
        timer = ticker
""", "youtube timer mode")
s = once(s, "        post({ type: 'tick', t: t, d: d, s: s, title: title });\n      }, 200);\n",
         "        post({ type: 'tick', t: t, d: d, s: s, title: title });\n      }, 100);\n", "page interval")

# ---------- the highlight skips the words in the mining queue ----------
s = once(s, """        let (settings, mined) = cachedSettings()
        guard settings.enabled else { return [:] }
        var result: [Int: Color] = [:]
""", """        let (settings, mined) = cachedSettings()
        guard settings.enabled else { return [:] }
        // notes waiting in the player's mining queue are added words too
        let queued = Set(yomikiriQueuedWordsHook?() ?? [])
        var result: [Int: Color] = [:]
""", "highlight queue")
s = once(s, "        for token in tokens where !token.base.isEmpty && !mined.contains(token.base) && contentPOS.contains(token.pos) {\n",
         "        for token in tokens where !token.base.isEmpty && !mined.contains(token.base) && !queued.contains(token.base)\n"
         "            && contentPOS.contains(token.pos) {\n", "highlight loop")
s = once(s, """        .onReceive(coordinator.subtitleModel.$parts) { parts in
""", """        .onAppear {
            // the highlight of the first lines already knows the words in the mining queue
            yomikiriQueuedWordsHook = {
                MiningQueue.shared.entries.map { MiningQueue.statsWord(of: $0.url) }
            }
        }
        .onReceive(coordinator.subtitleModel.$parts) { parts in
""", "player queue hook")
hv.write_text(s, encoding="utf-8")
print("v1.68 subtitles applied")
