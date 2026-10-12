# v1.46 (player): subtitles at the top or the bottom; a rotate button that forces landscape (also with the rotation
# lock on); lock screen / Control Center player with a frame of the video every ~10 s and playback buttons; watching
# statistics (time, words of the subtitle lines); coverage badge (% of known words in the Jimaku subtitles).
import pathlib

p = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = p.read_text(encoding="utf-8")


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


s = once(s, "import Vision\n", "import Vision\nimport MediaPlayer\n", "import")

# ---------- state ----------
s = once(s, '@AppStorage("ykSharpen") private var ykSharpen: Double = 0',
         '@AppStorage("ykSharpen") private var ykSharpen: Double = 0\n'
         '              @AppStorage("ykSubsTop") private var subsTop = false', "subs position storage")
s = once(s, "    @State private var lastResync: CFTimeInterval = 0\n", '''    @State private var lastResync: CFTimeInterval = 0
    @State private var watchPending: Double = 0
    @State private var watchWords = 0
    @State private var lastWatchTick: CFTimeInterval = 0
    @State private var lastCountedLine = ""
    @State private var forcedLandscape = false
    @State private var nowPlayingReady = false
    @State private var lastNowPlaying: CFTimeInterval = 0
    @State private var lastArtwork: CFTimeInterval = 0
''', "player state")

# ---------- settings: subtitle position ----------
s = once(s, 'Section("Субтитры") {', '''Section("Субтитры") {
                              Picker("Положение субтитров", selection: $subsTop) {
                                  Text("Внизу").tag(false)
                                  Text("Вверху").tag(true)
                              }''', "position picker")

