# v2.17: the best free translator, only ready notes leave the mining queue.
# - The sentences are translated by Google's page translator (translate-pa, the one of Chrome): of the free Japanese →
#   Russian ones tried (Google gtx and translate-pa, Yandex, DeepL, Microsoft Edge) it got the meaning right most
#   often at ~0.45 s; Yandex is faster (~0.25 s) but missed the meaning in 5 of 16 sentences, DeepL and Microsoft's
#   free endpoints do not answer any more. The old Google endpoint (gtx, often "429 Too Many Requests") is the
#   fallback. The web (translate.ts) and the mining queue (Translator) use the same.
# - A note of the mining queue waits until it is ready: the translation of its sentence, the sound of its line (the
#   queue remembers the line and cuts it again from the video when the note went without it), the check of its word
#   audio when the dictionary could not check it (JapanesePod101 answers a word it has not with an "audio not
#   available" clip). While the app is open, the queue repairs such notes in the background (at the start, every
#   minute, on the return to the app, after a new note); «Добавить все», «Выбрать» and the swipe send ready notes
#   only, a waiting note shows what it waits for.
import pathlib


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


here = pathlib.Path(__file__).resolve().parent
hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")

# --- MiningFrame: the line of the clip goes with it, the sentence audio field is known to the queue
s = once(s, '''            if jpegBase64 == nil {
                audioBase64 = nil
                audioFile = nil
            }''', '''            if jpegBase64 == nil {
                audioBase64 = nil
                audioFile = nil
                clip = nil
            }''', "clip reset")
s = once(s, "    private static func isSentenceAudio(_ field: String) -> Bool {",
         "    static func isSentenceAudio(_ field: String) -> Bool {", "sentence audio visible")

# the player: the line on screen
s = once(s, '''            let stream = (playing as? FFmpegAssetTrack)?.trackID
            let language = playing?.languageCode
            Task.detached(priority: .userInitiated) {''', '''            let stream = (playing as? FFmpegAssetTrack)?.trackID
            let language = playing?.languageCode
            MiningFrame.clip = MiningFrame.Clip(video: VideoKey.path(file), from: from, to: to, stream: stream,
                                                language: language)
            Task.detached(priority: .userInitiated) {''', "player clip")
# the list of unknown words: the clearest line
s = once(s, '''        MiningFrame.jpegBase64 = nil
        if let frame = made.0 {
            MiningFrame.capture(frame)
        }
        MiningFrame.audioFile = made.1''', '''        MiningFrame.jpegBase64 = nil
        if let frame = made.0 {
            MiningFrame.capture(frame)
        }
        MiningFrame.audioFile = made.1
        MiningFrame.clip = MiningFrame.Clip(video: VideoKey.path(video), from: from, to: to)''', "list clip")

# --- MiningQueue: the line of a note, the repair, ready notes only
s = once(s, '''        /// the sound of the line, next to the frame (its field holds audioMarker)
        var audio: String? = nil
    }''', '''        /// the sound of the line, next to the frame (its field holds audioMarker)
        var audio: String? = nil
        /// the line its sound is cut from (nil: none, or it cannot be cut any more)
        var clip: MiningFrame.Clip? = nil
    }''', "entry clip")
s = once(s, '''    /// the note opened in AnkiMobile, until its x-success callback comes back
    private var awaiting: UUID?
''', '''    /// the note opened in AnkiMobile, until its x-success callback comes back
    private var awaiting: UUID?
    private var repairing = false
''', "repairing flag")
s = once(s, '''            Task { @MainActor in
                self?.checkCancelled()
            }''', '''            Task { @MainActor in
                self?.checkCancelled()
                await self?.repair()
            }''', "repair on return")
s = once(s, '''                          sentence: field(["sentence", "предложение"]), url: url.absoluteString)
        MiningQueue.detachFrame(&entry)
        entries.append(entry)
        save()
    }''', '''                          sentence: field(["sentence", "предложение"]), url: url.absoluteString)
        entry.clip = MiningFrame.clip
        MiningQueue.detachFrame(&entry)
        entries.append(entry)
        save()
        // the sound of the line may still be being cut, the translation may have failed: the queue looks again
        Task {
            try? await Task.sleep(nanoseconds: 3_000_000_000)
            await self.repair()
        }
    }''', "repair after add")
