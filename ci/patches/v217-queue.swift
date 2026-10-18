
// MARK: - Satori v2.17: the translator, only ready notes leave the mining queue

/// The Russian of a Japanese sentence for the notes the mining queue repairs (the web has the same in translate.ts):
/// Google's page translator (translate-pa, the one of Chrome), the best of the free ones tried for 2.17 (~0.45 s);
/// the old endpoint (gtx) when it does not answer.
enum Translator {
    private static let key = "AIzaSyATBXajvzQLTDHEQbcpq0Ihe0vWDHmO520"

    static func translate(_ text: String) async -> String? {
        if let page = await page(text), !page.isEmpty {
            return page
        }
        return await gtx(text)
    }

    private static func page(_ text: String) async -> String? {
        guard let url = URL(string: "https://translate-pa.googleapis.com/v1/translateHtml") else { return nil }
        var request = URLRequest(url: url, timeoutInterval: 8)
        request.httpMethod = "POST"
        request.setValue("application/json+protobuf", forHTTPHeaderField: "Content-Type")
        request.setValue(key, forHTTPHeaderField: "X-Goog-API-Key")
        // HTML in and out: the sentence's own & < > are escaped
        var html = text.replacingOccurrences(of: "&", with: "&amp;")
        html = html.replacingOccurrences(of: "<", with: "&lt;").replacingOccurrences(of: ">", with: "&gt;")
        let payload: [Any] = [[[html], "ja", "ru"] as [Any], "te_lib"]
        request.httpBody = try? JSONSerialization.data(withJSONObject: payload)
        guard let loaded = try? await URLSession.shared.data(for: request),
              (loaded.1 as? HTTPURLResponse)?.statusCode == 200,
              let body = (try? JSONSerialization.jsonObject(with: loaded.0)) as? [Any],
              var translated = (body.first as? [Any])?.first as? String else { return nil }
        for (entity, letter) in [("&lt;", "<"), ("&gt;", ">"), ("&quot;", "\""), ("&#39;", "'"), ("&amp;", "&")] {
            translated = translated.replacingOccurrences(of: entity, with: letter)
        }
        return translated.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    private static func gtx(_ text: String) async -> String? {
        let base = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=ja&tl=ru&dt=t&dj=1&q="
        guard let query = text.addingPercentEncoding(withAllowedCharacters: ankiQueryAllowed),
              let url = URL(string: base + query),
              let loaded = try? await URLSession.shared.data(from: url),
              (loaded.1 as? HTTPURLResponse)?.statusCode == 200,
              let body = (try? JSONSerialization.jsonObject(with: loaded.0)) as? [String: Any],
              let sentences = body["sentences"] as? [[String: Any]] else { return nil }
        let joined = sentences.compactMap { $0["trans"] as? String }.joined()
        let trimmed = joined.trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.isEmpty ? nil : trimmed
    }
}

extension MiningFrame {
    /// The line a clip is cut from: a queued note that went without the sound of its line gets it cut again.
    struct Clip: Codable, Equatable {
        /// VideoKey.path of the video
        let video: String
        let from: Double
        let to: Double
        var stream: Int32? = nil
        var language: String? = nil
    }

    /// the line of `audioFile` (nil with it)
    static var clip: Clip? = nil
}

extension VideoKey {
    /// The video of a key of `path`; nil when it is not there any more.
    static func file(_ key: String) -> URL? {
        var found: URL? = nil
        if key.hasPrefix("linked:") {
            let rest = key.dropFirst("linked:".count)
            if let slash = rest.firstIndex(of: "/") {
                let folder = String(rest[..<slash])
                let inside = String(rest[rest.index(after: slash)...])
                found = LinkedFolders.all().first { $0.lastPathComponent == folder }?.appendingPathComponent(inside)
            }
        } else {
            found = YomikiriMediaSchemeHandler.videosDirectory()?.appendingPathComponent(key)
        }
        guard let file = found, FileManager.default.fileExists(atPath: file.path) else { return nil }
        return file
    }
}

/// What a note of the mining queue waits for before it goes to AnkiMobile: the translation of its sentence, the
/// clip of its line, the check of its word audio. A note that waits is not sent.
enum MiningReady {
    enum Need: String {
        case translation = "перевод"
        case clip = "звук реплики"
        case wordAudio = "звук слова"
    }

    /// the mark of a JapanesePod101 link the dictionary could not check (ankiBuilder.ts)
    static let unchecked = "&unchecked=1"

    /// The content of every field of the Anki template ("SentenceMeaning": "translated-sentence" …).
    static func fieldContents() -> [String: String] {
        guard let json = try? Storage.config.get(), let data = json.data(using: .utf8),
              let root = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any],
              let template = root["anki.anki_template"] as? [String: Any],
              let fields = template["fields"] as? [[String: Any]] else { return [:] }
        var contents: [String: String] = [:]
        for field in fields {
            if let name = field["name"] as? String, let content = field["content"] as? String {
                contents[name] = content
            }
        }
        return contents
    }

    /// The fields of a note: the name (after "fld") and the value as AnkiMobile gets it.
    static func fields(of url: String) -> [(name: String, value: String)] {
        let items = URLComponents(string: url)?.percentEncodedQueryItems ?? []
        return items.compactMap { item -> (name: String, value: String)? in
            let name = item.name.removingPercentEncoding ?? item.name
            guard name.hasPrefix("fld") else { return nil }
            let value = item.value.map { $0.removingPercentEncoding ?? $0 } ?? ""
            return (name: String(name.dropFirst(3)), value: value)
        }
    }

