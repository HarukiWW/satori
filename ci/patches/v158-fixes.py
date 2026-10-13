# v1.58: better known-word matching (merged expressions by their parts, no Latin, no reduplicated onomatopoeia, a noun
# through its verb, the vocabulary from the highlight range with the range itself counting as half known); folder
# badges from the episodes inside; live frames while swiping; a green-yellow-red coverage badge; covers instead of
# icons (the picture attached to the file, otherwise a frame taken while watching).
import pathlib

hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


# ---------- the parts of a merged token ----------
s = once(s, '    var pos2: String = ""\n}\n\nstruct LookupEntry',
         '    var pos2: String = ""\n    /// the parts of an expression the tokenizer merged (ここ + に)\n    var parts: [LookupToken] = []\n}\n\nstruct LookupEntry', "parts field")
s = once(s, '''            tokens.append(LookupToken(id: i,
                                      text: t["text"] as? String ?? "",
                                      start: t["start"] as? Int ?? 0,
                                      base: t["base"] as? String ?? "",
                                      reading: t["reading"] as? String ?? "",
                                      pos: t["pos"] as? String ?? "",
                                      pos2: t["pos2"] as? String ?? ""))
''', '''            tokens.append(NativeLookup.token(t, id: i))
''', "token builder use")
s = once(s, "enum NativeLookup {\n", '''enum NativeLookup {
    /// A token of the backend JSON, with the parts of a merged expression.
    static func token(_ t: [String: Any], id: Int, withParts: Bool = true) -> LookupToken {
        var result = LookupToken(id: id,
                                 text: t["text"] as? String ?? "",
                                 start: t["start"] as? Int ?? 0,
                                 base: t["base"] as? String ?? "",
                                 reading: t["reading"] as? String ?? "",
                                 pos: t["pos"] as? String ?? "",
                                 pos2: t["pos2"] as? String ?? "")
        if withParts, let children = t["children"] as? [[String: Any]], children.count > 1 {
            var parts: [LookupToken] = []
            for (index, child) in children.enumerated() {
                parts.append(NativeLookup.token(child, id: index, withParts: false))
            }
            result.parts = parts
        }
        return result
    }

''', "token builder")