s = once(s, '''    func sendAll(video: String?) {
        sending = entries.filter { video == nil || $0.video == video }
        sendNext()
    }

    /// The chosen notes only, in the order of the queue.
    func send(_ ids: Set<UUID>) {
        sending = entries.filter { ids.contains($0.id) }
        sendNext()
    }''', '''    func sendAll(video: String?) {
        let contents = MiningReady.fieldContents()
        // a note that is not ready stays in the queue
        sending = entries.filter { (video == nil || $0.video == video) && MiningReady.needs($0, contents).isEmpty }
        sendNext()
    }

    /// The chosen notes only, in the order of the queue.
    func send(_ ids: Set<UUID>) {
        let contents = MiningReady.fieldContents()
        sending = entries.filter { ids.contains($0.id) && MiningReady.needs($0, contents).isEmpty }
        sendNext()
    }''', "ready only")

# --- the queue: what a note waits for
s = once(s, '''            List(selection: $chosen) {
                let entries = queue.entries.filter { video == nil || $0.video == video }
                if entries.isEmpty {''', '''            List(selection: $chosen) {
                let entries = queue.entries.filter { video == nil || $0.video == video }
                let contents = MiningReady.fieldContents()
                if entries.isEmpty {''', "queue contents")
s = once(s, '''                ForEach(entries) { entry in
                    VStack(alignment: .leading, spacing: 4) {
                        Text(entry.word.isEmpty ? "—" : entry.word)
                            .font(.system(size: 20))''', '''                ForEach(entries) { entry in
                    let waiting = MiningReady.needs(entry, contents)
                    VStack(alignment: .leading, spacing: 4) {
                        Text(entry.word.isEmpty ? "—" : entry.word)
                            .font(.system(size: 20))''', "row waiting")
s = once(s, '''                        if video == nil {
                            Text((entry.video as NSString).deletingPathExtension)
                                .font(.caption2)
                                .foregroundColor(.secondary)
                                .lineLimit(1)
                        }
                    }
                    .swipeActions {''', '''                        if video == nil {
                            Text((entry.video as NSString).deletingPathExtension)
                                .font(.caption2)
                                .foregroundColor(.secondary)
                                .lineLimit(1)
                        }
                        if !waiting.isEmpty {
                            let what: String = waiting.map { $0.rawValue }.joined(separator: ", ")
                            HStack(spacing: 6) {
                                ProgressView()
                                    .controlSize(.mini)
                                Text("Готовится: " + what)
                            }
                            .font(.caption)
                            .foregroundColor(.orange)
                            .transition(.opacity)
                        }
                    }
                    .animation(.easeInOut(duration: 0.3), value: waiting.isEmpty)
                    .swipeActions {''', "row status")
s = once(s, '''                        .tint(.blue)
                        .disabled(!queue.sending.isEmpty)
                    }
                    .tag(entry.id)''', '''                        .tint(.blue)
                        .disabled(!queue.sending.isEmpty || !waiting.isEmpty)
                    }
                    .tag(entry.id)''', "row swipe")
s = once(s, '''                        Button(queue.sending.isEmpty ? "Добавить все" : "Добавляю… " + String(queue.sending.count)) {
                            queue.sendAll(video: video)
                        }
                        .disabled(!queue.sending.isEmpty || !queue.entries.contains { video == nil || $0.video == video })''',
         '''                        Button(sendTitle) {
                            queue.sendAll(video: video)
                        }
                        .disabled(!queue.sending.isEmpty || readyCount == 0)''', "send all ready")
