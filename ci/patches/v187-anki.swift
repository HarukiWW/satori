
// MARK: - Satori v1.87: known words from the backups of AnkiMobile, full notes from the list of unknown words

/// AnkiMobile's own backups (На iPhone → Anki → Backups): when Satori opens and a backup is newer than the last one
/// read, its mature cards replace the mature list, so the coverage, the difficulty and the furigana follow the cards
/// without an export. The backup is read by the import page (the same reader as for a shared deck), hidden.
@MainActor
final class AnkiBackupSync: ObservableObject {
    static let shared = AnkiBackupSync()
    private let bookmarkKey = "ykAnkiBackupsBookmark"
    private let doneKey = "ykAnkiBackupRead"
    /// the hidden import page is on screen
    @Published private(set) var importing = false
    @Published private(set) var status = ""
    private var pendingDate: Date? = nil

    var connected: Bool {
        UserDefaults.standard.data(forKey: bookmarkKey) != nil
    }

    var lastRead: Date? {
        let value = UserDefaults.standard.double(forKey: doneKey)
        return value > 0 ? Date(timeIntervalSince1970: value) : nil
    }

    /// The folder chosen in Settings; it stays reachable between launches through its bookmark.
    func choose(_ folder: URL) {
        let access = folder.startAccessingSecurityScopedResource()
        defer {
            if access {
                folder.stopAccessingSecurityScopedResource()
            }
        }
        guard let data = try? folder.bookmarkData() else {
            status = "Папку не удалось запомнить"
            return
        }
        UserDefaults.standard.set(data, forKey: bookmarkKey)
        UserDefaults.standard.removeObject(forKey: doneKey)
        objectWillChange.send()
        check()
    }

    func disconnect() {
        UserDefaults.standard.removeObject(forKey: bookmarkKey)
        UserDefaults.standard.removeObject(forKey: doneKey)
        status = ""
        objectWillChange.send()
    }

    private func folder() -> URL? {
        guard let data = UserDefaults.standard.data(forKey: bookmarkKey) else { return nil }
        var stale = false
        guard let url = try? URL(resolvingBookmarkData: data, bookmarkDataIsStale: &stale) else { return nil }
        if stale, url.startAccessingSecurityScopedResource() {
            if let fresh = try? url.bookmarkData() {
                UserDefaults.standard.set(fresh, forKey: bookmarkKey)
            }
            url.stopAccessingSecurityScopedResource()
        }
        return url
    }

    /// The newest backup goes to the import page when it is newer than the one read last (or always: `force`).
    func check(force: Bool = false) {
        guard !importing, let folder = folder() else { return }
        let access = folder.startAccessingSecurityScopedResource()
        defer {
            if access {
                folder.stopAccessingSecurityScopedResource()
            }
        }
        let keys: [URLResourceKey] = [.contentModificationDateKey]
        let files = (try? FileManager.default.contentsOfDirectory(at: folder, includingPropertiesForKeys: keys)) ?? []
        func date(_ file: URL) -> Date {
            (try? file.resourceValues(forKeys: [.contentModificationDateKey]))?.contentModificationDate ?? .distantPast
        }
        guard let newest = files.filter({ $0.pathExtension.lowercased() == "colpkg" }).max(by: { date($0) < date($1) }) else {
            status = access ? "В папке нет бэкапов (.colpkg)" : "Нет доступа к папке: выберите её снова"
            return
        }
        let made = date(newest)
        if !force, let lastRead, made <= lastRead.addingTimeInterval(1) {
            return
        }
        guard DeckInbox.receive(newest) else {
            status = "Не удалось скопировать бэкап"
            return
        }
        DeckInbox.fromBackup = true
        pendingDate = made
        importing = true
        status = "Обновляю знакомые слова из бэкапа…"
        // a page that never answers must not block the next backups
        Task { @MainActor in
            try? await Task.sleep(nanoseconds: 300_000_000_000)
            if self.importing, self.pendingDate == made {
                self.finished(ok: false, message: "Бэкап не прочитан: импорт не ответил")
            }
        }
    }

    /// The import page is done with the backup.
    func finished(ok: Bool, message: String) {
        importing = false
        DeckInbox.fromBackup = false
        if ok, let pendingDate {
            UserDefaults.standard.set(pendingDate.timeIntervalSince1970, forKey: doneKey)
        }
        pendingDate = nil
        status = message
    }
}

/// Настройки → Anki: the folder of the backups of AnkiMobile.
struct AnkiBackupRow: View {
    @ObservedObject private var sync = AnkiBackupSync.shared
    @State private var picking = false

