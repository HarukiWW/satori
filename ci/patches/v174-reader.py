# v1.74: reading. The lists stay smooth while chapters download (the progress has its own object, the store
# publishes the downloaded episodes at most every 3 s, the analysis every 10 episodes, the reader observes nothing);
# volumes fold (the one being read is open); a search with the Japanese keyboard while reading; a finished chapter
# counts in the statistics ("Прочитано глав"); "Продолжить" shows the whole chapter title. The code is
# v174-reader.swift (it replaces the library, novel and reader screens of 1.73).
import pathlib


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


def between(text, start, end, new, label):
    assert text.count(start) == 1, "start not found exactly once: " + label
    a = text.index(start)
    b = text.index(end, a) if end is not None else len(text)
    return text[:a] + new + text[b:]


here = pathlib.Path(__file__).resolve().parent
hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")

# ---------- the store: progress apart, downloaded episodes published every few seconds ----------
s = once(s, "    @Published private(set) var job: Job? = nil\n", """    /// the download in progress (published by NovelProgress: the long lists do not redraw on every page)
    var job: Job? { NovelProgress.shared.job }
    /// the episodes on disk right now; `downloaded` follows them at most every 3 s
    private var onDisk: [String: Set<Int>] = [:]
    private var lastPublished: CFTimeInterval = 0
""", "store job")
s = once(s, "        novels = loaded.sorted { $0.addedAt > $1.addedAt }\n    }\n",
         "        novels = loaded.sorted { $0.addedAt > $1.addedAt }\n        onDisk = downloaded\n    }\n", "store init")
s = once(s, "        downloaded[ncode] = downloaded[ncode] ?? []\n",
         "        onDisk[ncode] = onDisk[ncode] ?? []\n        downloaded[ncode] = onDisk[ncode]\n", "store add")
s = once(s, "        downloaded[ncode] = nil\n", "        onDisk[ncode] = nil\n        downloaded[ncode] = nil\n", "store remove")
s = once(s, "        downloaded[ncode]?.contains(number) ?? false\n", "        onDisk[ncode]?.contains(number) ?? false\n",
         "store is downloaded")
s = once(s, """            downloaded[ncode, default: []].insert(number)
        }
    }
""", """            onDisk[ncode, default: []].insert(number)
            publishDownloaded(force: false)
        }
    }

    /// The long lists redraw at most every 3 s while downloading.
    private func publishDownloaded(force: Bool) {
        let now = CACurrentMediaTime()
        guard force || now - lastPublished > 3 else { return }
        lastPublished = now
        downloaded = onDisk
    }
""", "store keep")
s = once(s, "        let have = downloaded[ncode] ?? []\n", "        let have = onDisk[ncode] ?? []\n", "store download")
s = once(s, "        job = Job(ncode: ncode, done: done, total: total, failed: failed)\n",
         "        NovelProgress.shared.job = Job(ncode: ncode, done: done, total: total, failed: failed)\n", "store publish")
s = once(s, "            worker = nil\n            job = nil\n", "            worker = nil\n            NovelProgress.shared.job = nil\n"
         "            publishDownloaded(force: true)\n", "store end")

# ---------- the analysis publishes every 10 episodes ----------
s = once(s, """            current.episodes[number] = entry
            episodes[ncode, default: [:]][number] = entry
            unsaved += 1
            if unsaved >= 10 {
                NovelAnalyzer.save(current, ncode)
                unsaved = 0
            }
        }
        if store.novel(ncode) != nil {
""", """            current.episodes[number] = entry
            unsaved += 1
            // the screens redraw every 10 episodes, not on each one
            if unsaved >= 10 {
                episodes[ncode] = current.episodes
                NovelAnalyzer.save(current, ncode)
                unsaved = 0
            }
        }
        episodes[ncode] = current.episodes
        if store.novel(ncode) != nil {
""", "analysis throttle")

# ---------- chapters in the statistics ----------
s = once(s, "    static func add(characters: Int = 0, sentences: Int = 0, words: Int = 0, seconds: Int = 0) {\n"
            "        guard characters > 0 || seconds > 0 else { return }\n",
         "    static func add(characters: Int = 0, sentences: Int = 0, words: Int = 0, seconds: Int = 0, chapters: Int = 0) {\n"
         "        guard characters > 0 || seconds > 0 || chapters > 0 else { return }\n", "stats chapters")
s = once(s, '        day["words"] = number("words") + words\n',
         '        day["words"] = number("words") + words\n        day["chapters"] = number("chapters") + chapters\n', "stats chapters field")

# ---------- the screens of 1.73 give way to the new ones ----------
s = between(s, "/// The saved novels.\n@available(iOS 16.0, *)\nstruct NovelLibraryView",
            "/// A novel: the synopsis, downloads, the grade, and the table of contents by volumes with a jump to any volume.",
            "", "old library")
s = between(s, "/// A novel: the synopsis, downloads, the grade, and the table of contents by volumes with a jump to any volume.",
            "/// iOS 17+: the paragraph at the top edge of the reader is reported exactly", "", "old novel")
s = between(s, "/// The reader: one episode, word lookup and mining (also into the mining queue), the exact place kept, the next",
            None, "", "old reader")
s = s.rstrip("\n") + "\n" + (here / "v174-reader.swift").read_text(encoding="utf-8")
hv.write_text(s, encoding="utf-8")
print("v1.74 reader applied")
