# v2.06: the settings, cleaned up.
# - Настройки → Anki keeps the backup folder, «Прочитать последний бэкап сейчас» and «Не следить за бэкапами»; the
#   drop zone, the folder check, the backup file, the signature report and the transfer are gone (with their code),
#   and so are the long explanations: the gray texts under the sections and in the Anki section.
# - New backups can be looked for every 5, 15, 30 or 60 minutes while Satori is open, not only when it opens.
# - No web pages in the settings: «Импорт колоды Anki» (the backups replace it) and «О программе и лицензии» are gone,
#   and «Шаблон Anki» is native (deck, note type, the content of every field and its options, tags).
# - The top of the settings is no more a black bar: the title is part of the page (as on «Статистика»), and the bars
#   of the app are clear at the top and blurred when content goes under them, so the live background shows.
# - A word of a list of unknown words vanished at a light tap: the full swipe marked it «Знаю» or «Игнор». The swipe
#   now only opens the buttons, and «Отмеченные слова» (Настройки → Anki) shows the marked words to take a mark away.
# - The bars of «Статистика» take the accent colour.
import pathlib
import re


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)




here = pathlib.Path(__file__).resolve().parent
hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")

# --- the settings page: the title in the page, no footers, no web pages
start = "struct NativeSettingsView: View {"
end = "/// Reports for finding problems"
a = s.index(start)
b = s.index(end, a)
page = s[a:b]
page, n = re.subn(r"\n            \} footer: \{\n                Text\([^\n]*\)\n            \}", "\n            }", page)
assert n == 4, "settings footers: " + str(n)
c = page.index("    private var levelFooter: String {")
d = page.index("    /// One switch: the frequency highlight")
page = page[:c] + page[d:]
page = once(page, '''        Form {
            Section {
                Picker("Японский шрифт"''', '''        Form {
            Section {
            } header: {
                Text("Настройки")
                    .font(.system(size: 30, weight: .bold))
                    .foregroundColor(.primary)
                    .textCase(nil)
                    .padding(.top, 6)
            }
            Section {
                Picker("Японский шрифт"''', "settings title")
page = once(page, '''                Button("Настроить шаблон Anki") {
                    onAnkiTemplate()
                }
                NavigationLink(destination: AnkiImportPage()) {
                    Text("Импорт колоды Anki")
                }
''', '''                Button("Шаблон Anki") {
                    onAnkiTemplate()
                }
''', "anki rows")
page = once(page, '''                MarksResetRow()
''', '''                NavigationLink(destination: MarkedWordsView()) {
                    Text("Отмеченные слова")
                }
''', "marked words row")
page = once(page, '''            Section {
                NavigationLink(destination: webPage("about", "О программе")) {
                    Text("О программе и лицензии")
                }
            }

''', "", "about section")
c = page.index("    private func webPage(_ only: String, _ title: String) -> some View {")
d = page.index("    private func numberRow(")
page = page[:c] + page[d:]
s = s[:a] + page + s[b:]

s = once(s, '''        .navigationTitle("Диагностика")
        .navigationBarTitleDisplayMode(.inline)
''', '''        .navigationTitle("Диагностика")
        .navigationBarTitleDisplayMode(.inline)
        .navigationBarHidden(false)
''', "diagnostics bar")

# --- the Anki section: the folder, how often, read now, stop
a = s.index("/// Настройки → Anki: the folder of the backups of AnkiMobile.\nstruct AnkiBackupRow: View {")
b = s.index("/// One frame of a video file (FFmpeg)", a)
s = s[:a] + '''/// Настройки → Anki: the folder of the backups of AnkiMobile and how often new backups are looked for.
struct AnkiBackupRow: View {
    @ObservedObject private var sync = AnkiBackupSync.shared
    /// minutes between the checks while Satori is open; 0: only when it opens
    @AppStorage("ykBackupInterval") private var interval = 0

    /// what happened last, or when the last backup was read
    private var status: String {
        if !sync.status.isEmpty {
            return sync.status
        }
        guard let date = sync.lastRead else { return "" }
        return "Последний бэкап: " + date.formatted(date: .abbreviated, time: .shortened)
    }

    var body: some View {
        Group {
            Button(sync.connected ? "Папка бэкапов AnkiMobile: выбрана" : "Папка бэкапов AnkiMobile…") {
                FolderPick.present({ url in
                    sync.choose(url)
                }, multiple: true)
            }
            if sync.connected {
                Picker("Новые бэкапы", selection: $interval) {
                    Text("При открытии").tag(0)
                    Text("Каждые 5 минут").tag(5)
                    Text("Каждые 15 минут").tag(15)
                    Text("Каждые 30 минут").tag(30)
                    Text("Каждый час").tag(60)
                }
                Button(sync.importing ? "Читаю бэкап…" : "Прочитать последний бэкап сейчас") {
                    sync.check(force: true)
                }
                .disabled(sync.importing)
                Button("Не следить за бэкапами", role: .destructive) {
                    sync.disconnect()
                }
            }
            if !status.isEmpty {
                Text(status)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
        }
    }
}

''' + s[b:]

# the drop zone (2.01), the signature report (2.03) and the transfer (2.04) are no more used
a = s.index("/// A folder dragged in from «Файлы»: open this page")
s = s[:a].rstrip("\n") + "\n"

