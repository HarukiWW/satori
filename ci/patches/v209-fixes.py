# v2.09: fixes.
# - The examples of the grammar decks mark only the grammar, with its own conjugation: 押すと → と, 降るそうです →
#   そうです, ふりを → ふりをして (the decks in ci/assets/grammar; 53 marks).
# - A grammar card no more ends in a hard cut above the answer buttons: it fades out there and scrolls clear of them.
# - «О приложении» is back, native: the version, the code, the data and the libraries, the third-party licences.
# - A word queued from a list of unknown words leaves the list also when the note keeps another written form of it
#   (いたずら in the subtitles, 悪戯[いたずら] in the note): the queue gives every short field of its notes, without
#   HTML and furigana, and the kana of the furigana.
# - The grammar cards are read by Apple's own Japanese voices only (the best one installed, Kyoko first among equals):
#   the first voice of the list was an Eloquence one (Eddy, Flo, Grandma…), which sounds robotic.
import pathlib


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


here = pathlib.Path(__file__).resolve().parent
hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")

# --- the card fades out above the answers
s = once(s, '''                ScrollView {
                    face(point)
                        .id(point.id)
                        .transition(.asymmetric(insertion: .move(edge: .trailing).combined(with: .opacity),
                                                removal: .opacity))
                }
                .contentShape(Rectangle())''', '''                ScrollView {
                    face(point)
                        .padding(.bottom, 28)
                        .id(point.id)
                        .transition(.asymmetric(insertion: .move(edge: .trailing).combined(with: .opacity),
                                                removal: .opacity))
                }
                .mask(
                    LinearGradient(stops: [.init(color: .black, location: 0), .init(color: .black, location: 0.9),
                                           .init(color: .clear, location: 1)],
                                   startPoint: .top, endPoint: .bottom)
                )
                .contentShape(Rectangle())''', "card fade")

# --- Apple's voices for the grammar
s = once(s, '''    private static func chosen() -> TTSVoice? {
        if let json = try? Storage.config.get(), let data = json.data(using: .utf8),
           let config = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any],
           let voice = config["tts.voice"] as? [String: Any], let id = voice["id"] as? String {
            return TTSVoice(id: id, name: "", quality: 0)
        }
        return japaneseTtsVoices().max { $0.quality < $1.quality }
    }''', '''    /// Apple's own Japanese voices, the best quality installed (premium, enhanced, then the default one), Kyoko
    /// first among equals; nil (the system's Japanese voice) when there is none.
    private static func chosen() -> TTSVoice? {
        let apple = japaneseTtsVoices().filter { !$0.id.lowercased().contains("eloquence") }
        return apple.max { a, b in
            if a.quality != b.quality {
                return a.quality < b.quality
            }
            return rank(a) < rank(b)
        }
    }

    private static func rank(_ voice: TTSVoice) -> Int {
        let name = voice.name.lowercased()
        if name.contains("kyoko") {
            return 2
        }
        return name.contains("o-ren") || name.contains("otoya") || name.contains("hattori") ? 1 : 0
    }''', "grammar voice")

# --- «О приложении» in the settings
s = once(s, '''            Section {
                NavigationLink(destination: DiagnosticsView()) {''', '''            Section {
                NavigationLink(destination: AboutView()) {
                    Text("О приложении")
                }
            }

            Section {
                NavigationLink(destination: DiagnosticsView()) {''', "about row")

# --- the words of the queue for the lists, the dictionary and the highlight
old = "MiningQueue.shared.entries.map { MiningQueue.statsWord(of: $0.url) }"
assert s.count(old) == 5, "queue hooks: " + str(s.count(old))
s = s.replace(old, "MiningQueue.queuedWords()")

s = s.rstrip("\n") + "\n" + (here / "v209-fixes.swift").read_text(encoding="utf-8")
hv.write_text(s, encoding="utf-8")
print("v2.09 fixes applied")
