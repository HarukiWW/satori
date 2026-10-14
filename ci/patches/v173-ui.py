# v1.73: the interface.
# - Video tab: two buttons on the left (catalog, mining queue) and one "+" menu on the right (files, YouTube, new
#   folder, Jimaku key): the six buttons did not fit.
# - Landscape dictionary panel of both players: it slides out as well (a removed view vanished at once).
# - Settings: a "Готово" button above the number keyboard; the accent colour as a compact menu with a swatch, and
#   UIKit controls (pickers, menus) take the new colour at once; the highlight is one switch "по частотности" (the
#   general switch and the JLPT levels are gone, here and in Safari); "Очередь майнинга" in the Anki section.
# - Watching statistics: subtitle lines and finished videos are counted; the cards are time, words, lines,
#   finished videos, words per minute and days in a row ("в среднем за день" is gone).
import pathlib


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


def times(text, old, new, count, label):
    assert text.count(old) == count, "pattern not found " + str(count) + " times: " + label
    return text.replace(old, new)


def between(text, start, end, new, label):
    assert text.count(start) == 1, "start not found exactly once: " + label
    a = text.index(start)
    b = text.index(end, a)
    return text[:a] + new + text[b:]


hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")

# ---------- video tab: the toolbar ----------
s = between(s, """        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                Button {
                    showImporter = true""", "        .sheet(isPresented: $showKey) {\n", """        .toolbar {
            ToolbarItem(placement: .navigationBarLeading) {
                NavigationLink(destination: CatalogView()) {
                    Image(systemName: "books.vertical")
                }
            }
            ToolbarItem(placement: .navigationBarLeading) {
                Button {
                    showQueue = true
                } label: {
                    Image(systemName: "tray.full")
                }
            }
            ToolbarItem(placement: .navigationBarTrailing) {
                Menu {
                    Button {
                        showImporter = true
                    } label: {
                        Label("Видео из «Файлов»", systemImage: "doc.badge.plus")
                    }
                    Button {
                        showYouTube = true
                    } label: {
                        Label("Видео с YouTube", systemImage: "play.rectangle")
                    }
                    Button {
                        showNewFolder = true
                    } label: {
                        Label("Новая папка", systemImage: "folder.badge.plus")
                    }
                    Divider()
                    Button {
                        showKey = true
                    } label: {
                        Label("Ключ Jimaku", systemImage: "key")
                    }
                } label: {
                    Image(systemName: "plus")
                }
            }
        }
""", "video toolbar")

# ---------- landscape dictionary panel: in and out ----------
s = times(s, "    @State private var forcedLandscape = false\n", """    @State private var forcedLandscape = false
    /// the landscape dictionary panel: kept on screen while it slides out, then removed
    @State private var panelMounted = false
    @State private var panelLowered = true
""", 2, "panel state")
s = times(s, "    /// Landscape (also with the rotation lock on) and back.\n    private func toggleLandscape() {", """    /// The landscape panel slides in and out (a view taken away at once would vanish without the animation).
    private func movePanel(_ shown: Bool) {
        if shown {
            panelLowered = true
            panelMounted = true
            DispatchQueue.main.async {
                withAnimation(.easeOut(duration: 0.25)) {
                    panelLowered = false
                }
            }
        } else {
            withAnimation(.easeIn(duration: 0.22)) {
                panelLowered = true
            }
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.25) {
                if !showLookup {
                    panelMounted = false
                }
            }
        }
    }

    /// Landscape (also with the rotation lock on) and back.
    private func toggleLandscape() {""", 2, "panel helper")
s = once(s, """            if showLookup && verticalSize == .compact {
                landscapeLookup
                    .ignoresSafeArea(edges: .bottom)
                    .transition(.move(edge: .bottom))
            }
        }
        .animation(.easeOut(duration: 0.25), value: showLookup)
""", """            if panelMounted && verticalSize == .compact {
                landscapeLookup
                    .ignoresSafeArea(edges: .bottom)
                    .offset(y: panelLowered ? UIScreen.main.bounds.height : 0)
            }
        }
""", "file player panel")
s = once(s, """            if landscape && showLookup {
                landscapeLookup
                    .ignoresSafeArea(edges: .bottom)
                    .transition(.move(edge: .bottom))
            }
        }
        .animation(.easeOut(duration: 0.25), value: showLookup)
""", """            if landscape && panelMounted {
                landscapeLookup
                    .ignoresSafeArea(edges: .bottom)
                    .offset(y: panelLowered ? UIScreen.main.bounds.height : 0)
            }
        }
""", "youtube panel")
s = once(s, """        .onChange(of: showLookup) { shown in
            if !shown, lookupWasPlaying {
                coordinator.playerLayer?.play()
            }
        }
""", """        .onChange(of: showLookup) { shown in
            movePanel(shown)
            if !shown, lookupWasPlaying {
                coordinator.playerLayer?.play()
            }
        }
""", "file player panel trigger")
s = once(s, """        .onChange(of: showLookup) { shown in
            if !shown, lookupWasPlaying {
                player.play()
            }
        }
""", """        .onChange(of: showLookup) { shown in
            movePanel(shown)
            if !shown, lookupWasPlaying {
                player.play()
            }
        }
""", "youtube panel trigger")

