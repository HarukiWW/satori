# v2.21: the word audio of JapanesePod101 is downloaded ahead, onto the phone.
# - JapanesePod101 answers slowly (1.7 s a word as a rule, up to 9 s, and that is before the redirect to its CDN): the
#   package could not wait for 30 words at once («Не скачался звук с assets.languagepod101.com»), and AnkiMobile spent
#   5-15 s on some notes downloading it itself. Now the mining queue downloads the word audio in the background, like
#   the clip of the line, and the note links to the file on the phone (ClipFiles, now also .mp3): the package and
#   AnkiMobile take it at once. A note waits for it («Готовится: звук слова»); after three failed tries it goes with
#   the link as before, and the package leaves out a word audio that still does not download.
import pathlib


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")

# --- the files on the phone: the word audio too
s = once(s, r'''            if name.range(of: "^[0-9A-F-]{36}\\.(m4a|jpg)$", options: .regularExpression) != nil {''',
         r'''            if name.range(of: "^[0-9A-F-]{36}\\.(m4a|jpg|mp3)$", options: .regularExpression) != nil {''',
         "serve mp3")
s = once(s, '''                let type = name.hasSuffix(".jpg") ? "image/jpeg" : "audio/mp4"''',
         '''                let type = name.hasSuffix(".jpg") ? "image/jpeg" : (name.hasSuffix(".mp3") ? "audio/mpeg" : "audio/mp4")''',
         "mp3 type")

# --- the note: its tries of the word audio
s = once(s, '''        var clip: MiningFrame.Clip? = nil
    }''', '''        var clip: MiningFrame.Clip? = nil
        /// failed downloads of the word audio (after three the note goes with the link)
        var wordTries: Int? = nil
    }''', "word tries")

# --- readiness: a word audio still on JapanesePod101
s = once(s, '''        if list.contains(where: { $0.value.contains(unchecked) }) {
            waiting.append(.wordAudio)
        }''', '''        // downloaded ahead (JapanesePod101 takes seconds a word): AnkiMobile and the package get it from the phone
        if (entry.wordTries ?? 0) < 3, list.contains(where: { $0.value.hasPrefix(jpod101) }) {
            waiting.append(.wordAudio)
        }''', "word audio need")
s = once(s, '''    /// JapanesePod101 has a recording of the word: a word it has not gets the same "audio not available" clip
    /// (52 288 bytes); nil: no answer.
    static func hasRecording(_ link: String) async -> Bool? {
        guard let url = URL(string: link) else { return false }
        guard let loaded = try? await URLSession.shared.data(from: url) else { return nil }
        guard (loaded.1 as? HTTPURLResponse)?.statusCode == 200 else { return false }
        return loaded.0.count != 52288 && loaded.0.count >= 2000
    }''', '''    static let jpod101 = "https://assets.languagepod101.com/dictionary/japanese/audiomp3.php"

    enum WordAudio {
        case file(Data)
        /// JapanesePod101 has no recording of the word
        case missing
        /// no answer
        case failed
    }

    /// The word audio of a JapanesePod101 link: a word it has not gets the same "audio not available" clip
    /// (52 288 bytes).
    static func wordAudio(_ link: String) async -> WordAudio {
        guard let url = URL(string: link.replacingOccurrences(of: unchecked, with: "")) else { return .missing }
        guard let loaded = try? await URLSession.shared.data(for: URLRequest(url: url, timeoutInterval: 30)) else {
            return .failed
        }
        guard (loaded.1 as? HTTPURLResponse)?.statusCode == 200 else { return .missing }
        return loaded.0.count == 52288 || loaded.0.count < 2000 ? .missing : .file(loaded.0)
    }''', "word audio download")
s = once(s, '''            var url = entry.url
            var clip = entry.clip''', '''            var url = entry.url
            var clip = entry.clip
            var tries = entry.wordTries ?? 0''', "tries var")
s = once(s, '''            if waiting.contains(.wordAudio) {
                for field in MiningReady.fields(of: url) where field.value.contains(MiningReady.unchecked) {
                    // no answer: the link stays as it was before 2.17, AnkiMobile downloads it itself
                    let found = await MiningReady.hasRecording(field.value)
                    let link = found == false ? "" : field.value.replacingOccurrences(of: MiningReady.unchecked, with: "")
                    url = MiningReady.filling(url, link) { name, _ in
                        name == field.name
                    }
                }
            }''', '''            if waiting.contains(.wordAudio) {
                for field in MiningReady.fields(of: url) where field.value.hasPrefix(MiningReady.jpod101) {
                    switch await MiningReady.wordAudio(field.value) {
                    case .file(let data):
                        if let kept = ClipFiles.keep(data, ext: "mp3") {
                            url = MiningReady.filling(url, ClipFiles.link(kept)) { fieldName, _ in
                                fieldName == field.name
                            }
                        }
                    case .missing:
                        url = MiningReady.filling(url, "") { fieldName, _ in
                            fieldName == field.name
                        }
                    case .failed:
                        tries += 1
                    }
                }
            }''', "word audio repair")
s = once(s, '''            entries[index].clip = clip''', '''            entries[index].clip = clip
            entries[index].wordTries = tries > 0 ? tries : nil''', "tries save")

# --- the package: a word audio that still does not download is left out, the package is made
s = once(s, '''                    loaded = try await URLSession.shared.data(for: URLRequest(url: url, timeoutInterval: 15))
                } catch {
                    throw MiningBatch.Failure.offline(url.host ?? link)
                }''', '''                    loaded = try await URLSession.shared.data(for: URLRequest(url: url, timeoutInterval: 30))
                } catch {
                    // the word audio the queue could not download three times: the note goes without it
                    if (url.host ?? "").contains("languagepod101") {
                        return ("", nil)
                    }
                    throw MiningBatch.Failure.offline(url.host ?? link)
                }''', "package word audio")
hv.write_text(s, encoding="utf-8")
print("v2.21 word audio applied")
