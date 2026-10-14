# v1.74: the last word of a subtitle line, the statistics, the unknown word lists.
# - FlowLayout finds its rows once for the size and the placing (with half a point to spare): the last word of a
#   line (a particle, an auxiliary) no longer falls into a row that was not measured and is cut off.
# - Statistics: the blocks of reading and watching mean the same things in the same places; chapters read; words
#   per minute; the chart of reading shows words; the reset button is under "Добавленные слова".
# - The Safari extension no longer counts reading (it was not accurate): its popup is the original one again.
# - Unknown words of an episode, a title or a novel open the dictionary, and ⊕ puts them into the mining queue.
import pathlib


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


def between(text, start, end, new, label):
    assert text.count(start) == 1, "start not found exactly once: " + label
    a = text.index(start)
    b = text.index(end, a)
    return text[:a] + new + text[b:]


hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")

# ---------- the rows of a subtitle line ----------
s = between(s, "/// Lays its items out in rows and wraps to the next row when they do not fit.\n",
            "/// Frequency and JLPT tables of the web app (res/hl)", '''/// Lays its items out in rows and wraps to the next row when they do not fit. The rows are found the same way for
/// the size and for the placing (half a point to spare): the last word never falls into a row that was not measured.
@available(iOS 16.0, *)
struct FlowLayout: Layout {
    var spacing: CGFloat = 0

    /// Every item's frame from (0, 0), and the size of them all.
    private func arrange(_ subviews: Subviews, width: CGFloat) -> (frames: [CGRect], size: CGSize) {
        var frames: [CGRect] = []
        var x: CGFloat = 0
        var y: CGFloat = 0
        var rowHeight: CGFloat = 0
        var widest: CGFloat = 0
        for view in subviews {
            let size = view.sizeThatFits(.unspecified)
            if x > 0 && x + size.width > width + 0.5 {
                x = 0
                y += rowHeight + spacing
                rowHeight = 0
            }
            frames.append(CGRect(x: x, y: y, width: size.width, height: size.height))
            x += size.width + spacing
            rowHeight = max(rowHeight, size.height)
            widest = max(widest, x - spacing)
        }
        return (frames, CGSize(width: min(widest, width), height: y + rowHeight))
    }

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        arrange(subviews, width: proposal.width ?? .infinity).size
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        // the rows of the width the size was measured for (the bounds may be a little narrower after rounding)
        let laid = arrange(subviews, width: max(bounds.width, proposal.width ?? bounds.width))
        for (index, view) in subviews.enumerated() where index < laid.frames.count {
            let frame = laid.frames[index]
            view.place(at: CGPoint(x: bounds.minX + frame.minX, y: bounds.minY + frame.minY), anchor: .topLeading,
                       proposal: ProposedViewSize(frame.size))
        }
    }
}

''', "flow layout")

# ---------- statistics: chapters ----------
s = once(s, '''    var sentences = 0
    var words = 0

    enum CodingKeys: String, CodingKey {
        case mined, kanji, read, time, sentences, words
    }
''', '''    var sentences = 0
    var words = 0
    /// chapters of novels read to the end (since 1.74)
    var chapters = 0

    enum CodingKeys: String, CodingKey {
        case mined, kanji, read, time, sentences, words, chapters
    }
''', "stat day chapters")
s = once(s, "        words = (try? c.decode(Int.self, forKey: .words)) ?? 0\n    }\n}\n\nstruct StatFile",
         "        words = (try? c.decode(Int.self, forKey: .words)) ?? 0\n"
         "        chapters = (try? c.decode(Int.self, forKey: .chapters)) ?? 0\n    }\n}\n\nstruct StatFile", "stat day decode")
s = once(s, "    var sentences = 0\n    var readWords = 0\n}\n", "    var sentences = 0\n    var readWords = 0\n    var chapters = 0\n}\n",
         "stat summary chapters")
