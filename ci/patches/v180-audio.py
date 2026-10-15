# v1.80: the sound of the subtitle line in the note. When the dictionary opens in the player, the line on screen is cut
# out of the video (FFmpeg, mono AAC) and goes into the first empty field named like "sentence audio"
# (SentenceAudio, SectenceAudio, Аудио предложения …) as an inline <audio> player: AnkiMobile takes text only.
# The mining queue keeps the sound in a file of its own, like the frame. The code is v180-audio.swift.
import pathlib


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


def between(text, start, end, new, label):
    assert text.count(start) == 1, "start not found exactly once: " + label
    a = text.index(start)
    b = text.index(end, a)
    return text[:a] + new + text[b:]


here = pathlib.Path(__file__).resolve().parent
hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")

# ---------- the note: the frame and the sound ----------
s = once(s, '''enum MiningFrame {
    static var jpegBase64: String?
''', '''enum MiningFrame {
    static var jpegBase64: String? {
        // every new note starts without the sound of an earlier line
        didSet {
            if jpegBase64 == nil {
                audioBase64 = nil
            }
        }
    }
    /// the sound of the line (m4a), for the sentence audio field
    static var audioBase64: String?
    static let audioPrefix = "<audio controls src=\\"data:audio/mp4;base64,"
''', "audio state")
s = between(s, "    /// The note with the frame in its first empty picture field (an inline image: AnkiMobile takes text only).\n",
            "    /// AnkiMobile comes back to the queue after the note.", '''    /// A field for the sound of the sentence: SentenceAudio, Sentence audio, Аудио предложения …
    private static func isSentenceAudio(_ field: String) -> Bool {
        ["audio", "sound", "аудио", "звук"].contains { field.contains($0) }
            && ["sent", "sect", "предлож"].contains { field.contains($0) }
    }

    /// The note with the frame in its first empty picture field and the sound of the line in its first empty sentence
    /// audio field (inline: AnkiMobile takes text only).
    static func attach(to url: URL) -> URL {
        guard isAddNote(url), var parts = URLComponents(url: url, resolvingAgainstBaseURL: false),
              var items = parts.percentEncodedQueryItems else { return url }
        func emptyField(_ matches: (String) -> Bool) -> Int? {
            items.firstIndex { item in
                guard item.name.hasPrefix("fld"), (item.value ?? "").isEmpty else { return false }
                return matches(item.name.dropFirst(3).lowercased())
            }
        }
        if let frame = jpegBase64, let index = emptyField({ field in pictureNames.contains { field.contains($0) } }) {
            let html = "<img src=\\"data:image/jpeg;base64," + frame + "\\">"
            items[index].value = html.addingPercentEncoding(withAllowedCharacters: ankiQueryAllowed)
        }
        if let sound = audioBase64, let index = emptyField(isSentenceAudio) {
            let html = audioPrefix + sound + "\\"></audio>"
            items[index].value = html.addingPercentEncoding(withAllowedCharacters: ankiQueryAllowed)
        }
        parts.percentEncodedQueryItems = items
        return parts.url ?? url
    }

''', "attach")