# ---------- the analysis ----------
a = s.index("    nonisolated static func analyze(of file: URL, index: KnownWordsIndex, level: Int) -> EpisodeAnalysis? {")
b = s.index("    /// The known word index, built once", a)
s = s[:a] + '''    /// easy / normal / hard from the share of known words and of clear lines.
    nonisolated static func classify(known: Double, clear: Double) -> Int {
        if known >= 0.90 && clear >= 0.65 { return 0 }
        if known >= 0.80 && clear >= 0.40 { return 1 }
        return 2
    }

    /// The vocabulary: words more frequent than the start of the highlight range are known, the range itself is
    /// half known; without a range in the settings it comes from the level.
    static func frequencyBand(level: Int) -> (lower: Int, upper: Int) {
        let byLevel: [Int: Int] = [5: 800, 4: 1500, 3: 3700, 2: 6000, 1: 10000]
        let fallback = byLevel[level] ?? 800
        guard let json = try? Storage.config.get(), let data = json.data(using: .utf8),
              let root = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any],
              let lower = (root["highlight.min"] as? NSNumber)?.intValue, lower > 0 else {
            return (fallback, fallback * 2)
        }
        let upper = (root["highlight.max"] as? NSNumber)?.intValue ?? lower * 2
        return (lower, max(lower, upper))
    }

    /// One pass over the subtitles. Content words only (no particles, auxiliaries, symbols, interjections, proper
    /// nouns, numbers, katakana-only words, Latin, reduplicated onomatopoeia). A word counts 1 when known: a card in
    /// any form, JLPT up to the level, more frequent than the band; 0.5 inside the band; merged expressions by their
    /// parts; a noun made of a verb stem (守り) through the verb.
    nonisolated static func analyze(of file: URL, index: KnownWordsIndex, level: Int, lower: Int, upper: Int) -> EpisodeAnalysis? {
        var readings: [String: String] = [:]
        func reading(of base: String) -> String {
            if let saved = readings[base] {
                return saved
            }
            let value = KnownWordsIndex.isKana(base) ? HighlightData.hiragana(base) : autoreleasepool {
                HighlightData.hiragana(NativeLookup.tokenize(base, charAt: 0).tokens.map { $0.reading }.joined())
            }
            readings[base] = value
            return value
        }
        func knowledge(base: String, text: String, tokenReading: String) -> Double {
            if index.forms.contains(base) || index.forms.contains(text) { return 1 }
            let kana = reading(of: base)
            if !kana.isEmpty {
                if index.kanaReadings.contains(kana) { return 1 }
                if let kanji = index.kanjiByReading[kana],
                   KnownWordsIndex.isKana(text) || !kanji.isDisjoint(with: KnownWordsIndex.kanji(base)) { return 1 }
            }
            let lookup = kana.isEmpty ? HighlightData.hiragana(tokenReading) : kana
            let jlpt = HighlightData.jlptLevel(base: base, reading: lookup)
            if jlpt > 0, jlpt >= level { return 1 }
            let rank = HighlightData.rank(base: base, reading: lookup, dict: "main", text: text)
                ?? HighlightData.rank(base: base, reading: "", dict: "main", text: text)
            if let rank {
                if rank <= lower { return 1 }
                if rank <= upper { return 0.5 }
            }
            return 0
        }
        func counted(_ token: LookupToken) -> Bool {
            guard token.text.unicodeScalars.contains(where: { KnownWordsIndex.isJapanese($0) }) else { return false }
            if token.pos.hasPrefix("助詞") || token.pos.hasPrefix("助動詞") || token.pos.contains("記号") { return false }
            if token.pos.hasPrefix("感動詞") || token.pos2.contains("固有名詞") || token.pos2.contains("数詞") { return false }
            if KnownWordsIndex.isKatakana(token.text) || KnownWordsIndex.isReduplicated(token.text) { return false }
            return true
        }
        func score(_ token: LookupToken) -> Double {
            let base = token.base.isEmpty ? token.text : token.base
            var best = knowledge(base: base, text: token.text, tokenReading: token.reading)
            if best < 1, !token.parts.isEmpty {
                let content = token.parts.filter { counted($0) }
                if content.isEmpty {
                    return 1
                }
                var weakest = 1.0
                for part in content {
                    let partBase = part.base.isEmpty ? part.text : part.base
                    weakest = min(weakest, knowledge(base: partBase, text: part.text, tokenReading: part.reading))
                }
                best = max(best, weakest)
            }
            if best < 1, let verb = KnownWordsIndex.verbOfNoun(base) {
                best = max(best, knowledge(base: verb, text: verb, tokenReading: ""))
            }
            return best
        }

        var total = 0.0
        var familiar = 0.0
        var wordCount = 0
        var lines = 0
        var clearLines = 0
        var unknownCounts: [String: UnknownWord] = [:]
        for cue in EmbeddedSubtitles.cues(fromFile: file) {
            guard !cue.text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { continue }
            let tokens = autoreleasepool { NativeLookup.tokenize(cue.text, charAt: 0).tokens }
            var words = 0
            var missing = 0.0
            for token in tokens where counted(token) {
                words += 1
                let value = score(token)
                missing += 1 - value
                if value < 1 {
                    let base = token.base.isEmpty ? token.text : token.base
                    let count = (unknownCounts[base]?.count ?? 0) + 1
                    unknownCounts[base] = UnknownWord(word: base, reading: reading(of: base), count: count, partial: value > 0)
                }
            }
            guard words > 0 else { continue }
            total += Double(words)
            familiar += Double(words) - missing
            wordCount += words
            lines += 1
            if missing <= 1.0 {
                clearLines += 1
            }
        }
        guard total > 0, lines > 0 else { return nil }
        let known = familiar / total
        let clear = Double(clearLines) / Double(lines)
        let difficulty: Int? = wordCount >= 50 ? classify(known: known, clear: clear) : nil
        let list = unknownCounts.values.sorted { first, second in
            first.count != second.count ? first.count > second.count : first.word < second.word
        }
        return EpisodeAnalysis(coverage: Int((known * 100).rounded()), difficulty: difficulty, knownShare: known,
                               clearShare: clear, words: wordCount, lines: lines, unknown: list)
    }

''' + s[b:]