s = once(s, "            result.readWords += day.words\n", "            result.readWords += day.words\n            result.chapters += day.chapters\n",
         "summary chapters")
s = once(s, "            result.append(StatBar(id: key, label: label, read: days[key]?.read ?? 0))\n",
         "            result.append(StatBar(id: key, label: label, read: days[key]?.words ?? 0))\n", "bars words")
s = once(s, '''    private func speed(_ s: StatSummary) -> String {
        if s.time < 60 || s.read == 0 {
            return "—"
        }
        return statNumber(Int((Double(s.read) / (Double(s.time) / 60.0)).rounded()))
    }
''', '''    /// Words read per minute of reading.
    private func speed(_ s: StatSummary) -> String {
        if s.time < 60 || s.readWords == 0 {
            return "—"
        }
        return statNumber(Int((Double(s.readWords) / (Double(s.time) / 60.0)).rounded()))
    }
''', "reading speed")

# ---------- statistics: the same meaning in the same place ----------
s = once(s, '''                        StatCard(title: "Прочитано предложений", value: statNumber(s.sentences))
                        StatCard(title: "Прочитано слов", value: statNumber(s.readWords))
                        StatCard(title: "Прочитано знаков", value: statNumber(s.read))
                        StatCard(title: "Время чтения", value: statDuration(s.time))
                        StatCard(title: "Скорость, зн./мин", value: speed(s))
                        StatCard(title: "Серия, дней подряд", value: statNumber(model.streak()))
''', '''                        StatCard(title: "Прочитано предложений", value: statNumber(s.sentences))
                        StatCard(title: "Прочитано слов", value: statNumber(s.readWords))
                        StatCard(title: "Прочитано глав", value: statNumber(s.chapters))
                        StatCard(title: "Время чтения", value: statDuration(s.time))
                        StatCard(title: "Слов в минуту", value: speed(s))
                        StatCard(title: "Дней подряд", value: statNumber(model.streak()))
''', "reading cards")
s = once(s, '''                        StatCard(title: "Время просмотра", value: statDuration(w.time))
                        StatCard(title: "Слов из субтитров", value: statNumber(w.words))
                        StatCard(title: "Реплик", value: statNumber(w.lines))
                        StatCard(title: "Серий досмотрено", value: statNumber(w.episodes))
                        StatCard(title: "Слов в минуту", value: watchSpeed(w))
                        StatCard(title: "Дней подряд", value: statNumber(model.watchStreak()))
''', '''                        StatCard(title: "Прочитано реплик", value: statNumber(w.lines))
                        StatCard(title: "Прочитано слов", value: statNumber(w.words))
                        StatCard(title: "Просмотрено серий", value: statNumber(w.episodes))
                        StatCard(title: "Время просмотра", value: statDuration(w.time))
                        StatCard(title: "Слов в минуту", value: watchSpeed(w))
                        StatCard(title: "Дней подряд", value: statNumber(model.watchStreak()))
''', "watch cards")
s = once(s, 'Text(mode == 0 ? "Прочитано знаков за 7 дней" : "Время просмотра за 7 дней, мин")',
         'Text(mode == 0 ? "Прочитано слов за 7 дней" : "Время просмотра за 7 дней")', "chart title")
reset = '''                Button(role: .destructive) {
                    confirmReset = true
                } label: {
                    Text("Сбросить статистику")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.bordered)

'''
s = once(s, reset, "", "reset button out")
s = once(s, '''                    .background(Color(.secondarySystemBackground))
                    .cornerRadius(14)
                }
                .buttonStyle(.plain)
            }
            .padding(16)
''', '''                    .background(Color(.secondarySystemBackground))
                    .cornerRadius(14)
                }
                .buttonStyle(.plain)

''' + reset.rstrip("\n").replace("\n\n", "\n") + '''
            }
            .padding(16)
''', "reset button under the words")