# ---------- the queue keeps the sound in a file ----------
s = once(s, '''        /// the frame of the note in Library/mining-frames (its field holds frameMarker)
        var frame: String? = nil
    }
''', '''        /// the frame of the note in Library/mining-frames (its field holds frameMarker)
        var frame: String? = nil
        /// the sound of the line, next to the frame (its field holds audioMarker)
        var audio: String? = nil
    }
''', "entry audio")
s = between(s, "    /// The base64 picture of a note goes to its own file: the saved queue grew by ~80 KB with every note.\n",
            "    @Published private(set) var entries: [Entry] = []", '''    private static let audioMarker = "yk-audio"

    /// The base64 picture and sound of a note go to files of their own: the saved queue grew by ~80 KB with every note.
    static func detachFrame(_ entry: inout Entry) {
        guard var parts = URLComponents(string: entry.url), var items = parts.percentEncodedQueryItems else { return }
        var frame: String? = nil
        var audio: String? = nil
        for index in items.indices {
            guard let value = items[index].value?.removingPercentEncoding else { continue }
            let isFrame = entry.frame == nil && frame == nil && value.hasPrefix(framePrefix)
            let isAudio = entry.audio == nil && audio == nil && value.hasPrefix(MiningFrame.audioPrefix)
            guard isFrame || isAudio else { continue }
            let body = value.dropFirst(isFrame ? framePrefix.count : MiningFrame.audioPrefix.count)
            guard let end = body.firstIndex(of: "\\""), let data = Data(base64Encoded: String(body[..<end])) else { continue }
            let name = entry.id.uuidString + (isFrame ? ".jpg" : ".m4a")
            guard (try? data.write(to: frameFolder.appendingPathComponent(name))) != nil else { continue }
            items[index].value = isFrame ? frameMarker : audioMarker
            if isFrame {
                frame = name
            } else {
                audio = name
            }
        }
        guard frame != nil || audio != nil else { return }
        parts.percentEncodedQueryItems = items
        guard let short = parts.url?.absoluteString else { return }
        entry.url = short
        entry.frame = frame ?? entry.frame
        entry.audio = audio ?? entry.audio
    }

    /// The note as AnkiMobile gets it: the frame and the sound back in their fields.
    static func fullURL(_ entry: Entry) -> URL? {
        guard entry.frame != nil || entry.audio != nil, var parts = URLComponents(string: entry.url),
              var items = parts.percentEncodedQueryItems else { return URL(string: entry.url) }
        let frame = entry.frame.flatMap { try? Data(contentsOf: frameFolder.appendingPathComponent($0)) }
        let audio = entry.audio.flatMap { try? Data(contentsOf: frameFolder.appendingPathComponent($0)) }
        for index in items.indices {
            var html: String? = nil
            if items[index].value == frameMarker {
                html = frame.map { framePrefix + $0.base64EncodedString() + "\\">" } ?? ""
            } else if items[index].value == audioMarker {
                html = audio.map { MiningFrame.audioPrefix + $0.base64EncodedString() + "\\"></audio>" } ?? ""
            }
            if let html {
                items[index].value = html.addingPercentEncoding(withAllowedCharacters: ankiQueryAllowed)
            }
        }
        parts.percentEncodedQueryItems = items
        return parts.url
    }

    private static func deleteFrame(_ entry: Entry) {
        for name in [entry.frame, entry.audio].compactMap({ $0 }) {
            try? FileManager.default.removeItem(at: frameFolder.appendingPathComponent(name))
        }
    }

''', "queue files")

# ---------- the player cuts the line out ----------
s = once(s, '''        guard let player = coordinator.playerLayer?.player else { return }
        Task { @MainActor in
            if let frame = await player.thumbnailImageAtCurrentTime() {
                MiningFrame.capture(frame)
            }
        }
    }
}
''', '''        // the sound of the lines on screen (in the time of the video), a little room on both sides
        MiningFrame.audioBase64 = nil
        let t = position - subDelay
        let shown = (usingExternal ? externalCues : embeddedCues).filter { $0.start <= t && t < $0.end }
        if let first = shown.map({ $0.start }).min(), let last = shown.map({ $0.end }).max() {
            let from = max(0, first + subDelay - 0.2)
            let to = min(last + subDelay + 0.3, from + 20)
            let file = url
            Task.detached(priority: .userInitiated) {
                let sound = MiningAudio.clip(url: file, from: from, to: to)?.base64EncodedString()
                await MainActor.run {
                    MiningFrame.audioBase64 = sound
                }
            }
        }
        guard let player = coordinator.playerLayer?.player else { return }
        Task { @MainActor in
            if let frame = await player.thumbnailImageAtCurrentTime() {
                MiningFrame.capture(frame)
            }
        }
    }
}
''', "player audio")
s = s.rstrip("\n") + "\n" + (here / "v180-audio.swift").read_text(encoding="utf-8")
hv.write_text(s, encoding="utf-8")
print("v1.80 audio applied")