    /// The sentence of a note as the dictionary had it: without the furigana (漢字[かんじ]), cloze and spaces of Anki.
    static func plainSentence(_ sentence: String) -> String {
        var text = sentence
        if hasAnyScalar(text, of: "[") {
            text = text.replacingOccurrences(of: "\\[[^\\]]*\\]", with: "", options: .regularExpression)
        }
        if hasAnyScalar(text, of: "{") {
            text = text.replacingOccurrences(of: "\\{\\{c\\d+::|\\}\\}", with: "", options: .regularExpression)
        }
        return text.replacingOccurrences(of: " ", with: "").trimmingCharacters(in: .whitespacesAndNewlines)
    }

    /// What a note still waits for; empty: it is ready for AnkiMobile.
    static func needs(_ entry: MiningQueue.Entry, _ contents: [String: String]) -> [Need] {
        let list = MiningReady.fields(of: entry.url)
        var waiting: [Need] = []
        if list.contains(where: { contents[$0.name] == "translated-sentence" && $0.value.isEmpty }),
           !plainSentence(entry.sentence).isEmpty {
            waiting.append(.translation)
        }
        if list.contains(where: { $0.value.contains(unchecked) }) {
            waiting.append(.wordAudio)
        }
        let sounds = list.filter { MiningFrame.isSentenceAudio($0.name.lowercased()) }
        if entry.clip != nil, !sounds.isEmpty, sounds.allSatisfy({ $0.value.isEmpty }) {
            waiting.append(.clip)
        }
        return waiting
    }

    /// The note with `value` in the fields that `matches` (name, value): the first one, or every one.
    static func filling(_ url: String, _ value: String, every: Bool = false,
                        where matches: (String, String) -> Bool) -> String {
        guard var parts = URLComponents(string: url), var items = parts.percentEncodedQueryItems else { return url }
        for index in items.indices {
            let name = items[index].name.removingPercentEncoding ?? items[index].name
            let current = items[index].value.map { $0.removingPercentEncoding ?? $0 } ?? ""
            guard name.hasPrefix("fld"), matches(String(name.dropFirst(3)), current) else { continue }
            items[index].value = value.addingPercentEncoding(withAllowedCharacters: ankiQueryAllowed)
            if !every {
                break
            }
        }
        parts.percentEncodedQueryItems = items
        return parts.url?.absoluteString ?? url
    }

    /// JapanesePod101 has a recording of the word: a word it has not gets the same "audio not available" clip
    /// (52 288 bytes); nil: no answer.
    static func hasRecording(_ link: String) async -> Bool? {
        guard let url = URL(string: link) else { return false }
        guard let loaded = try? await URLSession.shared.data(from: url) else { return nil }
        guard (loaded.1 as? HTTPURLResponse)?.statusCode == 200 else { return false }
        return loaded.0.count != 52288 && loaded.0.count >= 2000
    }
}

@MainActor
extension MiningQueue {
    /// The notes that are not ready get what they lack, one after another, while the app is open (MainView, the
    /// return to the app, a new note); a clip that cannot be cut any more (the video is gone) is not waited for.
    func repair() async {
        guard !repairing, UIApplication.shared.applicationState == .active else { return }
        repairing = true
        defer { repairing = false }
        let contents = MiningReady.fieldContents()
        for id in entries.map({ $0.id }) {
            guard let entry = entries.first(where: { $0.id == id }), !sending.contains(where: { $0.id == id }) else {
                continue
            }
            let waiting = MiningReady.needs(entry, contents)
            guard !waiting.isEmpty else { continue }
            var url = entry.url
            var clip = entry.clip
            if waiting.contains(.translation),
               let translated = await Translator.translate(MiningReady.plainSentence(entry.sentence)) {
                url = MiningReady.filling(url, translated, every: true) { name, value in
                    contents[name] == "translated-sentence" && value.isEmpty
                }
            }
            if waiting.contains(.wordAudio) {
                for field in MiningReady.fields(of: url) where field.value.contains(MiningReady.unchecked) {
                    // no answer: the link stays as it was before 2.17, AnkiMobile downloads it itself
                    let found = await MiningReady.hasRecording(field.value)
                    let link = found == false ? "" : field.value.replacingOccurrences(of: MiningReady.unchecked, with: "")
                    url = MiningReady.filling(url, link) { name, _ in
                        name == field.name
                    }
                }
            }
            if waiting.contains(.clip), let source = clip {
                var name: String? = nil
                if MiningFrame.clip == source, let ready = MiningFrame.audioFile {
                    // the player has cut it meanwhile
                    name = ready
                } else if let file = VideoKey.file(source.video) {
                    name = await Task.detached(priority: .utility) {
                        MiningAudio.clip(url: file, from: source.from, to: source.to, stream: source.stream,
                                         language: source.language).flatMap { ClipFiles.keep($0) }
                    }.value
                }
                if let name {
                    url = MiningReady.filling(url, ClipFiles.link(name)) { field, value in
                        MiningFrame.isSentenceAudio(field.lowercased()) && value.isEmpty
                    }
                } else {
                    // the video is gone or cannot be read: the note goes without the sound of its line
                    clip = nil
                }
            }
            guard let index = entries.firstIndex(where: { $0.id == id }) else { continue }
            entries[index].url = url
            entries[index].clip = clip
            save()
        }
    }
}