# ---------- settings ----------
s = once(s, """                Picker("Акцентный цвет", selection: $accent) {
                    ForEach(AppAccent.options, id: \\.hex) { option in
                        Text(option.name).tag(option.hex)
                    }
                }
""", """                HStack {
                    Text("Акцентный цвет")
                    Spacer()
                    Menu {
                        ForEach(AppAccent.options, id: \\.hex) { option in
                            Button(option.name) {
                                accent = option.hex
                            }
                        }
                    } label: {
                        HStack(spacing: 6) {
                            Circle()
                                .fill(AppAccent.color(accent))
                                .frame(width: 14, height: 14)
                            Text(AppAccent.name(accent))
                                .foregroundColor(.secondary)
                        }
                    }
                }
""", "accent menu")
s = once(s, """            Section {
                Toggle("Подсвечивать слова", isOn: config.bool("highlight.enabled", false))
            } header: {
                Text("Подсветка слов")
            } footer: {
                Text("Выделяет слова, которых ещё нет в Anki. После изменения обновите страницу.")
            }

            Section {
                Toggle("Подсвечивать по частотности", isOn: config.bool("highlight.freq", true))
""", """            Section {
                Toggle("Подсвечивать по частотности", isOn: highlightOn)
""", "one highlight switch")
s = once(s, """                Text("1 — самое частое слово. Слова чаще первого места и реже второго не выделяются.")
            }

            Section {
                Toggle("N5 🟢", isOn: config.bool("highlight.jlpt.n5", false))
                Toggle("N4 🔵", isOn: config.bool("highlight.jlpt.n4", false))
                Toggle("N3 🟡", isOn: config.bool("highlight.jlpt.n3", false))
                Toggle("N2 🟠", isOn: config.bool("highlight.jlpt.n2", false))
                Toggle("N1 🔴", isOn: config.bool("highlight.jlpt.n1", false))
            } header: {
                Text("Подсветка по уровню JLPT")
            }
""", """                Text("Выделяет слова, которых ещё нет в Anki: от первого места до второго (1 — самое частое слово). В Safari после изменения обновите страницу.")
            }
""", "no JLPT section")
s = once(s, """                Toggle("Возвращаться в Safari после добавления заметки", isOn: config.bool("anki.ios_auto_redirect", true))
""", """                Toggle("Возвращаться в Safari после добавления заметки", isOn: config.bool("anki.ios_auto_redirect", true))
                Toggle("Очередь майнинга", isOn: $miningQueue)
""", "queue switch")
s = once(s, """                NavigationLink(destination: webPage("ankiImport", "Импорт колоды Anki")) {
                    Text("Импорт колоды Anki")
                }
            } header: {
                Text("Anki")
            }
""", """                NavigationLink(destination: webPage("ankiImport", "Импорт колоды Anki")) {
                    Text("Импорт колоды Anki")
                }
            } header: {
                Text("Anki")
            } footer: {
                Text("Очередь майнинга: кнопка ⊕ в видео и в чтении кладёт заметку в очередь, а не открывает AnkiMobile. Очередь — кнопка вверху вкладок «Видео» и «Чтение».")
            }
""", "anki footer")
s = once(s, "    @AppStorage(AppAccent.key) private var accent = AppAccent.standard\n", """    @AppStorage(AppAccent.key) private var accent = AppAccent.standard
    @AppStorage("ykMiningQueue") private var miningQueue = false

    /// One switch: the frequency highlight is the only one left (the general switch follows it).
    private var highlightOn: Binding<Bool> {
        Binding(get: {
            config.bool("highlight.enabled", false).wrappedValue && config.bool("highlight.freq", true).wrappedValue
        }, set: { value in
            config.set("highlight.enabled", value)
            config.set("highlight.freq", value)
        })
    }
""", "settings state")
s = once(s, """        .onAppear {
            config.reload()
        }
        .onChange(of: accent) { value in
""", """        // the number pad has no return key
        .toolbar {
            ToolbarItemGroup(placement: .keyboard) {
                Spacer()
                Button("Готово") {
                    UIApplication.shared.sendAction(#selector(UIResponder.resignFirstResponder), to: nil, from: nil, for: nil)
                }
            }
        }
        .onAppear {
            config.reload()
        }
        .onChange(of: accent) { value in
""", "keyboard done")
s = once(s, '        ("#0a84ff", "Синий"), ("#c4392b", "Красный (Satori)"),', '        ("#0a84ff", "Синий"), ("#c4392b", "Красный"),',
         "accent names")
