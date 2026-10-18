
// MARK: - Satori v2.14: subtitles from the sound (iOS 26)

/// The sound of a video turned into Japanese subtitles by the speech recognition of iOS 26 (SpeechTranscriber, on
/// the device), in pieces of 90 s: from the place of the playback to the end first, so the lines are ready before
/// they are spoken, then the beginning. Every piece adds its lines at once; the whole file is kept as <name>.ja.srt.
@available(iOS 26.0, *)
enum SpeechSubtitles {
    static let piece: Double = 90

    @MainActor
    static func run(video: URL, from start: Double, duration: Double, report: @escaping (String) -> Void,
                    update: @escaping ([EmbeddedSubtitles.Cue]) -> Void) async {
        guard SpeechTranscriber.isAvailable,
              let locale = await SpeechTranscriber.supportedLocale(equivalentTo: Locale(identifier: "ja-JP")) else {
            report("Субтитры из звука: распознавание японского недоступно на этом устройстве")
            return
        }
        if SFSpeechRecognizer.authorizationStatus() == .notDetermined {
            _ = await withCheckedContinuation { (done: CheckedContinuation<SFSpeechRecognizerAuthorizationStatus, Never>) in
                SFSpeechRecognizer.requestAuthorization { status in
                    done.resume(returning: status)
                }
            }
        }
        do {
            let probe = SpeechTranscriber(locale: locale, preset: .transcription)
            if let request = try await AssetInventory.assetInstallationRequest(supporting: [probe]) {
                report("Субтитры из звука: скачиваю модель японского…")
                try await request.downloadAndInstall()
            }
        } catch {
            report("Субтитры из звука: модель не скачалась (" + error.localizedDescription + ")")
            return
        }
        guard duration > 1 else { return }
        var ranges: [(from: Double, to: Double)] = []
        var at: Double = max(0, min(start, duration - 1))
        let first = at
        while at < duration {
            ranges.append((from: at, to: min(at + piece, duration)))
            at += piece
        }
        at = 0
        while at < first {
            ranges.append((from: at, to: min(at + piece, first)))
            at += piece
        }
        var cues: [EmbeddedSubtitles.Cue] = []
        for (index, range) in ranges.enumerated() {
            if Task.isCancelled {
                return
            }
            let step: String = String(index + 1)
            let all: String = String(ranges.count)
            report("Субтитры из звука: часть " + step + " из " + all + "…")
            let found = await Task.detached(priority: .userInitiated) {
                await transcribe(video: video, from: range.from, to: range.to, locale: locale)
            }.value
            cues = (cues + found).sorted { $0.start < $1.start }
            update(cues)
        }
        guard !cues.isEmpty else {
            report("Субтитры из звука: речь не найдена")
            return
        }
        let count: String = String(cues.count)
        report("Субтитры из звука: " + count + " реплик")
        let out = video.deletingPathExtension().appendingPathExtension("ja.srt")
        try? EmbeddedSubtitles.srtText(cues).write(to: out, atomically: true, encoding: .utf8)
    }

    /// One piece of the sound: its phrases as lines, in the time of the video.
    static func transcribe(video: URL, from: Double, to: Double, locale: Locale) async -> [EmbeddedSubtitles.Cue] {
        guard let data = MiningAudio.clip(url: video, from: from, to: to) else { return [] }
        let file = FileManager.default.temporaryDirectory.appendingPathComponent("speech-" + UUID().uuidString + ".m4a")
        defer {
            try? FileManager.default.removeItem(at: file)
        }
        guard (try? data.write(to: file)) != nil, let audio = try? AVAudioFile(forReading: file) else { return [] }
        let transcriber = SpeechTranscriber(locale: locale, preset: .transcription)
        let analyzer = SpeechAnalyzer(modules: [transcriber])
        let collect = Task { () -> [EmbeddedSubtitles.Cue] in
            var out: [EmbeddedSubtitles.Cue] = []
            do {
                for try await result in transcriber.results where result.isFinal {
                    out += lines(of: result, offset: from)
                }
            } catch {}
            return out
        }
        do {
            if let last = try await analyzer.analyzeSequence(from: audio) {
                try await analyzer.finalizeAndFinish(through: last)
            } else {
                await analyzer.cancelAndFinishNow()
            }
        } catch {
            await analyzer.cancelAndFinishNow()
        }
        return await collect.value
    }

    /// A phrase as lines of a readable length (at 。？！, at 、 after 14 letters, at 28), the time of the phrase shared
    /// by their letters.
    static func lines(of result: SpeechTranscriber.Result, offset: Double) -> [EmbeddedSubtitles.Cue] {
        let text = String(result.text.characters).trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return [] }
        let start: Double = offset + result.range.start.seconds
        let length: Double = max(0.5, result.range.duration.seconds)
        var parts: [String] = []
        var current = ""
        for character in text {
            current.append(character)
            let stop: Bool = "。？！?!".contains(character)
            let comma: Bool = character == "、" && current.count >= 14
            if stop || comma || current.count >= 28 {
                parts.append(current)
                current = ""
            }
        }
        if !current.trimmingCharacters(in: .whitespaces).isEmpty {
            parts.append(current)
        }
        let total = Double(max(1, text.count))
        var at: Double = start
        var out: [EmbeddedSubtitles.Cue] = []
        for part in parts {
            let span: Double = length * Double(part.count) / total
            let line = part.trimmingCharacters(in: .whitespaces)
            if !line.isEmpty {
                out.append(EmbeddedSubtitles.Cue(start: at, end: at + max(span, 0.8), text: line))
            }
            at += span
        }
        return out
    }
}