# --- marks: no full swipe, and the lists for «Отмеченные слова»
s = once(s, '''            .swipeActions(edge: .leading, allowsFullSwipe: true) {
                Button {
                    WordMarks.set(word, "known")''', '''            .swipeActions(edge: .leading, allowsFullSwipe: false) {
                Button {
                    WordMarks.set(word, "known")''', "swipe known")
s = once(s, '''            .swipeActions(edge: .trailing, allowsFullSwipe: true) {
                Button {
                    WordMarks.set(word, "ignored")''', '''            .swipeActions(edge: .trailing, allowsFullSwipe: false) {
                Button {
                    WordMarks.set(word, "ignored")''', "swipe ignored")
s = once(s, '''    static func count() -> Int {
        guard let root = load() else { return 0 }
        return all(root).count
    }
''', '''    static func count() -> Int {
        guard let root = load() else { return 0 }
        return all(root).count
    }

    /// The marked words in the order they were marked.
    static func lists() -> (known: [String], ignored: [String]) {
        guard let root = load() else { return ([], []) }
        return ((root["manualKnown"] as? [String]) ?? [], (root["ignored"] as? [String]) ?? [])
    }
''', "marks lists")

# --- the bars of the statistics in the accent colour
s = once(s, '''struct HelpView: View {
    @StateObject private var model = StatsViewModel()
''', '''struct HelpView: View {
    @StateObject private var model = StatsViewModel()
    @AppStorage(AppAccent.key) private var accent = AppAccent.standard
''', "stats accent")
s = once(s, '''                                    .fill(Color.orange)
                                    .frame(height: max(3, 90 * CGFloat(bar.read) / CGFloat(maxRead)))''', '''                                    .fill(AppAccent.color(accent))
                                    .frame(height: max(3, 90 * CGFloat(bar.read) / CGFloat(maxRead)))''', "stats bars")

s = s.rstrip("\n") + "\n" + (here / "v206-settings.swift").read_text(encoding="utf-8")
hv.write_text(s, encoding="utf-8")

# --- OptionsView: no bar over the page, the native template
ov = pathlib.Path("src/safari/iOS (App)/OptionsView.swift")
o = ov.read_text(encoding="utf-8")
a = o.index("                NavigationLink(isActive: self.appState.settingsNavigationIsAnkiTemplate) {")
b = o.index("                } label: { EmptyView() }", a)
o = o[:a] + '''                NavigationLink(isActive: self.appState.settingsNavigationIsAnkiTemplate) {
                    AnkiTemplateView(loadInfo: { try await getAnkiInfoFromPasteboard() })
''' + o[b:]
o = once(o, '''                NativeSettingsView(onAnkiTemplate: { _ = requestAnkiInfo() })
            }
            .navigationTitle("Настройки")
            .navigationBarTitleDisplayMode(.large)
''', '''                // without AnkiMobile the template opens with what was saved
                NativeSettingsView(onAnkiTemplate: {
                    if !requestAnkiInfo() {
                        appState.settingsNavigation = .ankiTemplate
                    }
                })
            }
            .navigationBarHidden(true)
''', "options root")
o = once(o, '''        let appearance = UINavigationBarAppearance()
        appearance.shadowColor = .clear
        appearance.backgroundColor = UIColor(OptionsView.BACKGROUND_COLOR)
        appearance.largeTitleTextAttributes = [.font: UIFont.systemFont(ofSize: 30, weight: .bold)]

        UINavigationBar.appearance().standardAppearance = appearance
        UINavigationBar.appearance().scrollEdgeAppearance = appearance
''', '''        // clear at the top (the live background shows), blurred when content goes under the bar
        let appearance = UINavigationBarAppearance()
        appearance.configureWithDefaultBackground()
        appearance.largeTitleTextAttributes = [.font: UIFont.systemFont(ofSize: 30, weight: .bold)]
        let edge = UINavigationBarAppearance()
        edge.configureWithTransparentBackground()
        edge.largeTitleTextAttributes = appearance.largeTitleTextAttributes

        UINavigationBar.appearance().standardAppearance = appearance
        UINavigationBar.appearance().scrollEdgeAppearance = edge
''', "bar appearance")
ov.write_text(o, encoding="utf-8")

# --- MainView: new backups looked for every few minutes while Satori is open
mv = pathlib.Path("src/safari/iOS (App)/MainView.swift")
m = mv.read_text(encoding="utf-8")
m = once(m, '''    @ObservedObject private var backups = AnkiBackupSync.shared
''', '''    @ObservedObject private var backups = AnkiBackupSync.shared
    @AppStorage("ykBackupInterval") private var backupInterval = 0
''', "main interval")
m = once(m, '''        .onReceive(NotificationCenter.default.publisher(for: UIApplication.didBecomeActiveNotification)) { _ in
            AnkiBackupSync.shared.check()
        }
    }
''', '''        .onReceive(NotificationCenter.default.publisher(for: UIApplication.didBecomeActiveNotification)) { _ in
            AnkiBackupSync.shared.check()
        }
        .task(id: backupInterval) {
            guard backupInterval > 0 else { return }
            while !Task.isCancelled {
                try? await Task.sleep(nanoseconds: UInt64(backupInterval) * 60_000_000_000)
                guard !Task.isCancelled else { return }
                if UIApplication.shared.applicationState == .active {
                    AnkiBackupSync.shared.check()
                }
            }
        }
    }
''', "main backup task")
mv.write_text(m, encoding="utf-8")
print("v2.06 settings applied")