s = once(s, """    static func color(_ hex: String) -> Color {
        let clean = hex.trimmingCharacters(in: CharacterSet(charactersIn: "#"))""", """    static func name(_ hex: String) -> String {
        options.first { $0.hex == hex }?.name ?? "Синий"
    }

    /// Menus, pickers and alerts are UIKit: they take the colour of the window, set at once (no restart).
    @MainActor
    static func applyToWindows(_ hex: String) {
        let tint = UIColor(color(hex))
        for scene in UIApplication.shared.connectedScenes {
            guard let windowScene = scene as? UIWindowScene else { continue }
            for window in windowScene.windows {
                window.tintColor = tint
            }
        }
    }

    static func color(_ hex: String) -> Color {
        let clean = hex.trimmingCharacters(in: CharacterSet(charactersIn: "#"))""", "accent helpers")
s = once(s, """                              Text("Кнопка ⊕ в словаре кладёт карточку в очередь серии, а не открывает AnkiMobile. Очередь — свайп по серии в списке видео.")""",
         """                              Text("Кнопка ⊕ в словаре кладёт заметку в очередь, а не открывает AnkiMobile. Тот же переключатель — в Настройках → Anki. Очередь — кнопка вверху вкладки «Видео».")""",
         "player queue note")
s = once(s, """                    Text("Очередь пуста. Включите «Очередь майнинга» в настройках плеера и добавляйте слова кнопкой ⊕ в словаре.")""",
         """                    Text("Очередь пуста. Включите «Очередь майнинга» (Настройки → Anki или меню плеера) и добавляйте слова кнопкой ⊕ в словаре.")""",
         "empty queue")

# ---------- the highlight: frequency only ----------
s = once(s, '                s.jlpt[n] = root["highlight.jlpt.n\\(n)"] as? Bool ?? false\n',
         "                // the JLPT highlight is gone (1.73): only the frequency highlight is left\n                s.jlpt[n] = false\n",
         "no JLPT colours")

# ---------- watching statistics ----------
s = once(s, """struct WatchDay: Codable {
    var time = 0
    var words = 0
}
""", """struct WatchDay: Codable {
    var time = 0
    var words = 0
    /// subtitle lines shown (since 1.73)
    var lines = 0
    /// videos watched to the end (since 1.73)
    var episodes = 0

    enum CodingKeys: String, CodingKey {
        case time, words, lines, episodes
    }

    init() {}

    /// days saved before 1.73 have no lines and episodes
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        time = (try? c.decode(Int.self, forKey: .time)) ?? 0
        words = (try? c.decode(Int.self, forKey: .words)) ?? 0
        lines = (try? c.decode(Int.self, forKey: .lines)) ?? 0
        episodes = (try? c.decode(Int.self, forKey: .episodes)) ?? 0
    }
}
""", "watch day")
s = once(s, """    static func add(seconds: Int, words: Int) {
        var days = load()
        let today = statKey(daysAgo: 0)
        var day = days[today] ?? WatchDay()
        day.time += seconds
        day.words += words
""", """    static func add(seconds: Int, words: Int, lines: Int = 0, episodes: Int = 0) {
        var days = load()
        let today = statKey(daysAgo: 0)
        var day = days[today] ?? WatchDay()
        day.time += seconds
        day.words += words
        day.lines += lines
        day.episodes += episodes
""", "watch add")
s = once(s, """struct WatchSummary {
    var time = 0
    var words = 0
    var average = 0
}
""", """struct WatchSummary {
    var time = 0
    var words = 0
    var average = 0
    var lines = 0
    var episodes = 0
}
""", "watch summary")
s = times(s, "result.words += day.words\n", "result.words += day.words\n                result.lines += day.lines\n"
          "                result.episodes += day.episodes\n", 2, "watch summary sums")
