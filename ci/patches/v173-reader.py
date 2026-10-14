# v1.73: reading. Difficulty and coverage of chapters, volumes and novels (the same analysis as the episodes of the
# videos, now shared as TextAnalysis), a jump to any volume, a tap anywhere closes the dictionary (a tap on another
# word no longer opens it full-screen), the exact place is kept (the first paragraph on screen), the mining queue,
# the paragraphs read count in the statistics as they scroll past. The code is v173-reader.swift (it replaces the
# library, novel and reader screens of 1.72).
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

# ---------- the novel keeps how far its episodes were counted (older files have no such field) ----------
s = between(s, "/// A web novel saved for offline reading: its table of contents and the reading state.\nstruct NovelInfo",
            "struct NovelEpisode: Codable, Identifiable {", '''/// A web novel saved for offline reading: its table of contents and the reading state.
struct NovelInfo: Codable, Identifiable {
    let ncode: String
    var title: String
    var writer: String
    var story: String
    var shortStory: Bool
    var finished: Bool
    var episodes: [NovelEpisode]
    var addedAt: Date
    /// episodes read to the end
    var read: Set<Int> = []
    var lastRead: Int? = nil
    /// the first paragraph shown last time, per episode
    var positions: [Int: Int] = [:]
    /// the last paragraph counted in the reading statistics, per episode
    var counted: [Int: Int] = [:]
    var id: String { ncode }

    enum CodingKeys: String, CodingKey {
        case ncode, title, writer, story, shortStory, finished, episodes, addedAt, read, lastRead, positions, counted
    }

    init(ncode: String, title: String, writer: String, story: String, shortStory: Bool, finished: Bool,
         episodes: [NovelEpisode], addedAt: Date) {
        self.ncode = ncode
        self.title = title
        self.writer = writer
        self.story = story
        self.shortStory = shortStory
        self.finished = finished
        self.episodes = episodes
        self.addedAt = addedAt
    }

    /// novels saved by 1.72 have no "counted"
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        ncode = try c.decode(String.self, forKey: .ncode)
        title = try c.decode(String.self, forKey: .title)
        writer = (try? c.decode(String.self, forKey: .writer)) ?? ""
        story = (try? c.decode(String.self, forKey: .story)) ?? ""
        shortStory = (try? c.decode(Bool.self, forKey: .shortStory)) ?? false
        finished = (try? c.decode(Bool.self, forKey: .finished)) ?? false
        episodes = (try? c.decode([NovelEpisode].self, forKey: .episodes)) ?? []
        addedAt = (try? c.decode(Date.self, forKey: .addedAt)) ?? Date()
        read = (try? c.decode(Set<Int>.self, forKey: .read)) ?? []
        lastRead = try? c.decode(Int.self, forKey: .lastRead)
        positions = (try? c.decode([Int: Int].self, forKey: .positions)) ?? [:]
        counted = (try? c.decode([Int: Int].self, forKey: .counted)) ?? [:]
    }
}

''', "novel info")

# ---------- the episodes of the videos use the shared analysis ----------
s = between(s, "    nonisolated static func analyze(of file: URL, index: KnownWordsIndex, level: Int, vocabulary: Int) -> EpisodeAnalysis? {\n",
            "    /// The known word index, built again when the known words change.",
            "    nonisolated static func analyze(of file: URL, index: KnownWordsIndex, level: Int, vocabulary: Int) -> EpisodeAnalysis? {\n"
            "        TextAnalysis.analyze(lines: EmbeddedSubtitles.cues(fromFile: file).map { $0.text }, index: index, level: level,\n"
            "                             vocabulary: vocabulary)\n    }\n\n", "video analysis")

# ---------- the screens of 1.72 give way to the new ones ----------
s = between(s, "/// The saved novels.\n@available(iOS 16.0, *)\nstruct NovelLibraryView", "/// The download in progress, with a stop button.",
            "", "old library")
s = between(s, "/// A novel: the synopsis, downloads and the table of contents by volumes.\n@available(iOS 16.0, *)\nstruct NovelDetailView",
            "/// A word tapped in the text: its sentence for the dictionary", "", "old novel")
s = between(s, "/// The reader: one episode, word lookup and mining, the place kept, the next episode.\n@available(iOS 16.0, *)\nstruct NovelReaderView",
            "/// A label with its icon after the title", "", "old reader")
s = s.rstrip("\n") + "\n" + (here / "v173-reader.swift").read_text(encoding="utf-8")
hv.write_text(s, encoding="utf-8")
print("v1.73 reader applied")
