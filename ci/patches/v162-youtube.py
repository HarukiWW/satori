# v1.62: YouTube videos in the app. A link (the "YouTube" button of the video list) opens the official YouTube player
# with the Japanese captions of YouTube under it: word lookup, mining (also the mining queue), line buttons, double
# tap, swipe seeking, subtitle delay, saved position, watching statistics. The code is v162-youtube.swift, added to
# HelpView.swift; the videos opened before are listed at the top of the video list.
import pathlib


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


here = pathlib.Path(__file__).resolve().parent
hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")

s = once(s, "import SwiftUI\n", "import SwiftUI\nimport WebKit\n", "import WebKit")
s = s.rstrip("\n") + "\n" + (here / "v162-youtube.swift").read_text(encoding="utf-8")

s = once(s, "    @State private var showQueue = false\n", """    @State private var showQueue = false
    @State private var showYouTube = false
    @State private var youTubeID: String? = nil
    @State private var youTubeItems: [YouTubeItem] = []
""", "youtube state")
s = once(s, """        List {
            if library.items.isEmpty {
                Text("Пусто. Нажмите «+», чтобы добавить видео.")
""", """        List {
            if isRootFolder {
                YouTubeRecentSection(items: $youTubeItems)
            }
            if library.items.isEmpty {
                Text("Пусто. Нажмите «+», чтобы добавить видео.")
""", "recent section")
s = once(s, """                    Image(systemName: "tray.full")
                }
            }
        }
        .sheet(isPresented: $showKey) {
""", """                    Image(systemName: "tray.full")
                }
            }
            ToolbarItem(placement: .navigationBarTrailing) {
                Button {
                    showYouTube = true
                } label: {
                    Image(systemName: "play.rectangle")
                }
            }
        }
        .sheet(isPresented: $showKey) {
""", "youtube button")
s = once(s, """        .sheet(isPresented: $showQueue) {
            MiningQueueView(video: nil)
        }
""", """        .sheet(isPresented: $showQueue) {
            MiningQueueView(video: nil)
        }
        .sheet(isPresented: $showYouTube) {
            YouTubeLinkSheet { id in
                // the sheet closes first
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.6) {
                    youTubeID = id
                }
            }
        }
        .background(
            NavigationLink(destination: youTubeDestination,
                           isActive: Binding(get: { youTubeID != nil }, set: { if !$0 { youTubeID = nil } })) {
                EmptyView()
            }
            .hidden()
        )
""", "youtube sheet")
s = once(s, """        .onAppear {
            library.reload()
        }
""", """        .onAppear {
            library.reload()
            youTubeItems = YouTubeHistory.load()
        }
""", "youtube items")
s = once(s, """    /// The folders here and, inside a folder, the folder above.
""", """    /// The top folder of the videos (the YouTube videos are listed there).
    private var isRootFolder: Bool {
        library.folder.standardizedFileURL == YomikiriMediaSchemeHandler.videosDirectory()?.standardizedFileURL
    }

    @ViewBuilder
    private var youTubeDestination: some View {
        if let id = youTubeID {
            YouTubePlayerScreen(videoID: id)
        } else {
            EmptyView()
        }
    }

    /// The folders here and, inside a folder, the folder above.
""", "youtube destination")
hv.write_text(s, encoding="utf-8")
print("v1.62 YouTube applied")