a = s.index("    /// Coverage and difficulty of every video with Jimaku subtitles")
b = s.index("    private static let videoExtensions", a)
s = s[:a] + '''    /// Coverage and difficulty of every video with Jimaku subtitles here and in the folders here (a folder shows the
    /// average of its episodes); kept until the known words, the level, the band or the file change.
    func updateCoverage() {
        var candidates: [(String, URL)] = []
        var folderVideos: [String: [String]] = [:]
        let fm = FileManager.default
        for item in items {
            if item.isFolder {
                let inside = (try? fm.contentsOfDirectory(at: item.url, includingPropertiesForKeys: nil)) ?? []
                var names: [String] = []
                for video in inside where VideoLibraryStore.isVideo(video.lastPathComponent) {
                    if let file = VideoLibraryStore.jimakuFile(for: video) {
                        candidates.append((video.lastPathComponent, file))
                        names.append(video.lastPathComponent)
                    }
                }
                folderVideos[item.url.lastPathComponent] = names
            } else if VideoLibraryStore.isVideo(item.url.lastPathComponent),
                      let file = VideoLibraryStore.jimakuFile(for: item.url) {
                candidates.append((item.url.lastPathComponent, file))
            }
        }
        guard !candidates.isEmpty else { return }
        let knownCount = HighlightData.minedWords().count
        let level = VideoLibraryStore.userLevel
        let band = VideoLibraryStore.frequencyBand(level: level)
        var pending: [(String, URL, String)] = []
        for (name, file) in candidates {
            let size = ((try? fm.attributesOfItem(atPath: file.path)[.size]) as? Int) ?? 0
            let stamp = "5|" + String(level) + "|" + String(band.lower) + "|" + String(band.upper) + "|"
                + String(knownCount) + "|" + String(size)
            if let saved = UserDefaults.standard.string(forKey: "coverage." + name), saved.hasPrefix(stamp + "|") {
                let parts = saved.dropFirst(stamp.count + 1).split(separator: "|")
                if parts.count == 4, let value = Int(parts[0]), let hardness = Int(parts[1]),
                   let known = Int(parts[2]), let clear = Int(parts[3]) {
                    coverage[name] = value
                    difficulty[name] = hardness >= 0 ? hardness : nil
                    shares[name] = (Double(known) / 1000, Double(clear) / 1000, value)
                    continue
                }
            }
            pending.append((name, file, stamp))
        }
        updateFolders(folderVideos)
        guard !pending.isEmpty, !coverageRunning else { return }
        coverageRunning = true
        Task { @MainActor in
            defer { coverageRunning = false }
            let index = await knownWordsIndex()
            for (name, file, stamp) in pending {
                CrashTrail.mark("покрытие: начало " + name)
                let result = await Task.detached(priority: .utility) {
                    VideoLibraryStore.analyze(of: file, index: index, level: level, lower: band.lower, upper: band.upper)
                }.value
                CrashTrail.mark("покрытие: готово " + name)
                guard let result else { continue }
                coverage[name] = result.coverage
                difficulty[name] = result.difficulty
                shares[name] = (result.knownShare, result.clearShare, result.coverage)
                let known = String(Int((result.knownShare * 1000).rounded()))
                let clear = String(Int((result.clearShare * 1000).rounded()))
                let hardness = String(result.difficulty ?? -1)
                let value = stamp + "|" + String(result.coverage) + "|" + hardness + "|" + known + "|" + clear
                UserDefaults.standard.set(value, forKey: "coverage." + name)
                updateFolders(folderVideos)
            }
        }
    }

    /// known share, clear share and coverage of each analysed video
    private var shares: [String: (known: Double, clear: Double, coverage: Int)] = [:]

    /// A folder: the averages of its analysed episodes.
    private func updateFolders(_ folderVideos: [String: [String]]) {
        for (folder, names) in folderVideos {
            let scored = names.compactMap { shares[$0] }
            guard !scored.isEmpty else { continue }
            let count = Double(scored.count)
            let known = scored.map { $0.known }.reduce(0, +) / count
            let clear = scored.map { $0.clear }.reduce(0, +) / count
            let average = Double(scored.map { $0.coverage }.reduce(0, +)) / count
            coverage[folder] = Int(average.rounded())
            difficulty[folder] = VideoLibraryStore.classify(known: known, clear: clear)
        }
    }

''' + s[b:]