    private var footer: String {
        var text = "Выберите «На iPhone → Anki → Backups». Когда AnkiMobile сделает новый бэкап (при синхронизации), "
            + "зрелые карточки обновятся сами при открытии Satori."
        if let date = sync.lastRead {
            text += " Последний прочитанный бэкап: " + date.formatted(date: .abbreviated, time: .shortened) + "."
        }
        return text
    }

    var body: some View {
        Group {
            Button(sync.connected ? "Папка бэкапов AnkiMobile: выбрана" : "Папка бэкапов AnkiMobile…") {
                picking = true
            }
            .fileImporter(isPresented: $picking, allowedContentTypes: [.folder]) { result in
                if case .success(let url) = result {
                    sync.choose(url)
                }
            }
            if sync.connected {
                Button(sync.importing ? "Читаю бэкап…" : "Прочитать последний бэкап сейчас") {
                    sync.check(force: true)
                }
                .disabled(sync.importing)
                Button("Не следить за бэкапами", role: .destructive) {
                    sync.disconnect()
                }
            }
            if !sync.status.isEmpty {
                Text(sync.status)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            Text(footer)
                .font(.caption)
                .foregroundColor(.secondary)
        }
    }
}

/// One frame of a video file (FFmpeg), without the player: for the notes made from a list of unknown words.
enum VideoFrameGrab {
    static func image(url: URL, at time: Double, width maxWidth: Int32 = 640) -> CGImage? {
        var opened: UnsafeMutablePointer<AVFormatContext>? = nil
        guard avformat_open_input(&opened, url.path, nil, nil) == 0, let fmt = opened else { return nil }
        defer {
            var closing: UnsafeMutablePointer<AVFormatContext>? = fmt
            avformat_close_input(&closing)
        }
        guard avformat_find_stream_info(fmt, nil) >= 0, let streams = fmt.pointee.streams else { return nil }
        let index = av_find_best_stream(fmt, AVMEDIA_TYPE_VIDEO, -1, -1, nil, 0)
        guard index >= 0, let stream = streams[Int(index)], let par = stream.pointee.codecpar,
              let decoder = avcodec_find_decoder(par.pointee.codec_id),
              let context = avcodec_alloc_context3(decoder) else { return nil }
        var codec: UnsafeMutablePointer<AVCodecContext>? = context
        defer {
            avcodec_free_context(&codec)
        }
        guard avcodec_parameters_to_context(context, par) >= 0 else { return nil }
        context.pointee.thread_count = 0
        guard avcodec_open2(context, decoder, nil) >= 0 else { return nil }
        for i in 0 ..< Int(fmt.pointee.nb_streams) where i != Int(index) {
            streams[i]?.pointee.discard = AVDISCARD_ALL
        }
        let timeBase = av_q2d(stream.pointee.time_base)
        guard timeBase > 0 else { return nil }
        av_seek_frame(fmt, index, Int64(max(0, time) / timeBase), AVSEEK_FLAG_BACKWARD)
        guard let packet = av_packet_alloc(), let frame = av_frame_alloc() else { return nil }
        defer {
            var freedPacket: UnsafeMutablePointer<AVPacket>? = packet
            av_packet_free(&freedPacket)
            var freedFrame: UnsafeMutablePointer<AVFrame>? = frame
            av_frame_free(&freedFrame)
        }
        var packets = 0
        while av_read_frame(fmt, packet) >= 0 {
            defer { av_packet_unref(packet) }
            guard packet.pointee.stream_index == index else { continue }
            // a very long group of pictures: no frame rather than a long wait
            packets += 1
            if packets > 600 {
                break
            }
            guard avcodec_send_packet(context, packet) >= 0 else { continue }
            while avcodec_receive_frame(context, frame) >= 0 {
                var stamp = frame.pointee.best_effort_timestamp
                if stamp == Int64.min {
                    stamp = frame.pointee.pts
                }
                if stamp != Int64.min, Double(stamp) * timeBase + 0.05 < time {
                    av_frame_unref(frame)
                    continue
                }
                let image = rgb(frame, maxWidth: maxWidth)
                av_frame_unref(frame)
                return image
            }
        }
        return nil
    }