s = once(s, '''    @State private var choosing = false
    @State private var chosen = Set<UUID>()

    var body: some View {
        NavigationView {
            List(selection: $chosen) {''', '''    @State private var choosing = false
    @State private var chosen = Set<UUID>()

    /// The notes of this list that can go to AnkiMobile now.
    private var readyCount: Int {
        let contents = MiningReady.fieldContents()
        return queue.entries.filter { entry in
            (video == nil || entry.video == video) && MiningReady.needs(entry, contents).isEmpty
        }.count
    }

    private var sendTitle: String {
        if !queue.sending.isEmpty {
            return "Добавляю… " + String(queue.sending.count)
        }
        let all = queue.entries.filter { video == nil || $0.video == video }.count
        return readyCount < all ? "Добавить готовые" : "Добавить все"
    }

    var body: some View {
        NavigationView {
            List(selection: $chosen) {''', "queue counts")

s = s.rstrip("\n") + "\n" + (here / "v217-queue.swift").read_text(encoding="utf-8")
hv.write_text(s, encoding="utf-8")

# --- the repair while the app is open
mv = pathlib.Path("src/safari/iOS (App)/MainView.swift")
m = mv.read_text(encoding="utf-8")
m = once(m, '''        .task(id: backupInterval) {''', '''        .task {
            // the notes of the mining queue that are not ready get their translation and sound
            while !Task.isCancelled {
                if UIApplication.shared.applicationState == .active {
                    await MiningQueue.shared.repair()
                }
                try? await Task.sleep(nanoseconds: 60_000_000_000)
            }
        }
        .task(id: backupInterval) {''', "main repair")
mv.write_text(m, encoding="utf-8")

# --- the web: the page translator first
tr = pathlib.Path("src/main/src/platform/common/translate.ts")
t = tr.read_text(encoding="utf-8")
t = once(t, '''const translationCache: Record<string, TranslateResult> = {};
''', '''const translationCache: Record<string, TranslateResult> = {};

const PAGE_TRANSLATE_URL = "https://translate-pa.googleapis.com/v1/translateHtml";
/** The public key of Chrome's page translator. */
const PAGE_TRANSLATE_KEY = "AIzaSyATBXajvzQLTDHEQbcpq0Ihe0vWDHmO520";

/**
 * Google's page translator (the one of Chrome): of the free Japanese → Russian translators tried for Satori 2.17 it
 * gets the meaning right most often (~0.45 s). The same is in the app (Translator, the mining queue).
 */
async function pageTranslation(text: string, targetLang: string): Promise<string> {
  // HTML in and out: the sentence's own & < > are escaped
  const html = text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const response = await fetch(PAGE_TRANSLATE_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json+protobuf",
      "X-Goog-API-Key": PAGE_TRANSLATE_KEY,
    },
    body: JSON.stringify([[[html], "ja", targetLang], "te_lib"]),
  });
  if (response.status !== 200) {
    throw new Error("translate-pa: " + response.status);
  }
  const body = (await response.json()) as string[][];
  return body[0][0]
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&amp;/g, "&")
    .trim();
}
''', "page translator")
t = once(t, '''  const targetLang = "ru";
  const encodedText = encodeURIComponent(text);
''', '''  const targetLang = "ru";
  try {
    const translated = await pageTranslation(text, targetLang);
    if (translated !== "") {
      const result = { translated };
      translationCache[text] = result;
      return result;
    }
  } catch (err) {
    // the old endpoint below answers when the page translator does not
    console.warn(err);
  }
  const encodedText = encodeURIComponent(text);
''', "page first")
tr.write_text(t, encoding="utf-8")

# --- the word audio the dictionary could not check is marked: the queue checks it before the note goes
ab = pathlib.Path("src/main/src/lib/anki/ankiBuilder.ts")
a = ab.read_text(encoding="utf-8")
a = once(a, '''    console.warn("Could not check JapanesePod101 audio:", err);
  }''', '''    console.warn("Could not check JapanesePod101 audio:", err);
    // the app's mining queue checks it again (MiningReady.unchecked)
    return JPOD101_URL + query + "&unchecked=1&fakePath=audio.mp3";
  }''', "jpod101 unchecked")
ab.write_text(a, encoding="utf-8")
print("v2.17 translator and queue applied")