s = once(s, """        let index = await library.knownWordsIndex()
        let level = VideoLibraryStore.userLevel
        analysis = await Task.detached(priority: .userInitiated) {
            VideoLibraryStore.analyze(of: file, index: index, level: level)
        }.value
""", """        let index = await library.knownWordsIndex()
        let level = VideoLibraryStore.userLevel
        let band = VideoLibraryStore.frequencyBand(level: level)
        analysis = await Task.detached(priority: .userInitiated) {
            VideoLibraryStore.analyze(of: file, index: index, level: level, lower: band.lower, upper: band.upper)
        }.value
""", "words screen analysis")
s = once(s, """struct UnknownWord: Identifiable {
    var id: String { word }
    let word: String
    let reading: String
    let count: Int
}
""", """struct UnknownWord: Identifiable {
    var id: String { word }
    let word: String
    let reading: String
    let count: Int
    /// inside the frequency band of the highlight settings: counted as half known
    var partial: Bool = false
}
""", "unknown word partial")
s = once(s, """                                Text("×" + String(word.count))
                                    .foregroundColor(.secondary)
""", """                                if word.partial {
                                    Text("50/50")
                                        .font(.caption2.bold())
                                        .foregroundColor(.orange)
                                }
                                Text("×" + String(word.count))
                                    .foregroundColor(.secondary)
""", "partial mark")

s = once(s, "    static func isKatakana(_ text: String) -> Bool {\n", """    /// Kana, kanji or the iteration mark: Latin letters (song lyrics) are not Japanese words.
    static func isJapanese(_ scalar: Unicode.Scalar) -> Bool {
        let v = scalar.value
        return (0x3040 ... 0x30FF).contains(v) || (0x3400 ... 0x4DBF).contains(v) || (0x4E00 ... 0x9FFF).contains(v)
            || (0xF900 ... 0xFAFF).contains(v) || v == 0x3005
    }

    /// ふわふわ, きらきら: reduplicated kana onomatopoeia.
    static func isReduplicated(_ text: String) -> Bool {
        let letters = Array(text)
        guard letters.count >= 4, letters.count % 2 == 0, isKana(text) else { return false }
        let half = letters.count / 2
        return Array(letters[0 ..< half]) == Array(letters[half...])
    }

    /// 守り → 守る, 騒めき → 騒めく: a noun made of the stem of a godan verb.
    static func verbOfNoun(_ word: String) -> String? {
        guard word.count >= 2, let last = word.last,
              word.dropLast().unicodeScalars.contains(where: { statIsKanji($0) }) else { return nil }
        let endings: [Character: Character] = ["り": "る", "き": "く", "し": "す", "ち": "つ", "に": "ぬ",
                                               "び": "ぶ", "み": "む", "ぎ": "ぐ", "い": "う"]
        guard let ending = endings[last] else { return nil }
        return String(word.dropLast()) + String(ending)
    }

    static func isKatakana(_ text: String) -> Bool {
""", "index helpers")

# ---------- badges: folders too, coverage in colour ----------
s = once(s, """                    if !item.isFolder, let hardness = library.difficulty[name] {""",
         """                    if let hardness = library.difficulty[name] {""", "folder difficulty")
s = once(s, """                            .highPriorityGesture(TapGesture().onEnded { wordsVideo = item.url })""",
         """                            .highPriorityGesture(TapGesture().onEnded {
                                if !item.isFolder {
                                    wordsVideo = item.url
                                }
                            })""", "badge tap videos")
s = once(s, """                    if !item.isFolder, let value = library.coverage[name] {
                        Text(String(value) + "%")
                            .font(.caption2.bold())
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(Color.green.opacity(value >= 90 ? 0.35 : 0.15))
                            .cornerRadius(4)
                    }
""", """                    if let value = library.coverage[name] {
                        Text(String(value) + "%")
                            .font(.caption2.bold())
                            .foregroundColor(.black)
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(coverageColor(value))
                            .cornerRadius(4)
                    }
""", "coverage colour")
s = once(s, "    private func label(_ item: VideoLibraryStore.Item) -> some View {\n", """    /// Green at 100 %, yellow at 55 %, red at 0 %.
    private func coverageColor(_ value: Int) -> Color {
        let v = Double(min(max(value, 0), 100))
        var hue: Double = 0.15 * v / 55
        if v >= 55 {
            hue = 0.15 + 0.18 * (v - 55) / 45
        }
        return Color(hue: hue, saturation: 0.75, brightness: 0.88)
    }

    private func label(_ item: VideoLibraryStore.Item) -> some View {
""", "colour func")