s = once(s, """                        StatCard(title: "Слов из субтитров", value: statNumber(w.words))
                        StatCard(title: "Время просмотра", value: statDuration(w.time))
                        StatCard(title: "Дней подряд", value: statNumber(model.watchStreak()))
                        StatCard(title: "В среднем за день", value: statDuration(w.average))
""", """                        StatCard(title: "Время просмотра", value: statDuration(w.time))
                        StatCard(title: "Слов из субтитров", value: statNumber(w.words))
                        StatCard(title: "Реплик", value: statNumber(w.lines))
                        StatCard(title: "Серий досмотрено", value: statNumber(w.episodes))
                        StatCard(title: "Слов в минуту", value: watchSpeed(w))
                        StatCard(title: "Дней подряд", value: statNumber(model.watchStreak()))
""", "watch cards")
s = once(s, "    private func speed(_ s: StatSummary) -> String {\n", """    /// Words of the subtitles per minute of watching.
    private func watchSpeed(_ w: WatchSummary) -> String {
        guard w.time >= 60, w.words > 0 else { return "—" }
        let minutes: Double = Double(w.time) / 60
        return statNumber(Int((Double(w.words) / minutes).rounded()))
    }

    private func speed(_ s: StatSummary) -> String {
""", "watch speed")
s = once(s, """        if position >= duration * 0.92 {
            UserDefaults.standard.set(true, forKey: "watched." + name)
        }
""", """        if position >= duration * 0.92, !isWatched(name) {
            UserDefaults.standard.set(true, forKey: "watched." + name)
            // a finished video counts once in the watching statistics
            WatchStats.add(seconds: 0, words: 0, episodes: 1)
        }
""", "finished videos")
s = times(s, "    @State private var watchWords = 0\n", "    @State private var watchWords = 0\n    @State private var watchLines = 0\n", 2,
          "watch lines state")
s = times(s, "            lastCountedLine = line\n            watchWords += ", "            lastCountedLine = line\n            watchLines += 1\n"
          "            watchWords += ", 2, "watch lines count")
s = times(s, """        guard seconds > 0 || watchWords > 0 else { return }
        WatchStats.add(seconds: seconds, words: watchWords)
        watchPending = 0
        watchWords = 0
""", """        guard seconds > 0 || watchWords > 0 || watchLines > 0 else { return }
        WatchStats.add(seconds: seconds, words: watchWords, lines: watchLines)
        watchPending = 0
        watchWords = 0
        watchLines = 0
""", 2, "watch lines flush")
hv.write_text(s, encoding="utf-8")

# ---------- the app: UIKit tint follows the accent ----------
mv = pathlib.Path("src/safari/iOS (App)/MainView.swift")
m = mv.read_text(encoding="utf-8")
m = once(m, """        .accentColor(AppAccent.color(accent))
        .tint(AppAccent.color(accent))
""", """        .accentColor(AppAccent.color(accent))
        .tint(AppAccent.color(accent))
        .onAppear {
            AppAccent.applyToWindows(accent)
        }
        .onChange(of: accent) { value in
            AppAccent.applyToWindows(value)
        }
""", "window tint")
mv.write_text(m, encoding="utf-8")

# ---------- Safari: the frequency highlight only ----------
fh = pathlib.Path("src/main/src/extension/content/freqHighlight.ts")
t = fh.read_text(encoding="utf-8")
t = once(t, """  const jlptFlags: [number, boolean][] = [
    [5, config.get("highlight.jlpt.n5")],
    [4, config.get("highlight.jlpt.n4")],
    [3, config.get("highlight.jlpt.n3")],
    [2, config.get("highlight.jlpt.n2")],
    [1, config.get("highlight.jlpt.n1")],
  ];
  const jlptLevels = new Set(jlptFlags.filter(([, on]) => on).map(([n]) => n));
""", """  // the JLPT highlight is gone (1.73): only the frequency highlight is left
  const jlptLevels = new Set<number>();
""", "web no JLPT")
fh.write_text(t, encoding="utf-8")
gh = pathlib.Path("src/main/src/components/options/groups/GroupHighlight.svelte")
g = gh.read_text(encoding="utf-8")
g = once(g, """<GroupedOptions title="Подсветка слов">
  <OptionToggle bind:value={$enabledConfig} title="Подсвечивать слова">
    Выделяет слова, которых ещё нет в Anki. После изменения обновите страницу.
  </OptionToggle>
</GroupedOptions>

""", "", "web general switch")
g = once(g, """    Выделяет слова по частотности: 1 — самое частое слово, чем больше число, тем реже слово.""",
         """    Выделяет слова, которых ещё нет в Anki, по частотности: 1 — самое частое слово. После изменения обновите страницу.""",
         "web switch text")
g = once(g, "  $: to = Math.max(Number($minConfig), Number($maxConfig));\n",
         "  $: to = Math.max(Number($minConfig), Number($maxConfig));\n"
         "  // one switch: the general highlight switch follows the frequency one\n"
         "  $: if ($enabledConfig !== $freqConfig) $enabledConfig = $freqConfig;\n", "web one switch")
g = between(g, '<GroupedOptions title="Подсветка по уровню JLPT">', "<style>", "", "web no JLPT group")
gh.write_text(g, encoding="utf-8")
print("v1.73 interface applied")
