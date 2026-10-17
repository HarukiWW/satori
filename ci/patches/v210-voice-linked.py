# v2.10: the voice, the folder of iTorrent.
# - Настройки → Озвучка: the Japanese voice of Satori, «Как в настройках iOS» by default (the voice chosen in
#   Универсальный доступ → Устной контент → Голоса → Японский) or any installed one, with «Прослушать». The grammar
#   cards read with it, the dictionary too once it is chosen (tts.voice). 2.09 picked a voice by itself, and it could
#   be a worse one than the user's.
# - «Видео» → «+» → «Привязать папку (iTorrent)»: a folder of another app is shown in place, nothing is copied.
#   Only its folders and the videos downloaded to the end show (no holes in the file, nothing written in the last
#   half minute); pull down to refresh. The settings of its videos are kept under «linked:<folder>/…», videos are not
#   moved inside it, the next episode is only a downloaded one. A swipe unlinks it.
import pathlib


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


here = pathlib.Path(__file__).resolve().parent
hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")

# --- the voice
a = s.index("/// The sentences are read by the voice of the dictionary settings (tts.voice), else by the best Japanese voice.")
b = s.index("enum GrammarText {", a)
s = s[:a] + '''/// The sentences are read by the voice of «Настройки → Озвучка».
enum GrammarVoice {
    static func speak(_ text: String) {
        SatoriVoice.speak(text)
    }
}

''' + s[b:]
s = once(s, '''    @AppStorage("ykReaderBackdrop") private var readerBackdrop = true
    /// words imported from Anki decks''', '''    @AppStorage("ykReaderBackdrop") private var readerBackdrop = true
    @AppStorage(SatoriVoice.key) private var voice = ""
    /// words imported from Anki decks''', "settings voice state")
s = once(s, '''            } header: {
                Text("Внешний вид")
            }
''', '''            } header: {
                Text("Внешний вид")
            }

            Section {
                Picker("Голос", selection: $voice) {
                    Text("Как в настройках iOS").tag("")
                    ForEach(SatoriVoice.voices, id: \\.id) { item in
                        Text(SatoriVoice.label(item)).tag(item.id)
                    }
                }
                Button("Прослушать") {
                    SatoriVoice.speak("日本語の勉強は楽しいです。")
                }
            } header: {
                Text("Озвучка")
            }
''', "settings voice section")
s = once(s, '''        .onChange(of: accent) { value in
            config.set("general.accent", value)
        }
''', '''        .onChange(of: accent) { value in
            config.set("general.accent", value)
        }
        // the dictionary reads with the same voice
        .onChange(of: voice) { value in
            if let item = SatoriVoice.voices.first(where: { $0.id == value }) {
                let saved: [String: Any] = ["id": item.id, "name": item.name, "quality": item.quality]
                config.set("tts.voice", saved)
            } else {
                config.set("tts.voice", NSNull())
            }
        }
''', "settings voice change")

# --- the folders of other apps
s = once(s, '''        guard full.hasPrefix(root + "/") else { return name }''',
         '''        guard full.hasPrefix(root + "/") else { return LinkedFolders.key(for: url) ?? name }''', "video key")
s = once(s, '''        let urls = (try? FileManager.default.contentsOfDirectory(
            at: folder, includingPropertiesForKeys: [.isDirectoryKey], options: [.skipsHiddenFiles])) ?? []
''', '''        let linked = LinkedFolders.root(of: folder) != nil
        let urls = (try? FileManager.default.contentsOfDirectory(
            at: folder, includingPropertiesForKeys: [.isDirectoryKey], options: [.skipsHiddenFiles])) ?? []
''', "reload linked")
s = once(s, '''        .filter { $0.isFolder || !VideoLibraryStore.isSubtitle($0.url.lastPathComponent) }
''', '''        .filter { $0.isFolder || !VideoLibraryStore.isSubtitle($0.url.lastPathComponent) }
        // a folder of another app (iTorrent): its folders and the videos downloaded to the end
        .filter { item in
            !linked || item.isFolder
                || (VideoLibraryStore.isVideo(item.url.lastPathComponent) && LinkedFolders.isComplete(item.url))
        }
''', "reload filter")
s = once(s, '''    private var moveTargets: [VideoMoveTarget] {
        var result: [VideoMoveTarget] = []
''', '''    private var moveTargets: [VideoMoveTarget] {
        var result: [VideoMoveTarget] = []
        // the files of another app stay where it keeps them
        if LinkedFolders.root(of: library.folder) != nil {
            return result
        }
''', "move targets")
s = once(s, '''            .filter { VideoLibraryStore.isVideo($0.lastPathComponent) }
''', '''            .filter { VideoLibraryStore.isVideo($0.lastPathComponent)
                && (LinkedFolders.root(of: $0) == nil || LinkedFolders.isComplete($0)) }
''', "next episode")
s = once(s, '''    @State private var wordsFolder: URL? = nil
''', '''    @State private var wordsFolder: URL? = nil
    @State private var linkedFolders: [URL] = []
''', "list linked state")
s = once(s, '''            if isRootFolder {
                YouTubeRecentSection(items: $youTubeItems)
            }
''', '''            if isRootFolder {
                YouTubeRecentSection(items: $youTubeItems)
                if !linkedFolders.isEmpty {
                    Section {
                        ForEach(linkedFolders, id: \\.self) { url in
                            NavigationLink(destination: NativeVideoListView(folder: url, title: url.lastPathComponent)) {
                                Label(url.lastPathComponent, systemImage: "link")
                            }
                            .swipeActions(edge: .trailing, allowsFullSwipe: false) {
                                Button(role: .destructive) {
                                    LinkedFolders.remove(url)
                                    withAnimation {
                                        linkedFolders = LinkedFolders.all()
                                    }
                                } label: {
                                    Label("Отвязать", systemImage: "minus.circle")
                                }
                            }
                        }
                    } header: {
                        Text("Папки других приложений")
                    }
                }
            }
''', "list linked rows")
s = once(s, '''                    Button {
                        showNewFolder = true
                    } label: {
                        Label("Новая папка", systemImage: "folder.badge.plus")
                    }
''', '''                    Button {
                        showNewFolder = true
                    } label: {
                        Label("Новая папка", systemImage: "folder.badge.plus")
                    }
                    if isRootFolder {
                        Button {
                            FolderPick.present({ url in
                                if LinkedFolders.add(url) {
                                    withAnimation {
                                        linkedFolders = LinkedFolders.all()
                                    }
                                }
                            })
                        } label: {
                            Label("Привязать папку (iTorrent)", systemImage: "link")
                        }
                    }
''', "list link menu")
s = once(s, '''        .animation(.default, value: library.items.map { $0.id })
        // the confirmation sits on its own view''', '''        .refreshable {
            library.reload()
        }
        .animation(.default, value: library.items.map { $0.id })
        // the confirmation sits on its own view''', "list refresh")
s = once(s, '''            library.reload()
            youTubeItems = YouTubeHistory.load()
''', '''            library.reload()
            youTubeItems = YouTubeHistory.load()
            linkedFolders = LinkedFolders.all()
''', "list linked load")

s = s.rstrip("\n") + "\n" + (here / "v210-voice-linked.swift").read_text(encoding="utf-8")
hv.write_text(s, encoding="utf-8")
print("v2.10 voice and linked folders applied")