# ---------- covers ----------
s = once(s, """            Image(systemName: item.isFolder ? "folder" : symbol(for: name))
                .font(.title2)
                .foregroundColor(.accentColor)
                .frame(width: 32)
""", """            Group {
                if !item.isFolder, let thumb = VideoThumbnails.image(for: name) {
                    Image(uiImage: thumb)
                        .resizable()
                        .scaledToFill()
                        .frame(width: 48, height: 48)
                        .clipShape(Circle())
                } else {
                    Image(systemName: item.isFolder ? "folder" : symbol(for: name))
                        .font(.title2)
                        .foregroundColor(.accentColor)
                        .frame(width: 48)
                }
            }
""", "row cover")
s = once(s, "    @Published var coverage: [String: Int] = [:]\n",
         "    @Published var coverage: [String: Int] = [:]\n    /// changes when a cover is ready, so the rows redraw\n    @Published var thumbStamp = 0\n", "thumb stamp")
s = once(s, "    func reload() {\n        CrashTrail.mark(\"список: обновление\")\n        defer { updateCoverage() }\n",
         "    func reload() {\n        CrashTrail.mark(\"список: обновление\")\n        defer {\n            updateCoverage()\n            updateThumbnails()\n        }\n", "thumbs on reload")
s = once(s, "    private func updateFolders(_ folderVideos: [String: [String]]) {\n", """    /// Covers for the videos here that have none yet: the picture attached to the file.
    private func updateThumbnails() {
        let missing = items.filter { !$0.isFolder && VideoLibraryStore.isVideo($0.url.lastPathComponent)
            && !VideoThumbnails.exists($0.url.lastPathComponent) && !VideoThumbnails.tried.contains($0.url.lastPathComponent) }
        guard !missing.isEmpty else { return }
        for item in missing {
            VideoThumbnails.tried.insert(item.url.lastPathComponent)
        }
        let urls = missing.map { $0.url }
        Task { @MainActor in
            for url in urls {
                let found = await Task.detached(priority: .utility) { VideoThumbnails.attachedCover(of: url) }.value
                if let found {
                    VideoThumbnails.save(found, for: url.lastPathComponent)
                    thumbStamp += 1
                }
            }
        }
    }

    private func updateFolders(_ folderVideos: [String: [String]]) {
""", "update thumbnails")
s = once(s, '            UserDefaults.standard.removeObject(forKey: "coverage." + name)\n',
         '            UserDefaults.standard.removeObject(forKey: "coverage." + name)\n            VideoThumbnails.remove(name)\n', "delete cover")

# the player keeps a frame as the cover when the file has no picture
s = once(s, "    @State private var endHandled = false\n",
         "    @State private var endHandled = false\n    @State private var thumbChecked = false\n", "thumb state")
s = once(s, "        detectSkipSegments()\n        checkEnd()\n    }\n",
         "        detectSkipSegments()\n        checkEnd()\n        saveCoverFrame()\n    }\n\n"
         "    /// A video without an attached picture gets a frame of its own as the cover.\n"
         "    private func saveCoverFrame() {\n"
         "        guard !thumbChecked, playing, position > 30, let player = coordinator.playerLayer?.player else { return }\n"
         "        thumbChecked = true\n"
         "        let name = url.lastPathComponent\n"
         "        guard !VideoThumbnails.exists(name) else { return }\n"
         "        Task { @MainActor in\n"
         "            if let frame = await player.thumbnailImageAtCurrentTime() {\n"
         "                VideoThumbnails.save(UIImage(cgImage: frame), for: name)\n"
         "            }\n"
         "        }\n"
         "    }\n", "player cover")

# ---------- live frames while swiping ----------
s = once(s, """            swipeStart = position
            swipeWasPlaying = playing
            if playing {
                coordinator.playerLayer?.pause()
            }
""", """            swipeStart = position
            swipeWasPlaying = playing
            // frames show while playing: muted and seeking to key frames during the swipe, like nPlayer
            options.isAccurateSeek = false
            coordinator.playerLayer?.player.isMuted = true
            if !playing {
                coordinator.playerLayer?.play()
            }
""", "swipe start")
s = once(s, """        if now - lastSwipeSeek > 0.2 {
            lastSwipeSeek = now
            coordinator.playerLayer?.seek(time: swipeTarget, autoPlay: false) { _ in }
        }
""", """        if now - lastSwipeSeek > 0.15 {
            lastSwipeSeek = now
            coordinator.playerLayer?.seek(time: swipeTarget, autoPlay: true) { _ in }
        }
""", "swipe seeks")
s = once(s, """        let target = swipeTarget
        swipeStart = nil
        position = target
        coordinator.playerLayer?.seek(time: target, autoPlay: swipeWasPlaying) { _ in }
""", """        let target = swipeTarget
        let wasPlaying = swipeWasPlaying
        swipeStart = nil
        position = target
        options.isAccurateSeek = true
        let layer = coordinator.playerLayer
        layer?.seek(time: target, autoPlay: true) { _ in
            layer?.player.isMuted = false
            if !wasPlaying {
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.2) {
                    layer?.pause()
                }
            }
        }
""", "swipe end")

