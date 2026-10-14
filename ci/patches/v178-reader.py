# v1.78: reading statistics that scrolling does not fool.
# - A paragraph counts only when it could have been read: the reader earns 12 characters a second while reading
#   (the app open, the text touched or scrolled in the last 90 s; at most 1 500 characters in store), a paragraph
#   passed spends its characters; a paragraph passed faster than that was skimmed and does not count.
# - The last screen of a chapter counts when the chapter is left (not when its last line appears).
# - "Прочитано глав": a chapter counts once, when its end was reached and at least half of its characters were
#   counted (over all the sessions).
import pathlib


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")

# ---------- the novel keeps the characters counted per chapter ----------
s = once(s, '''    /// the last paragraph counted in the reading statistics, per episode
    var counted: [Int: Int] = [:]
    var id: String { ncode }

    enum CodingKeys: String, CodingKey {
        case ncode, title, writer, story, shortStory, finished, episodes, addedAt, read, lastRead, positions, counted
''', '''    /// the last paragraph counted in the reading statistics, per episode
    var counted: [Int: Int] = [:]
    /// characters counted as read (at a reading pace), per episode
    var credited: [Int: Int] = [:]
    /// episodes counted in "Прочитано глав"
    var countedChapters: Set<Int> = []
    var id: String { ncode }

    enum CodingKeys: String, CodingKey {
        case ncode, title, writer, story, shortStory, finished, episodes, addedAt, read, lastRead, positions, counted
        case credited, countedChapters
''', "novel fields")
s = once(s, '''        counted = (try? c.decode([Int: Int].self, forKey: .counted)) ?? [:]
''', '''        counted = (try? c.decode([Int: Int].self, forKey: .counted)) ?? [:]
        credited = (try? c.decode([Int: Int].self, forKey: .credited)) ?? [:]
        // chapters read before 1.78 were counted when their end was reached
        countedChapters = (try? c.decode(Set<Int>.self, forKey: .countedChapters)) ?? read
''', "novel decode")

# ---------- the reader ----------
s = once(s, '''    @State private var countedUpTo = -1
    @State private var lastActivity = CACurrentMediaTime()
''', '''    @State private var countedUpTo = -1
    /// characters that could have been read since the last paragraph counted
    @State private var readBudget: Double = 0
    /// characters counted in this episode now (added to the novel when leaving)
    @State private var creditedChars = 0
    /// the last paragraph was shown: the rest counts when the episode is left
    @State private var reachedEnd = false
    @State private var lastActivity = CACurrentMediaTime()
''', "reader state")
s = once(s, '''        .onDisappear {
            if let text {
                countPassed(upTo: topParagraph, in: text)
            }
            saveState()
''', '''        .onDisappear {
            if let text {
                countPassed(upTo: reachedEnd ? text.body.count : topParagraph, in: text)
            }
            saveState()
''', "leave counts")
s = once(s, '''    private func go(_ next: Int, _ proxy: ScrollViewProxy) {
        if let text {
            countPassed(upTo: topParagraph, in: text)
        }
        saveState()
        text = nil
''', '''    private func go(_ next: Int, _ proxy: ScrollViewProxy) {
        if let text {
            countPassed(upTo: reachedEnd ? text.body.count : topParagraph, in: text)
        }
        saveState()
        reachedEnd = false
        readBudget = 0
        text = nil
''', "next counts")
s = once(s, '''    /// The paragraphs before `end` count in the statistics once (kept here, written to the novel when leaving).
    private func countPassed(upTo end: Int, in text: NovelText) {
        let start = countedUpTo + 1
        let stop = min(end, text.body.count)
        guard stop > start else { return }
        for paragraph in text.body[start ..< stop] where !paragraph.isEmpty {
            pendingCharacters += paragraph.filter { !$0.isWhitespace }.count
''', '''    /// The paragraphs before `end` count in the statistics once (kept here, written to the novel when leaving), each
    /// only when there was time to read it: a paragraph scrolled past faster than 12 characters a second does not.
    private func countPassed(upTo end: Int, in text: NovelText) {
        let start = countedUpTo + 1
        let stop = min(end, text.body.count)
        guard stop > start else { return }
        for paragraph in text.body[start ..< stop] where !paragraph.isEmpty {
            let characters = paragraph.filter { !$0.isWhitespace }.count
            // a very long paragraph needs at most what the store can hold
            guard readBudget >= Double(min(characters, 1200)) else { continue }
            readBudget = max(0, readBudget - Double(characters))
            creditedChars += characters
            pendingCharacters += characters
''', "count at a reading pace")
s = once(s, '''        guard index == text.body.count - 1 else { return }
        countPassed(upTo: text.body.count, in: text)
        if info?.read.contains(number) == false {
            let current = number
            store.update(ncode) { $0.read.insert(current) }
            info?.read.insert(current)
            ReadingStats.add(chapters: 1)
        }
    }
''', '''        guard index == text.body.count - 1 else { return }
        reachedEnd = true
        if info?.read.contains(number) == false {
            let current = number
            store.update(ncode) { $0.read.insert(current) }
            info?.read.insert(current)
        }
    }
''', "end reached")
s = once(s, '''    private func saveState() {
        let current = number
        let top = topParagraph
        let counted = countedUpTo
        store.update(ncode) { novel in
            novel.positions[current] = top
            if counted >= 0 {
                novel.counted[current] = max(novel.counted[current] ?? -1, counted)
            }
        }
    }
''', '''    /// A chapter counts in "Прочитано глав" once: its end was reached and at least half of it was counted.
    private func saveState() {
        let current = number
        let top = topParagraph
        let counted = countedUpTo
        let credited = creditedChars
        creditedChars = 0
        var total = 0
        for paragraph in text?.body ?? [] {
            total += paragraph.filter { !$0.isWhitespace }.count
        }
        var chapterRead = false
        store.update(ncode) { novel in
            novel.positions[current] = top
            if counted >= 0 {
                novel.counted[current] = max(novel.counted[current] ?? -1, counted)
            }
            let read = (novel.credited[current] ?? 0) + credited
            novel.credited[current] = read
            if total > 0, read * 2 >= total, novel.read.contains(current), !novel.countedChapters.contains(current) {
                novel.countedChapters.insert(current)
                chapterRead = true
            }
        }
        if chapterRead {
            ReadingStats.add(chapters: 1)
        }
    }
''', "chapters by pace")
s = once(s, '''        if scenePhase == .active, text != nil, now - lastActivity < 90 {
            pendingSeconds += step
        }
        flush(force: false)
''', '''        if scenePhase == .active, text != nil, now - lastActivity < 90 {
            pendingSeconds += step
            readBudget = min(1500, readBudget + step * 12)
        }
        flush(force: false)
''', "budget grows while reading")
s = once(s, '''            countedUpTo = info?.counted[number] ?? -1
''', '''            countedUpTo = info?.counted[number] ?? -1
            readBudget = 0
            reachedEnd = false
''', "load resets")
hv.write_text(s, encoding="utf-8")
print("v1.78 reader applied")
