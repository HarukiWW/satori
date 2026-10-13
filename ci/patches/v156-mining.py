# v1.56: the frame of the video goes into the note mined from the player (an empty picture field: Image, Picture,
# Screenshot, Изображение, 画像 ...; inline JPEG, AnkiMobile takes text fields only); a mining queue (switch in the player
# settings): the finished note is kept instead of opening AnkiMobile, and the queue of a video (swipe in the list) sends
# all its notes to AnkiMobile with one tap, one after another (AnkiMobile comes back after each note).
import pathlib

base = pathlib.Path("src/safari")


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


# ---------- the web view: a hook for links the page opens (empty in the Safari extension) ----------
wv = base / "Shared (iOS)/YomikiriWebView.swift"
s = wv.read_text(encoding="utf-8")
s = once(s, """                DispatchQueue.main.async {
                    // does nothing in ios action
                    openUrl(url)
                }
""", """                DispatchQueue.main.async {
                    // does nothing in ios action
                    // the video player can change an Anki note (its frame) or keep it in the mining queue (nil)
                    if let hook = yomikiriOpenLinkHook {
                        if let changed = hook(url) {
                            openUrl(changed)
                        }
                    } else {
                        openUrl(url)
                    }
                }
""", "openLink hook")
s = s.rstrip("\n") + """

/// Set by the video player of the app while it is open; nil everywhere else.
var yomikiriOpenLinkHook: ((URL) -> URL?)? = nil
"""
wv.write_text(s, encoding="utf-8")

# ---------- the app: AnkiMobile comes back after a queued note ----------
ap = base / "iOS (App)/YomikiriApp.swift"
s = ap.read_text(encoding="utf-8")
s = once(s, '        if url.host?.lowercased() == "ankireturn" {\n', '''        if url.host?.lowercased() == "ankiqueue" {
            NotificationCenter.default.post(name: Notification.Name("yomikiri.ankiQueue"), object: nil)
            return
        }
        if url.host?.lowercased() == "ankireturn" {
''', "ankiQueue url")
ap.write_text(s, encoding="utf-8")

# ---------- the player ----------
hv = base / "iOS (App)/HelpView.swift"
s = hv.read_text(encoding="utf-8")
s = once(s, '@AppStorage("ykSubsTop") private var subsTop = false',
         '@AppStorage("ykSubsTop") private var subsTop = false\n'
         '              @AppStorage("ykMiningQueue") private var miningQueueOn = false', "queue storage")
s = once(s, 'Section("Улучшение картинки") {', '''Section {
                              Toggle("Очередь майнинга", isOn: $miningQueueOn)
                          } header: {
                              Text("Майнинг")
                          } footer: {
                              Text("Кнопка ⊕ в словаре кладёт карточку в очередь серии, а не открывает AnkiMobile. Очередь — свайп по серии в списке видео.")
                          }
                          Section("Улучшение картинки") {''', "queue toggle")
s = once(s, "        showLookup = true\n    }\n}\n\n/// Text subtitles read straight from the file",
         "        showLookup = true\n        prepareMining()\n    }\n\n"
         "    /// The frame of this moment for the note, and the queue when it is on.\n"
         "    private func prepareMining() {\n"
         "        MiningFrame.jpegBase64 = nil\n"
         "        let video = url.lastPathComponent\n"
         "        yomikiriOpenLinkHook = { link in\n"
         "            guard MiningFrame.isAddNote(link) else { return link }\n"
         "            let withFrame = MiningFrame.attach(to: link)\n"
         "            if UserDefaults.standard.bool(forKey: \"ykMiningQueue\") {\n"
         "                MiningQueue.shared.add(withFrame, video: video)\n"
         "                UINotificationFeedbackGenerator().notificationOccurred(.success)\n"
         "                return nil\n"
         "            }\n"
         "            return withFrame\n"
         "        }\n"
         "        guard let player = coordinator.playerLayer?.player else { return }\n"
         "        Task { @MainActor in\n"
         "            if let frame = await player.thumbnailImageAtCurrentTime() {\n"
         "                MiningFrame.capture(frame)\n"
         "            }\n"
         "        }\n"
         "    }\n}\n\n/// Text subtitles read straight from the file", "prepare mining")
s = once(s, '            CrashTrail.mark("плеер: закрытие")\n',
         '            CrashTrail.mark("плеер: закрытие")\n            yomikiriOpenLinkHook = nil\n            MiningFrame.jpegBase64 = nil\n', "clear hook")