s = s.rstrip("\n") + '''

/// Covers of the videos: the picture attached to the file (MKV attachments, mp4 cover art) or a frame of the video.
enum VideoThumbnails {
    /// files already looked at in this session
    static var tried = Set<String>()
    private static var memory: [String: UIImage] = [:]

    private static var folder: URL {
        let base = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask)[0].appendingPathComponent("covers")
        try? FileManager.default.createDirectory(at: base, withIntermediateDirectories: true)
        return base
    }

    private static func file(_ name: String) -> URL {
        folder.appendingPathComponent(name + ".jpg")
    }

    static func exists(_ name: String) -> Bool {
        memory[name] != nil || FileManager.default.fileExists(atPath: file(name).path)
    }

    static func image(for name: String) -> UIImage? {
        if let cached = memory[name] {
            return cached
        }
        guard let image = UIImage(contentsOfFile: file(name).path) else { return nil }
        memory[name] = image
        return image
    }

    static func save(_ image: UIImage, for name: String) {
        let scale = min(1, 240 / max(min(image.size.width, image.size.height), 1))
        let size = CGSize(width: (image.size.width * scale).rounded(), height: (image.size.height * scale).rounded())
        let format = UIGraphicsImageRendererFormat()
        format.scale = 1
        let small = UIGraphicsImageRenderer(size: size, format: format).image { _ in
            image.draw(in: CGRect(origin: .zero, size: size))
        }
        memory[name] = small
        try? small.jpegData(compressionQuality: 0.8)?.write(to: file(name))
    }

    static func remove(_ name: String) {
        memory[name] = nil
        try? FileManager.default.removeItem(at: file(name))
    }

    /// The picture attached to the file; "cover" in its name is preferred.
    static func attachedCover(of video: URL) -> UIImage? {
        var opened: UnsafeMutablePointer<AVFormatContext>? = nil
        guard avformat_open_input(&opened, video.path, nil, nil) == 0, let fmt = opened else { return nil }
        defer {
            var closing: UnsafeMutablePointer<AVFormatContext>? = fmt
            avformat_close_input(&closing)
        }
        guard let streams = fmt.pointee.streams else { return nil }
        var best: UIImage? = nil
        var bestScore = -1
        for i in 0 ..< Int(fmt.pointee.nb_streams) {
            guard let st = streams[i], let par = st.pointee.codecpar else { continue }
            var data: Data? = nil
            if par.pointee.codec_type == AVMEDIA_TYPE_ATTACHMENT, let extra = par.pointee.extradata,
               par.pointee.extradata_size > 0, tag(st, "mimetype").lowercased().hasPrefix("image/") {
                data = Data(bytes: extra, count: Int(par.pointee.extradata_size))
            } else if (st.pointee.disposition & 0x0400) != 0, st.pointee.attached_pic.size > 0,   // AV_DISPOSITION_ATTACHED_PIC
                      let bytes = st.pointee.attached_pic.data {
                data = Data(bytes: bytes, count: Int(st.pointee.attached_pic.size))
            }
            guard let data, let image = UIImage(data: data) else { continue }
            let name = tag(st, "filename").lowercased()
            let score = name.contains("cover") ? 3 : ((name.contains("poster") || name.contains("folder")) ? 2 : 1)
            if score > bestScore {
                best = image
                bestScore = score
            }
        }
        return best
    }

    private static func tag(_ stream: UnsafeMutablePointer<AVStream>, _ key: String) -> String {
        guard let entry = av_dict_get(stream.pointee.metadata, key, nil, 0), let value = entry.pointee.value else { return "" }
        return String(cString: value)
    }
}
'''
hv.write_text(s, encoding="utf-8")
print("v1.58 fixes applied")