# ---------- subtitle layer: top or bottom ----------
a = s.index("    private func subtitleLayer(_ rect: CGRect, portrait: Bool) -> some View {")
b = s.index("    private var controlsLayer: some View {", a)
s = s[:a] + '''    private func subtitleLayer(_ rect: CGRect, portrait: Bool) -> some View {
        Group {
            if portrait && !subsTop {
                // portrait, bottom: the lines go under the picture, across the width of the video
                VStack(spacing: 6) {
                    if !line.isEmpty {
                        SubtitleLookupBar(line: line, onTap: { _ in openLookup() })
                    }
                    Spacer(minLength: 0)
                }
                .frame(width: rect.width, alignment: .top)
                .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
                .padding(.leading, rect.minX)
                .padding(.top, rect.maxY + 10)
            } else if portrait {
                // portrait, top: the lines go above the picture
                VStack(spacing: 6) {
                    Spacer(minLength: 0)
                    if !line.isEmpty {
                        SubtitleLookupBar(line: line, onTap: { _ in openLookup() })
                    }
                }
                .frame(width: rect.width, height: max(0, rect.minY - 10), alignment: .bottom)
                .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
                .padding(.leading, rect.minX)
            } else if subsTop {
                VStack(spacing: 6) {
                    if !line.isEmpty {
                        SubtitleLookupBar(line: line, onTap: { _ in openLookup() })
                    }
                    Spacer()
                }
                .padding(.top, 26)
                .frame(width: rect.width, height: rect.height, alignment: .top)
                .position(x: rect.midX, y: rect.midY)
            } else {
                VStack(spacing: 6) {
                    Spacer()
                    if !line.isEmpty {
                        SubtitleLookupBar(line: line, onTap: { _ in openLookup() })
                    }
                }
                .padding(.bottom, 26)
                .frame(width: rect.width, height: rect.height, alignment: .bottom)
                .position(x: rect.midX, y: rect.midY)
            }
        }
    }

    /// Landscape (also with the rotation lock on) and back.
    private func toggleLandscape() {
        guard let scene = UIApplication.shared.connectedScenes.compactMap({ $0 as? UIWindowScene }).first else { return }
        let toLandscape = !scene.interfaceOrientation.isLandscape
        forcedLandscape = toLandscape
        scene.requestGeometryUpdate(.iOS(interfaceOrientations: toLandscape ? .landscapeRight : .portrait)) { _ in }
    }

    private func restorePortrait() {
        guard let scene = UIApplication.shared.connectedScenes.compactMap({ $0 as? UIWindowScene }).first else { return }
        forcedLandscape = false
        scene.requestGeometryUpdate(.iOS(interfaceOrientations: .portrait)) { _ in }
    }

    // MARK: - watching statistics

    /// Watching time (real time while playing) and the words of every new subtitle line.
    private func recordWatching() {
        let now = CACurrentMediaTime()
        let step = lastWatchTick > 0 ? min(1.0, now - lastWatchTick) : 0
        lastWatchTick = now
        guard playing else { return }
        watchPending += step
        if !line.isEmpty, line != lastCountedLine {
            lastCountedLine = line
            watchWords += NativeLookup.tokenize(line, charAt: 0).tokens.filter { token in
                token.text.unicodeScalars.contains { CharacterSet.letters.contains($0) } && !token.pos.contains("記号")
            }.count
        }
        if watchPending >= 10 {
            flushWatching()
        }
    }

    private func flushWatching() {
        let seconds = Int(watchPending.rounded())
        guard seconds > 0 || watchWords > 0 else { return }
        WatchStats.add(seconds: seconds, words: watchWords)
        watchPending = 0
        watchWords = 0
    }

    // MARK: - lock screen and Control Center

    /// Title, progress, a frame of the video (about every 10 s) and the playback buttons.
    private func updateNowPlaying() {
        let now = CACurrentMediaTime()
        guard now - lastNowPlaying >= 1, let layer = coordinator.playerLayer, duration > 0 else { return }
        lastNowPlaying = now
        if !nowPlayingReady {
            nowPlayingReady = true
            setUpRemoteCommands()
        }
        let center = MPNowPlayingInfoCenter.default()
        var info = center.nowPlayingInfo ?? [:]
        let name = url.lastPathComponent
        let title = JimakuName.parse(name).title ?? url.deletingPathExtension().lastPathComponent
        info[MPMediaItemPropertyTitle] = [title, JimakuName.episodeTag(name)].compactMap { $0 }.joined(separator: " · ")
        info[MPMediaItemPropertyPlaybackDuration] = duration
        info[MPNowPlayingInfoPropertyElapsedPlaybackTime] = position
        info[MPNowPlayingInfoPropertyPlaybackRate] = playing ? 1.0 : 0.0
        info[MPNowPlayingInfoPropertyMediaType] = MPNowPlayingInfoMediaType.video.rawValue
        center.nowPlayingInfo = info
        guard now - lastArtwork >= 10 else { return }
        lastArtwork = now
        let player = layer.player
        Task { @MainActor in
            guard let frame = await player.thumbnailImageAtCurrentTime() else { return }
            let full = UIImage(cgImage: frame)
            let scale = min(1, 600 / max(full.size.width, 1))
            let size = CGSize(width: full.size.width * scale, height: full.size.height * scale)
            let image = UIGraphicsImageRenderer(size: size).image { _ in full.draw(in: CGRect(origin: .zero, size: size)) }
            var current = MPNowPlayingInfoCenter.default().nowPlayingInfo ?? [:]
            current[MPMediaItemPropertyArtwork] = MPMediaItemArtwork(boundsSize: size) { _ in image }
            MPNowPlayingInfoCenter.default().nowPlayingInfo = current
        }
    }

    private func setUpRemoteCommands() {
        let commands = MPRemoteCommandCenter.shared()
        removeRemoteCommands()
        let layer = coordinator.playerLayer
        commands.playCommand.addTarget { _ in
            layer?.play()
            return .success
        }
        commands.pauseCommand.addTarget { _ in
            layer?.pause()
            return .success
        }
        commands.togglePlayPauseCommand.addTarget { _ in
            if layer?.player.isPlaying == true {
                layer?.pause()
            } else {
                layer?.play()
            }
            return .success
        }
        commands.skipForwardCommand.preferredIntervals = [15]
        commands.skipForwardCommand.addTarget { _ in
            guard let layer else { return .commandFailed }
            layer.seek(time: layer.player.currentPlaybackTime + 15, autoPlay: layer.player.isPlaying) { _ in }
            return .success
        }
        commands.skipBackwardCommand.preferredIntervals = [15]
        commands.skipBackwardCommand.addTarget { _ in
            guard let layer else { return .commandFailed }
            layer.seek(time: max(0, layer.player.currentPlaybackTime - 15), autoPlay: layer.player.isPlaying) { _ in }
            return .success
        }
        commands.changePlaybackPositionCommand.addTarget { event in
            guard let layer, let event = event as? MPChangePlaybackPositionCommandEvent else { return .commandFailed }
            layer.seek(time: event.positionTime, autoPlay: layer.player.isPlaying) { _ in }
            return .success
        }
    }

    private func removeRemoteCommands() {
        let commands = MPRemoteCommandCenter.shared()
        commands.playCommand.removeTarget(nil)
        commands.pauseCommand.removeTarget(nil)
        commands.togglePlayPauseCommand.removeTarget(nil)
        commands.skipForwardCommand.removeTarget(nil)
        commands.skipBackwardCommand.removeTarget(nil)
        commands.changePlaybackPositionCommand.removeTarget(nil)
    }

    private func endNowPlaying() {
        removeRemoteCommands()
        MPNowPlayingInfoCenter.default().nowPlayingInfo = nil
        nowPlayingReady = false
    }

''' + s[b:]