# ---------- the list: the queue of a video ----------
s = once(s, """                    .swipeActions(edge: .trailing, allowsFullSwipe: false) {
                        Button(role: .destructive) {
                            pendingDelete = item
                        } label: {
                            Label("Удалить", systemImage: "trash")
                        }
                    }
""", """                    .swipeActions(edge: .trailing, allowsFullSwipe: false) {
                        Button(role: .destructive) {
                            pendingDelete = item
                        } label: {
                            Label("Удалить", systemImage: "trash")
                        }
                        if !item.isFolder {
                            Button {
                                queueVideo = item.url.lastPathComponent
                            } label: {
                                Label("Очередь", systemImage: "tray.full")
                            }
                            .tint(.blue)
                        }
                    }
""", "queue swipe")
s = once(s, "    @State private var nextVideo: URL? = nil\n",
         "    @State private var nextVideo: URL? = nil\n    @State private var queueVideo: String? = nil\n", "queue state")
s = once(s, '        .onReceive(NotificationCenter.default.publisher(for: Notification.Name("yomikiri.playNext"))) { note in\n',
         '''        .sheet(isPresented: Binding(get: { queueVideo != nil }, set: { if !$0 { queueVideo = nil } })) {
            if let video = queueVideo {
                MiningQueueView(video: video)
            }
        }
        .onReceive(NotificationCenter.default.publisher(for: Notification.Name("yomikiri.playNext"))) { note in
''', "queue sheet")

