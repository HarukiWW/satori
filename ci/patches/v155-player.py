# v1.55: difficulty badge (easy / normal / hard) from the Jimaku subtitles, the known words and the level chosen in the
# settings; a double tap on the picture replays the current subtitle line (the previous one in its first second)
# from 0.4 s before it.
import pathlib

hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


# ---------- difficulty ----------
s = once(s, "    @Published var coverage: [String: Int] = [:]\n",
         "    @Published var coverage: [String: Int] = [:]\n    /// 0 easy, 1 normal, 2 hard\n    @Published var difficulty: [String: Int] = [:]\n", "difficulty state")
s = once(s, "        coverage[name] = nil\n", "        coverage[name] = nil\n        difficulty[name] = nil\n", "delete difficulty")

a = s.index("    /// Coverage of every video with Jimaku subtitles")
b = s.index("    private static let videoExtensions", a)
s = s[:a] + '''    /// Easy / normal / hard. Known: added and imported words in any form, and the JLPT words up to the user's level.
    /// Words are content words (no particles, auxiliaries, symbols) and not katakana-only (names, loanwords).
    /// easy: at least 90 % of the words known and at least 65 % of the lines with at most one unknown word;
    /// normal: at least 80 % and 40 %; otherwise hard.
    nonisolated static func difficulty(of file: URL, index: KnownWordsIndex, level: Int) -> Int? {
        var total = 0
        var familiar = 0
        var lines = 0
        var clearLines = 0
        var readings: [String: String] = [:]
        for cue in EmbeddedSubtitles.cues(fromFile: file) {
            guard !cue.text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { continue }
            let tokens = autoreleasepool { NativeLookup.tokenize(cue.text, charAt: 0).tokens }
            var words = 0
            var unknown = 0
            for token in tokens {
                guard token.text.unicodeScalars.contains(where: { CharacterSet.letters.contains($0) }) else { continue }
                if token.pos.hasPrefix("助詞") || token.pos.hasPrefix("助動詞") || token.pos.contains("記号") { continue }
                if KnownWordsIndex.isKatakana(token.text) { continue }
                words += 1
                let base = token.base.isEmpty ? token.text : token.base
                if index.forms.contains(base) || index.forms.contains(token.text) { continue }
                let reading: String
                if let saved = readings[base] {
                    reading = saved
                } else {
                    reading = KnownWordsIndex.isKana(base) ? HighlightData.hiragana(base) : autoreleasepool {
                        HighlightData.hiragana(NativeLookup.tokenize(base, charAt: 0).tokens.map { $0.reading }.joined())
                    }
                    readings[base] = reading
                }
                if !reading.isEmpty {
                    if index.kanaReadings.contains(reading) { continue }
                    if let kanji = index.kanjiByReading[reading],
                       KnownWordsIndex.isKana(token.text) || !kanji.isDisjoint(with: KnownWordsIndex.kanji(base)) { continue }
                }
                let jlptReading = reading.isEmpty ? HighlightData.hiragana(token.reading) : reading
                let jlpt = HighlightData.jlptLevel(base: base, reading: jlptReading)
                if jlpt > 0, jlpt >= level { continue }
                unknown += 1
            }
            guard words > 0 else { continue }
            total += words
            familiar += words - unknown
            lines += 1
            if unknown <= 1 { clearLines += 1 }
        }
        guard total >= 50, lines > 0 else { return nil }
        let known = Double(familiar) / Double(total)
        let clear = Double(clearLines) / Double(lines)
        if known >= 0.90 && clear >= 0.65 { return 0 }
        if known >= 0.80 && clear >= 0.40 { return 1 }
        return 2
    }

    /// Coverage and difficulty of every video with Jimaku subtitles; kept until the known words, the level or the file change.
    func updateCoverage() {
        let candidates: [(String, URL)] = items.compactMap { item in
            guard !item.isFolder, VideoLibraryStore.isVideo(item.url.lastPathComponent) else { return nil }
            let base = item.url.deletingPathExtension()
            for ext in ["srt", "ass", "ssa", "vtt"] {
                let file = base.appendingPathExtension("jimaku." + ext)
                if FileManager.default.fileExists(atPath: file.path) {
                    return (item.url.lastPathComponent, file)
                }
            }
            return nil
        }
        guard !candidates.isEmpty else { return }
        let known = HighlightData.minedWords()
        _ = HighlightData.jlptLevel(base: "の", reading: "の")   // loads the JLPT table here, on the main thread
        let savedLevel = UserDefaults.standard.integer(forKey: "ykUserLevel")
        let level = (1 ... 5).contains(savedLevel) ? savedLevel : 5
        var pending: [(String, URL, String)] = []
        for (name, file) in candidates {
            let size = ((try? FileManager.default.attributesOfItem(atPath: file.path)[.size]) as? Int) ?? 0
            let stamp = "3|" + String(level) + "|" + String(known.count) + "|" + String(size)
            if let saved = UserDefaults.standard.string(forKey: "coverage." + name), saved.hasPrefix(stamp + "|") {
                let parts = saved.dropFirst(stamp.count + 1).split(separator: "|")
                if parts.count == 2, let value = Int(parts[0]), let hardness = Int(parts[1]) {
                    coverage[name] = value
                    difficulty[name] = hardness >= 0 ? hardness : nil
                    continue
                }
            }
            pending.append((name, file, stamp))
        }
        guard !pending.isEmpty, !coverageRunning else { return }
        coverageRunning = true
        Task { @MainActor in
            defer { coverageRunning = false }
            let index: KnownWordsIndex
            if let saved = knownIndex, saved.count == known.count {
                index = saved.index
            } else {
                CrashTrail.mark("покрытие: индекс знакомых слов (" + String(known.count) + ")")
                index = await Task.detached(priority: .utility) { KnownWordsIndex(known) }.value
                knownIndex = (known.count, index)
                CrashTrail.mark("покрытие: индекс готов")
            }
            for (name, file, stamp) in pending {
                CrashTrail.mark("покрытие: начало " + name)
                let result = await Task.detached(priority: .utility) {
                    (VideoLibraryStore.coverage(of: file, index: index),
                     VideoLibraryStore.difficulty(of: file, index: index, level: level))
                }.value
                CrashTrail.mark("покрытие: готово " + name)
                if let value = result.0 {
                    coverage[name] = value
                    difficulty[name] = result.1
                    UserDefaults.standard.set(stamp + "|" + String(value) + "|" + String(result.1 ?? -1),
                                              forKey: "coverage." + name)
                }
            }
        }
    }

''' + s[b:]