# ---------- rotate button next to the title ----------
s = once(s, '''                    .shadow(color: .black.opacity(0.6), radius: 2)
            }
            .padding(.horizontal, 16)
            .padding(.top, 10)
''', '''                    .shadow(color: .black.opacity(0.6), radius: 2)
                circleButton("rotate.right") { toggleLandscape() }
            }
            .padding(.horizontal, 16)
            .padding(.top, 10)
''', "rotate button")

# ---------- every tick: statistics and the lock screen player ----------
s = once(s, "        updateLine()\n    }\n\n    private func updateLine() {",
         "        updateLine()\n        recordWatching()\n        updateNowPlaying()\n    }\n\n    private func updateLine() {", "tick hooks")
s = once(s, "        .onDisappear {\n            if resumeHandled {",
         "        .onDisappear {\n            flushWatching()\n            endNowPlaying()\n            if forcedLandscape {\n                restorePortrait()\n            }\n            if resumeHandled {",
         "disappear")

# ---------- coverage badge in the video list ----------
s = once(s, "    @Published var pendingChoice: URL? = nil\n", '''    @Published var pendingChoice: URL? = nil
    /// % of the words in the Jimaku subtitles of a video that are known (added, imported from Anki, or N5)
    @Published var coverage: [String: Int] = [:]

    nonisolated static func coverage(of file: URL, known: Set<String>) -> Int? {
        var total = 0
        var familiar = 0
        for cue in EmbeddedSubtitles.cues(fromFile: file) {
            for token in NativeLookup.tokenize(cue.text, charAt: 0).tokens {
                guard token.text.unicodeScalars.contains(where: { CharacterSet.letters.contains($0) }) else { continue }
                // particles, auxiliaries and symbols do not count
                if token.pos.hasPrefix("助詞") || token.pos.hasPrefix("助動詞") || token.pos.contains("記号") { continue }
                total += 1
                let base = token.base.isEmpty ? token.text : token.base
                if known.contains(base) || known.contains(token.text)
                    || HighlightData.jlptLevel(base: base, reading: HighlightData.hiragana(token.reading)) == 5 {
                    familiar += 1
                }
            }
        }
        return total > 0 ? Int((Double(familiar) * 100 / Double(total)).rounded()) : nil
    }

    /// Coverage of every video with Jimaku subtitles; kept until the known words or the file change.
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
        var pending: [(String, URL, String)] = []
        for (name, file) in candidates {
            let size = ((try? FileManager.default.attributesOfItem(atPath: file.path)[.size]) as? Int) ?? 0
            let stamp = String(known.count) + "|" + String(size)
            if let saved = UserDefaults.standard.string(forKey: "coverage." + name), saved.hasPrefix(stamp + "|"),
               let value = Int(saved.dropFirst(stamp.count + 1)) {
                coverage[name] = value
            } else {
                pending.append((name, file, stamp))
            }
        }
        guard !pending.isEmpty else { return }
        Task { @MainActor in
            for (name, file, stamp) in pending {
                let value = await Task.detached(priority: .utility) {
                    VideoLibraryStore.coverage(of: file, known: known)
                }.value
                if let value {
                    coverage[name] = value
                    UserDefaults.standard.set(stamp + "|" + String(value), forKey: "coverage." + name)
                }
            }
        }
    }
''', "coverage store")
s = once(s, "    func reload() {\n        let urls = (try? FileManager.default.contentsOfDirectory(",
         "    func reload() {\n        defer { updateCoverage() }\n        let urls = (try? FileManager.default.contentsOfDirectory(", "coverage on reload")
s = once(s, '''                    if !item.isFolder, VideoLibraryStore.isVideo(name), let tag = JimakuName.episodeTag(name) {
                        Text(tag)
                            .font(.caption2.bold())
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(Color.secondary.opacity(0.2))
                            .cornerRadius(4)
                    }
''', '''                    if !item.isFolder, VideoLibraryStore.isVideo(name), let tag = JimakuName.episodeTag(name) {
                        Text(tag)
                            .font(.caption2.bold())
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(Color.secondary.opacity(0.2))
                            .cornerRadius(4)
                    }
                    if !item.isFolder, let value = library.coverage[name] {
                        Text(String(value) + "%")
                            .font(.caption2.bold())
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(Color.green.opacity(value >= 90 ? 0.35 : 0.15))
                            .cornerRadius(4)
                    }
''', "coverage badge")

p.write_text(s, encoding="utf-8")
print("v1.46 player patch applied")