s = s.rstrip("\n") + r'''

/// Strict query encoding: base64 "+" must not turn into a space.
private let ankiQueryAllowed = CharacterSet(charactersIn: "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-._~")

/// The frame of the video when the dictionary opened from the player; it goes into an empty picture field of the note.
enum MiningFrame {
    static var jpegBase64: String?

    static func capture(_ image: CGImage) {
        let full = UIImage(cgImage: image)
        let scale = min(1, 640 / max(full.size.width, 1))
        let size = CGSize(width: (full.size.width * scale).rounded(), height: (full.size.height * scale).rounded())
        let format = UIGraphicsImageRendererFormat()
        format.scale = 1
        let resized = UIGraphicsImageRenderer(size: size, format: format).image { _ in
            full.draw(in: CGRect(origin: .zero, size: size))
        }
        jpegBase64 = resized.jpegData(compressionQuality: 0.6)?.base64EncodedString()
    }

    private static let pictureNames = ["image", "picture", "screenshot", "скрин", "изображ", "картин", "画像"]

    static func isAddNote(_ url: URL) -> Bool {
        url.scheme == "anki" && url.host == "x-callback-url" && url.path == "/addnote"
    }

    /// The note with the frame in its first empty picture field (an inline image: AnkiMobile takes text only).
    static func attach(to url: URL) -> URL {
        guard let frame = jpegBase64, isAddNote(url),
              var parts = URLComponents(url: url, resolvingAgainstBaseURL: false),
              var items = parts.percentEncodedQueryItems,
              let index = items.firstIndex(where: { item in
                  guard item.name.hasPrefix("fld"), (item.value ?? "").isEmpty else { return false }
                  let field = item.name.dropFirst(3).lowercased()
                  return pictureNames.contains { field.contains($0) }
              }) else { return url }
        let html = "<img src=\"data:image/jpeg;base64," + frame + "\">"
        items[index].value = html.addingPercentEncoding(withAllowedCharacters: ankiQueryAllowed)
        parts.percentEncodedQueryItems = items
        return parts.url ?? url
    }

    /// AnkiMobile comes back to the queue after the note.
    static func returningToQueue(_ url: URL) -> URL {
        guard var parts = URLComponents(url: url, resolvingAgainstBaseURL: false) else { return url }
        var items = (parts.percentEncodedQueryItems ?? []).filter { $0.name != "x-success" }
        items.append(URLQueryItem(name: "x-success",
                                  value: "yomikiri://ankiQueue".addingPercentEncoding(withAllowedCharacters: ankiQueryAllowed)))
        parts.percentEncodedQueryItems = items
        return parts.url ?? url
    }
}

/// Notes mined from the player and kept per video; sent to AnkiMobile with one tap, one after another.
@MainActor
final class MiningQueue: ObservableObject {
    static let shared = MiningQueue()

    struct Entry: Codable, Identifiable {
        var id = UUID()
        let video: String
        let word: String
        let sentence: String
        let url: String
    }

    @Published private(set) var entries: [Entry] = []
    /// notes on their way to AnkiMobile
    @Published private(set) var sending: [Entry] = []
    private let key = "miningQueue.v1"
    private var observer: NSObjectProtocol?

    init() {
        if let data = UserDefaults.standard.data(forKey: key),
           let saved = try? JSONDecoder().decode([Entry].self, from: data) {
            entries = saved
        }
        observer = NotificationCenter.default.addObserver(forName: Notification.Name("yomikiri.ankiQueue"),
                                                          object: nil, queue: .main) { [weak self] _ in
            Task { @MainActor in
                self?.sentOne()
            }
        }
    }

    func add(_ url: URL, video: String) {
        let items = URLComponents(url: url, resolvingAgainstBaseURL: false)?.queryItems ?? []
        func field(_ names: [String]) -> String {
            let value = items.first { item in
                names.contains { item.name.lowercased() == "fld" + $0 }
            }?.value ?? ""
            return value.replacingOccurrences(of: "<[^>]+>", with: "", options: .regularExpression)
        }
        entries.append(Entry(video: video, word: field(["word", "expression", "vocab", "слово"]),
                             sentence: field(["sentence", "предложение"]), url: url.absoluteString))
        save()
    }

    func remove(_ entry: Entry) {
        entries.removeAll { $0.id == entry.id }
        save()
    }

    func sendAll(video: String) {
        sending = entries.filter { $0.video == video }
        sendNext()
    }

    private func sendNext() {
        guard let next = sending.first, let url = URL(string: next.url) else {
            sending = []
            return
        }
        UIApplication.shared.open(MiningFrame.returningToQueue(url))
    }

    private func sentOne() {
        guard let done = sending.first else { return }
        sending.removeFirst()
        entries.removeAll { $0.id == done.id }
        save()
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.4) {
            self.sendNext()
        }
    }

    private func save() {
        if let data = try? JSONEncoder().encode(entries) {
            UserDefaults.standard.set(data, forKey: key)
        }
    }
}

@available(iOS 16.0, *)
struct MiningQueueView: View {
    let video: String
    @ObservedObject private var queue = MiningQueue.shared
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationView {
            List {
                let entries = queue.entries.filter { $0.video == video }
                if entries.isEmpty {
                    Text("Очередь пуста. Включите «Очередь майнинга» в настройках плеера и добавляйте слова кнопкой ⊕ в словаре.")
                        .foregroundColor(.secondary)
                }
                ForEach(entries) { entry in
                    VStack(alignment: .leading, spacing: 4) {
                        Text(entry.word.isEmpty ? "—" : entry.word)
                            .font(.system(size: 20))
                        if !entry.sentence.isEmpty {
                            Text(entry.sentence)
                                .font(.footnote)
                                .foregroundColor(.secondary)
                                .lineLimit(2)
                        }
                    }
                    .swipeActions {
                        Button(role: .destructive) {
                            queue.remove(entry)
                        } label: {
                            Label("Убрать", systemImage: "trash")
                        }
                    }
                }
            }
            .navigationTitle("Очередь")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Закрыть") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button(queue.sending.isEmpty ? "Добавить все" : "Добавляю… " + String(queue.sending.count)) {
                        queue.sendAll(video: video)
                    }
                    .disabled(!queue.sending.isEmpty || !queue.entries.contains { $0.video == video })
                }
            }
        }
    }
}
'''
# the swipe label of v1.54 was one long expression the compiler could not type-check in time: built step by step now
s = once(s, """            let delta = swipeTarget - start
            Text((delta < 0 ? "« " : "» ") + clock(swipeTarget) + "  (" + (delta < 0 ? "−" : "+") + clock(abs(delta)) + ")")
""", """            Text(swipeLabel(start: start))
""", "swipe label")
s = once(s, """    @ViewBuilder
    private var swipeOverlay: some View {
""", """    private func swipeLabel(start: Double) -> String {
        let delta: Double = swipeTarget - start
        let arrow: String = delta < 0 ? "« " : "» "
        let sign: String = delta < 0 ? "−" : "+"
        let target: String = clock(swipeTarget)
        let shift: String = clock(abs(delta))
        return arrow + target + "  (" + sign + shift + ")"
    }

    @ViewBuilder
    private var swipeOverlay: some View {
""", "swipe label func")
hv.write_text(s, encoding="utf-8")
print("v1.56 mining applied")
