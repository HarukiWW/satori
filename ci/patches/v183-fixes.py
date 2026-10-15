# v1.83: fixes of the mined note.
# - The sound of the line comes from the audio track that is playing (Japanese), not the file's default one
#   (often English): the player's track, else the same language, else Japanese, else the default.
# - "Макс. переводов" caps the whole list of a word in the list formats (its dots read as one list); in "one line"
#   it stays per meaning.
import pathlib


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")

# ---------- the audio track of the clip ----------
s = once(s, '''    /// Seconds `from` … `to` of the main audio track; nil when it cannot be read.
    static func clip(url: URL, from: Double, to: Double) -> Data? {
''', '''    /// The language tag of a stream ("jpn", "eng" …), lowercased.
    private static func language(of stream: UnsafeMutablePointer<AVStream>) -> String {
        guard let entry = av_dict_get(stream.pointee.metadata, "language", nil, 0),
              let value = entry.pointee.value else { return "" }
        return String(cString: value).lowercased()
    }

    /// Seconds `from` … `to` of the audio track that plays (`stream`), else of one in `language`, else a Japanese
    /// one, else the main one; nil when it cannot be read.
    static func clip(url: URL, from: Double, to: Double, stream wanted: Int32? = nil, language: String? = nil) -> Data? {
''', "clip signature")
s = once(s, '''        guard avformat_find_stream_info(fmt, nil) >= 0, let streams = fmt.pointee.streams else { return nil }
        let index = av_find_best_stream(fmt, AVMEDIA_TYPE_AUDIO, -1, -1, nil, 0)
        guard index >= 0, let stream = streams[Int(index)], let par = stream.pointee.codecpar,
''', '''        guard avformat_find_stream_info(fmt, nil) >= 0, let streams = fmt.pointee.streams else { return nil }
        let count = Int(fmt.pointee.nb_streams)
        func isAudio(_ i: Int) -> Bool {
            streams[i]?.pointee.codecpar?.pointee.codec_type == AVMEDIA_TYPE_AUDIO
        }
        var index: Int32 = -1
        if let wanted, wanted >= 0, Int(wanted) < count, isAudio(Int(wanted)) {
            index = wanted
        }
        for tag in [language?.lowercased() ?? "", "jpn", "ja", "jap"] where index < 0 && !tag.isEmpty {
            for i in 0 ..< count where isAudio(i) {
                if let candidate = streams[i], MiningAudio.language(of: candidate) == tag {
                    index = Int32(i)
                    break
                }
            }
        }
        if index < 0 {
            index = av_find_best_stream(fmt, AVMEDIA_TYPE_AUDIO, -1, -1, nil, 0)
        }
        guard index >= 0, let stream = streams[Int(index)], let par = stream.pointee.codecpar,
''', "clip track")
s = once(s, '''            let file = url
            Task.detached(priority: .userInitiated) {
                let name = MiningAudio.clip(url: file, from: from, to: to).flatMap { ClipFiles.keep($0) }
''', '''            let file = url
            // the audio track that plays (the Japanese one the player chose)
            let playing = coordinator.playerLayer?.player.tracks(mediaType: .audio).first { $0.isEnabled }
            let stream = (playing as? FFmpegAssetTrack)?.trackID
            let language = playing?.languageCode
            Task.detached(priority: .userInitiated) {
                let name = MiningAudio.clip(url: file, from: from, to: to, stream: stream, language: language)
                    .flatMap { ClipFiles.keep($0) }
''', "player track")
hv.write_text(s, encoding="utf-8")

# ---------- the cap of the glosses ----------
p = pathlib.Path("src/main/src/lib/anki/ankiBuilder.ts")
t = p.read_text(encoding="utf-8")
t = once(t, "    for (const group of data.entry.groupedSenses) {\n",
         "    // glosses shown so far: the list formats cap the whole word\n"
         "    let shown = 0;\n    for (const group of data.entry.groupedSenses) {\n", "shown counter")
t = once(t, '''      for (const sense of group.senses) {
        let items;
        if (opts.full_max_item > 0) {
          items = sense.meanings.slice(0, opts.full_max_item);
        } else {
          items = sense.meanings;
        }
''', '''      for (const sense of group.senses) {
        let items;
        if (opts.full_max_item > 0) {
          const cap =
            format === "line" || format === "yomichan"
              ? opts.full_max_item
              : Math.max(0, opts.full_max_item - shown);
          items = sense.meanings.slice(0, cap);
        } else {
          items = sense.meanings;
        }
        if (items.length === 0) continue;
        shown += items.length;
''', "cap")
p.write_text(t, encoding="utf-8")

p = pathlib.Path("src/main/src/components/options/ankiTemplate/AnkiTemplateFieldOptionsEdit.svelte")
t = p.read_text(encoding="utf-8")
t = once(t, '''      title="Макс. переводов на значение"
      min={0}
    >
      Первые N переводов на значение. 0 — без ограничений.''', '''      title="Макс. переводов"
      min={0}
    >
      Первые N переводов: в списке — всего, в одной строке — на значение. 0 — без ограничений.''', "cap label")
p.write_text(t, encoding="utf-8")
print("v1.83 fixes applied")