# ---------- unknown words of an episode: the dictionary, ⊕ into the queue ----------
s = once(s, '''    @State private var analysis: EpisodeAnalysis? = nil
    @State private var loading = true

    private func verdict(_ difficulty: Int?) -> String {''', '''    @State private var analysis: EpisodeAnalysis? = nil
    @State private var loading = true
    @State private var lookup: UnknownWord? = nil

    private func verdict(_ difficulty: Int?) -> String {''', "episode words state")
s = once(s, '''                        ForEach(result.unknown.prefix(300)) { word in
                            HStack {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(word.word)
                                        .font(.system(size: 20))
                                    if !word.reading.isEmpty && word.reading != word.word {
                                        Text(word.reading)
                                            .font(.caption)
                                            .foregroundColor(.secondary)
                                    }
                                }
                                Spacer()
                                Text("×" + String(word.count))
                                    .foregroundColor(.secondary)
                            }
                        }
                    } header: {
                        Text("Незнакомые слова: " + String(result.unknown.count))
                    }
''', '''                        ForEach(result.unknown) { word in
                            Button {
                                lookup = word
                            } label: {
                                HStack {
                                    VStack(alignment: .leading, spacing: 2) {
                                        Text(word.word)
                                            .font(.system(size: 20))
                                            .foregroundColor(.primary)
                                        if !word.reading.isEmpty && word.reading != word.word {
                                            Text(word.reading)
                                                .font(.caption)
                                                .foregroundColor(.secondary)
                                        }
                                    }
                                    Spacer()
                                    Text("×" + String(word.count))
                                        .foregroundColor(.secondary)
                                }
                            }
                        }
                    } header: {
                        Text("Незнакомые слова: " + String(result.unknown.count))
                    } footer: {
                        Text("Нажмите на слово, чтобы открыть словарь; ⊕ кладёт его в очередь майнинга.")
                    }
''', "episode words rows")
s = once(s, '''            .task {
                await load()
            }
        }
    }

    private func load() async {
        guard let file = VideoLibraryStore.jimakuFile(for: video) else {''', '''            .task {
                await load()
            }
            .sheet(item: $lookup) { word in
                WordLookupSheet(text: word.word)
            }
        }
        .modifier(QueueMiningHooks(source: VideoKey.of(video)))
    }

    private func load() async {
        guard let file = VideoLibraryStore.jimakuFile(for: video) else {''', "episode words sheet")

# ---------- unknown words of a title or a novel ----------
s = once(s, '''                Text("Самые частые незнакомые слова (до 500). Нажмите на слово, чтобы открыть словарь и добавить его в Anki.")
            }
        }
        .navigationTitle("Незнакомые слова")
        .navigationBarTitleDisplayMode(.inline)
        .sheet(item: $lookup) { word in
            WordLookupSheet(text: word.word)
        }
''', '''                Text("Все незнакомые слова, самые частые сверху. Нажмите на слово, чтобы открыть словарь; ⊕ кладёт его "
                     + "в очередь майнинга.")
            }
        }
        .navigationTitle("Незнакомые слова: " + String(words.count))
        .navigationBarTitleDisplayMode(.inline)
        .sheet(item: $lookup) { word in
            WordLookupSheet(text: word.word)
        }
        .modifier(QueueMiningHooks(source: title))
''', "title words")
hv.write_text(s, encoding="utf-8")

# ---------- Safari: no reading statistics ----------
ext = pathlib.Path("src/main/src/extension")
popup = ext / "popup/index.ts"
p = popup.read_text(encoding="utf-8")
p = once(p, 'import PopupPage from "./StatsPage.svelte";', 'import PopupPage from "./PopupPage.svelte";', "popup page")
popup.write_text(p, encoding="utf-8")
content = ext / "content/index.ts"
c = content.read_text(encoding="utf-8")
c = once(c, 'import "./readingStats";\n', "", "reading stats")
content.write_text(c, encoding="utf-8")
print("v1.74 ui applied")
