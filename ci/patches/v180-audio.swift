
// MARK: - Mining v1.80: the sound of the line in the note

/// The sound of a subtitle line for the note: decoded with FFmpeg (any video the player opens), mixed to mono, saved
/// as AAC in an .m4a. AnkiMobile takes text only, so the sound goes into the field as an inline <audio> player.
enum MiningAudio {
    /// Seconds `from` … `to` of the main audio track; nil when it cannot be read.
    static func clip(url: URL, from: Double, to: Double) -> Data? {
        var opened: UnsafeMutablePointer<AVFormatContext>? = nil
        guard avformat_open_input(&opened, url.path, nil, nil) == 0, let fmt = opened else { return nil }
        defer {
            var closing: UnsafeMutablePointer<AVFormatContext>? = fmt
            avformat_close_input(&closing)
        }
        guard avformat_find_stream_info(fmt, nil) >= 0, let streams = fmt.pointee.streams else { return nil }
        let index = av_find_best_stream(fmt, AVMEDIA_TYPE_AUDIO, -1, -1, nil, 0)
        guard index >= 0, let stream = streams[Int(index)], let par = stream.pointee.codecpar,
              let decoder = avcodec_find_decoder(par.pointee.codec_id),
              let context = avcodec_alloc_context3(decoder) else { return nil }
        var codec: UnsafeMutablePointer<AVCodecContext>? = context
        defer {
            avcodec_free_context(&codec)
        }
        guard avcodec_parameters_to_context(context, par) >= 0, avcodec_open2(context, decoder, nil) >= 0 else { return nil }
        for i in 0 ..< Int(fmt.pointee.nb_streams) where i != Int(index) {
            streams[i]?.pointee.discard = AVDISCARD_ALL
        }
        let timeBase = av_q2d(stream.pointee.time_base)
        guard timeBase > 0 else { return nil }
        // a second before the line: the decoder settles on the frames before it
        av_seek_frame(fmt, index, Int64(max(0, from - 1) / timeBase), AVSEEK_FLAG_BACKWARD)
        guard let packet = av_packet_alloc(), let frame = av_frame_alloc() else { return nil }
        defer {
            var freedPacket: UnsafeMutablePointer<AVPacket>? = packet
            av_packet_free(&freedPacket)
            var freedFrame: UnsafeMutablePointer<AVFrame>? = frame
            av_frame_free(&freedFrame)
        }
        var samples: [Float] = []
        var rate = 0
        reading: while av_read_frame(fmt, packet) >= 0 {
            defer { av_packet_unref(packet) }
            guard packet.pointee.stream_index == index, avcodec_send_packet(context, packet) >= 0 else { continue }
            while avcodec_receive_frame(context, frame) >= 0 {
                defer { av_frame_unref(frame) }
                var stamp = frame.pointee.best_effort_timestamp
                if stamp == Int64.min {
                    stamp = frame.pointee.pts
                }
                guard stamp != Int64.min else { continue }
                let start = Double(stamp) * timeBase
                if start >= to {
                    break reading
                }
                rate = Int(frame.pointee.sample_rate)
                let count = Int(frame.pointee.nb_samples)
                guard rate > 0, count > 0 else { continue }
                let first = max(0, Int(((from - start) * Double(rate)).rounded()))
                let last = min(count, Int(((to - start) * Double(rate)).rounded()))
                if first < last {
                    samples += mono(frame, first, last)
                }
            }
        }
        guard rate > 0, samples.count > rate / 5 else { return nil }
        return encode(samples, rate: rate)
    }

    /// Samples `first` ..< `last` of a frame, its channels mixed into one.
    private static func mono(_ frame: UnsafeMutablePointer<AVFrame>, _ first: Int, _ last: Int) -> [Float] {
        let channels = max(1, Int(frame.pointee.ch_layout.nb_channels))
        let format = AVSampleFormat(rawValue: frame.pointee.format)
        let planar = av_sample_fmt_is_planar(format) != 0
        guard let planes = frame.pointee.extended_data else { return [] }
        var out = [Float](repeating: 0, count: last - first)
        for channel in 0 ..< channels {
            guard let base = planes[planar ? channel : 0] else { continue }
            for i in first ..< last {
                let at = planar ? i : i * channels + channel
                var value: Float = 0
                switch format {
                case AV_SAMPLE_FMT_FLT, AV_SAMPLE_FMT_FLTP:
                    value = base.withMemoryRebound(to: Float.self, capacity: at + 1) { $0[at] }
                case AV_SAMPLE_FMT_S16, AV_SAMPLE_FMT_S16P:
                    value = Float(base.withMemoryRebound(to: Int16.self, capacity: at + 1) { $0[at] }) / 32768
                case AV_SAMPLE_FMT_S32, AV_SAMPLE_FMT_S32P:
                    value = Float(base.withMemoryRebound(to: Int32.self, capacity: at + 1) { $0[at] }) / 2_147_483_648
                case AV_SAMPLE_FMT_DBL, AV_SAMPLE_FMT_DBLP:
                    value = Float(base.withMemoryRebound(to: Double.self, capacity: at + 1) { $0[at] })
                case AV_SAMPLE_FMT_U8, AV_SAMPLE_FMT_U8P:
                    value = (Float(base[at]) - 128) / 128
                default:
                    value = 0
                }
                out[i - first] += value / Float(channels)
            }
        }
        return out
    }

    /// Mono AAC at 64 kbit/s in an .m4a.
    private static func encode(_ samples: [Float], rate: Int) -> Data? {
        let file = FileManager.default.temporaryDirectory.appendingPathComponent("line-" + UUID().uuidString + ".m4a")
        defer { try? FileManager.default.removeItem(at: file) }
        guard write(samples, rate: rate, to: file) else { return nil }
        return try? Data(contentsOf: file)
    }

    /// The file is complete when its writer is gone, at the end of this function.
    private static func write(_ samples: [Float], rate: Int, to file: URL) -> Bool {
        guard let format = AVAudioFormat(standardFormatWithSampleRate: Double(rate), channels: 1),
              let buffer = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: AVAudioFrameCount(samples.count)),
              let channel = buffer.floatChannelData?[0] else { return false }
        buffer.frameLength = AVAudioFrameCount(samples.count)
        for (i, sample) in samples.enumerated() {
            channel[i] = sample
        }
        let settings: [String: Any] = [AVFormatIDKey: kAudioFormatMPEG4AAC, AVSampleRateKey: rate,
                                       AVNumberOfChannelsKey: 1, AVEncoderBitRateKey: 64000]
        guard let output = try? AVAudioFile(forWriting: file, settings: settings, commonFormat: .pcmFormatFloat32,
                                             interleaved: false) else { return false }
        return (try? output.write(from: buffer)) != nil
    }
}