s = once(s, "    static func isKana(_ text: String) -> Bool {\n", """    static func isKatakana(_ text: String) -> Bool {
        !text.isEmpty && text.unicodeScalars.allSatisfy { (0x30A0 ... 0x30FF).contains($0.value) }
    }

    static func isKana(_ text: String) -> Bool {
""", "katakana")

s = once(s, "                    if !item.isFolder, let value = library.coverage[name] {\n", """                    if !item.isFolder, let hardness = library.difficulty[name] {
                        let step = min(max(hardness, 0), 2)
                        Text(["easy", "normal", "hard"][step])
                            .font(.caption2.bold())
                            .foregroundColor(step == 2 ? .white : .black)
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background([Color.green, Color.yellow, Color.red][step].opacity(0.85))
                            .cornerRadius(4)
                    }
                    if !item.isFolder, let value = library.coverage[name] {
""", "difficulty badge")

# the level in the settings
s = once(s, "    @State private var trail = \"\"\n",
         "    @State private var trail = \"\"\n    @AppStorage(\"ykUserLevel\") private var userLevel = 5\n", "level storage")
s = once(s, '            Section {\n                Toggle("Использовать Anki"', '''            Section {
                Picker("Уровень", selection: $userLevel) {
                    Text("N5").tag(5)
                    Text("N4").tag(4)
                    Text("N3").tag(3)
                    Text("N2").tag(2)
                    Text("N1").tag(1)
                }
            } header: {
                Text("Мой уровень японского")
            } footer: {
                Text("Слова JLPT до этого уровня считаются знакомыми при оценке сложности серий (easy / normal / hard).")
            }

            Section {
                Toggle("Использовать Anki"''', "level section")

# ---------- double tap: the line again ----------
s = once(s, """                    Color.black.opacity(0.001)
                        .contentShape(Rectangle())
                        .onTapGesture {
                            if showLookup {""", """                    Color.black.opacity(0.001)
                        .contentShape(Rectangle())
                        .onTapGesture(count: 2) { replayLine() }
                        .onTapGesture {
                            if showLookup {""", "double tap")
s = once(s, "    private func skipLine(_ direction: Int) {\n", """    private func replayLine() {
        let starts = (usingExternal ? externalCues : embeddedCues)
            .filter { !$0.text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }
            .map { $0.start + subDelay }
            .sorted()
        var target = max(0, position - 5)
        if let start = starts.last(where: { $0 <= position + 0.05 }) {
            target = start
            // a line that has just begun: the previous one
            if position - start < 1.0, let previous = starts.last(where: { $0 < start - 0.05 }) {
                target = previous
            }
            // a moment before the line, for the ear
            target = max(0, target - 0.4)
        }
        position = target
        coordinator.playerLayer?.seek(time: target, autoPlay: true) { _ in }
    }

    private func skipLine(_ direction: Int) {
""", "replay")

hv.write_text(s, encoding="utf-8")
print("v1.55 patch applied")