    /// The decoded picture as RGB, at most `maxWidth` wide, in the shape it is shown (DVD pictures are stored narrower
    /// or wider than that).
    private static func rgb(_ frame: UnsafeMutablePointer<AVFrame>, maxWidth: Int32) -> CGImage? {
        let width = frame.pointee.width
        let height = frame.pointee.height
        guard width > 0, height > 0 else { return nil }
        let sar = frame.pointee.sample_aspect_ratio
        let shown = sar.num > 0 && sar.den > 0 ? Double(width) * Double(sar.num) / Double(sar.den) : Double(width)
        let outWidth = max(2, min(maxWidth, Int32(shown.rounded())) & ~1)
        let outHeight = max(2, Int32((Double(outWidth) * Double(height) / shown).rounded()) & ~1)
        guard let scaler = sws_getContext(width, height, AVPixelFormat(rawValue: frame.pointee.format), outWidth, outHeight,
                                          AV_PIX_FMT_RGBA, SWS_BILINEAR, nil, nil, nil) else { return nil }
        defer {
            sws_freeContext(scaler)
        }
        guard let out = av_frame_alloc() else { return nil }
        defer {
            var freed: UnsafeMutablePointer<AVFrame>? = out
            av_frame_free(&freed)
        }
        out.pointee.format = AV_PIX_FMT_RGBA.rawValue
        out.pointee.width = outWidth
        out.pointee.height = outHeight
        guard av_frame_get_buffer(out, 0) >= 0, sws_scale_frame(scaler, out, frame) >= 0,
              let pixels = out.pointee.data.0 else { return nil }
        let bytesPerRow = Int(out.pointee.linesize.0)
        let data = Data(bytes: pixels, count: bytesPerRow * Int(outHeight))
        guard let provider = CGDataProvider(data: data as CFData) else { return nil }
        return CGImage(width: Int(outWidth), height: Int(outHeight), bitsPerComponent: 8, bitsPerPixel: 32,
                       bytesPerRow: bytesPerRow, space: CGColorSpaceCreateDeviceRGB(),
                       bitmapInfo: CGBitmapInfo(rawValue: CGImageAlphaInfo.noneSkipLast.rawValue),
                       provider: provider, decode: nil, shouldInterpolate: true, intent: .defaultIntent)
    }
}

/// A note from the list of unknown words of a series: the clearest line of the series with the word (the fewest
/// other unknown words, a readable length), its sound and its frame from the video.
@available(iOS 16.0, *)
enum ListMining {
    struct Line {
        let text: String
        let charAt: Int
        let start: Double
        let end: Double
    }

    static func bestLine(for word: String, file: URL, judge: WordKnowledge) -> Line? {
        guard let first = word.first else { return nil }
        var best: (score: Double, line: Line)? = nil
        for cue in EmbeddedSubtitles.cues(fromFile: file) {
            let text = SubtitleTokenCache.clean(cue.text)
            // the first letter of a word is in its line in every form (食べた, 食べる)
            guard text.contains(first) else { continue }
            let tokens = SubtitleTokenCache.shared.tokens(text)
            guard let hit = tokens.first(where: { ($0.base.isEmpty ? $0.text : $0.base) == word || $0.text == word }) else {
                continue
            }
            let others = tokens.filter { $0.id != hit.id && WordKnowledge.counted($0) && !judge.known($0) }.count
            let length = Double(text.count)
            let score = Double(others) * 10 + abs(length - 18) / 3 + (length < 6 ? 15 : 0)
            if best == nil || score < best!.score {
                best = (score, Line(text: text, charAt: hit.start, start: cue.start, end: cue.end))
            }
        }
        return best?.line
    }

    /// The frame in the middle of the line and its sound, for the next note (MiningFrame).
    @MainActor
    static func prepare(video: URL, line: Line) async {
        let delay = UserDefaults.standard.double(forKey: "subdelay." + VideoKey.of(video))
        let from = max(0, line.start + delay - 0.2)
        let to = min(line.end + delay + 0.3, from + 20)
        let middle = (line.start + line.end) / 2 + delay
        let made = await Task.detached(priority: .userInitiated) { () -> (CGImage?, String?) in
            let frame = VideoFrameGrab.image(url: video, at: middle)
            let sound = MiningAudio.clip(url: video, from: from, to: to).flatMap { ClipFiles.keep($0) }
            return (frame, sound)
        }.value
        MiningFrame.jpegBase64 = nil
        if let frame = made.0 {
            MiningFrame.capture(frame)
        }
        MiningFrame.audioFile = made.1
        if made.1 != nil {
            ClipServer.shared.start()
        }
    }
}

/// The line a dictionary sheet opens on.
struct LineLookup: Identifiable {
    let id = UUID()
    let text: String
    let charAt: Int
}
