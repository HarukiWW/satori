# v1.81: the sound of the line becomes a real sound of the card. The field gets a link to the clip
# (http://localhost:47611/<id>.m4a, served by Satori on this phone only); AnkiMobile downloads a field that is a link
# to an audio file into its media and puts a [sound:] there, so the card plays it by itself after the word audio.
# The clip stays reachable the ~30 s iOS gives after Satori opens AnkiMobile; the mining queue starts the server
# before each note. Before this the sound went into the field as an inline <audio> player, which does not play by
# itself. The code is v181-audio.swift.
import pathlib


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


here = pathlib.Path(__file__).resolve().parent
hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")

s = once(s, "import Security\n", "import Security\nimport Network\n", "import network")
s = once(s, '''            if jpegBase64 == nil {
                audioBase64 = nil
            }
''', '''            if jpegBase64 == nil {
                audioBase64 = nil
                audioFile = nil
            }
''', "reset clip")
s = once(s, '''    /// the sound of the line (m4a), for the sentence audio field
    static var audioBase64: String?
''', '''    /// the sound of the line (m4a), for the sentence audio field
    static var audioBase64: String?
    /// the clip of the line in ClipFiles, for the sentence audio field (as a link AnkiMobile downloads)
    static var audioFile: String?
''', "clip state")
s = once(s, '''        if let sound = audioBase64, let index = emptyField(isSentenceAudio) {
            let html = audioPrefix + sound + "\\"></audio>"
            items[index].value = html.addingPercentEncoding(withAllowedCharacters: ankiQueryAllowed)
        }
''', '''        if let name = audioFile, let index = emptyField(isSentenceAudio) {
            items[index].value = ClipFiles.link(name).addingPercentEncoding(withAllowedCharacters: ankiQueryAllowed)
        }
''', "attach link")
s = once(s, '''            Task.detached(priority: .userInitiated) {
                let sound = MiningAudio.clip(url: file, from: from, to: to)?.base64EncodedString()
                await MainActor.run {
                    MiningFrame.audioBase64 = sound
                }
            }
''', '''            Task.detached(priority: .userInitiated) {
                let name = MiningAudio.clip(url: file, from: from, to: to).flatMap { ClipFiles.keep($0) }
                await MainActor.run {
                    MiningFrame.audioFile = name
                    if name != nil {
                        ClipServer.shared.start()
                    }
                }
            }
''', "player clip file")
s = once(s, '''        awaiting = next.id
        UIApplication.shared.open(MiningFrame.returningToQueue(url))
''', '''        awaiting = next.id
        // AnkiMobile downloads the sound of the line from Satori
        ClipServer.shared.start()
        UIApplication.shared.open(MiningFrame.returningToQueue(url))
''', "queue serves clips")
s = s.rstrip("\n") + "\n" + (here / "v181-audio.swift").read_text(encoding="utf-8")
hv.write_text(s, encoding="utf-8")
print("v1.81 audio applied")
