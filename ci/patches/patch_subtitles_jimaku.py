# Moved out of build-ios-v141-player.yml, step "Patch subtitles and highlight (Jimaku search, kana rank, content words, tail of the line, seek, landscape)" (GitHub limits workflow files to 500 KB).
import pathlib

def replace_once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)

JIMAKU_ENUMS = r'''/// The Jimaku API key lives in the Keychain (never in the workflow file).
enum JimakuKeychain {
    static let service = "yomikiri.jimaku"

    static func read() -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ]
        var out: AnyObject?
        guard SecItemCopyMatching(query as CFDictionary, &out) == errSecSuccess,
              let data = out as? Data,
              let key = String(data: data, encoding: .utf8),
              !key.isEmpty else { return nil }
        return key
    }

    static func write(_ key: String) {
        let base: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
        ]
        SecItemDelete(base as CFDictionary)
        guard !key.isEmpty else { return }
        var add = base
        add[kSecValueData as String] = Data(key.utf8)
        SecItemAdd(add as CFDictionary, nil)
    }
}

/// Jimaku (api-1.json): search an entry, list the files of one episode, download a file.
@available(iOS 16.0, *)
enum JimakuService {
    static let base = "https://jimaku.cc"

    struct Entry: Decodable {
        let id: Int
        let name: String
        let english_name: String?
        let japanese_name: String?
        let anilist_id: Int?
    }

    struct FileEntry: Decodable {
        let url: String
        let name: String
        let size: Int
    }

    enum Failure: Error {
        case status(Int)
        case badURL
    }

    static func get<T: Decodable>(_ path: String, query: [URLQueryItem], key: String) async throws -> T {
        guard var parts = URLComponents(string: base + path) else { throw Failure.badURL }
        parts.queryItems = query.isEmpty ? nil : query
        guard let url = parts.url else { throw Failure.badURL }
        var request = URLRequest(url: url, timeoutInterval: 15)
        request.setValue(key, forHTTPHeaderField: "Authorization")
        request.setValue("Yomikiri/1.8", forHTTPHeaderField: "User-Agent")
        let (data, response) = try await URLSession.shared.data(for: request)
        let status = (response as? HTTPURLResponse)?.statusCode ?? 0
        guard status == 200 else { throw Failure.status(status) }
        return try JSONDecoder().decode(T.self, from: data)
    }

    static func search(_ title: String, key: String) async throws -> [Entry] {
        try await get("/api/entries/search",
                      query: [URLQueryItem(name: "anime", value: "true"),
                              URLQueryItem(name: "query", value: title)],
                      key: key)
    }

    static func files(entry: Int, episode: Int, key: String) async throws -> [FileEntry] {
        try await get("/api/entries/\(entry)/files",
                      query: [URLQueryItem(name: "episode", value: String(episode))],
                      key: key)
    }

    static func download(_ file: FileEntry, key: String) async throws -> URL {
        guard let url = URL(string: file.url) else { throw Failure.badURL }
        var request = URLRequest(url: url, timeoutInterval: 30)
        request.setValue(key, forHTTPHeaderField: "Authorization")
        let (temp, response) = try await URLSession.shared.download(for: request)
        let status = (response as? HTTPURLResponse)?.statusCode ?? 0
        guard status == 200 else { throw Failure.status(status) }
        return temp
    }

    /// lower-case letters, digits, kana and kanji; everything else becomes a space
    static func norm(_ text: String) -> String {
        let kept = text.lowercased().unicodeScalars.map { sc -> Character in
            let v = sc.value
            if (v >= 0x30 && v <= 0x39) || (v >= 0x61 && v <= 0x7A) || (v >= 0x3040 && v <= 0x30FF) || (v >= 0x4E00 && v <= 0x9FFF) {
                return Character(sc)
            }
            return " "
        }
        return String(kept).split(separator: " ").joined(separator: " ")
    }

    /// 2 * longest common subsequence / total length, between 0 and 1
    static func similarity(_ a: String, _ b: String) -> Double {
        let x = Array(a), y = Array(b)
        if x.isEmpty || y.isEmpty { return x.isEmpty && y.isEmpty ? 1 : 0 }
        var prev = Array(repeating: 0, count: y.count + 1)
        for i in 1...x.count {
            var cur = Array(repeating: 0, count: y.count + 1)
            for j in 1...y.count {
                cur[j] = x[i - 1] == y[j - 1] ? prev[j - 1] + 1 : max(prev[j], cur[j - 1])
            }
            prev = cur
        }
        return 2.0 * Double(prev[y.count]) / Double(x.count + y.count)
    }

    /// The entry only when one is clearly right; several close ones give nil (the user chooses later).
    static func pickEntry(title: String, entries: [Entry]) -> Entry? {
        let wanted = norm(title)
        let scored = entries.map { e -> (score: Double, entry: Entry) in
            let names = [e.name, e.english_name ?? "", e.japanese_name ?? ""]
            let best = names.map { similarity(wanted, norm($0)) }.max() ?? 0
            return (best, e)
        }.sorted { $0.score > $1.score }
        guard let first = scored.first, first.score >= 0.85 else { return nil }
        if scored.count > 1, first.score - scored[1].score < 0.10 { return nil }
        return first.entry
    }

    /// subtitle files only, Japanese first, the release of the video first, at most five
    static func pickFiles(_ files: [FileEntry], release: String?) -> [FileEntry] {
        let subs = files.filter { ["srt", "ass", "ssa", "vtt"].contains(($0.name as NSString).pathExtension.lowercased()) }
        func score(_ f: FileEntry) -> Int {
            var s = 0
            if let release, f.name.uppercased().contains(release) { s += 2 }
            if f.name.range(of: #"\b(ENG|CHS|CHT|CHI)\b"#, options: [.regularExpression, .caseInsensitive]) != nil { s -= 5 }
            return s
        }
        return Array(subs.sorted { score($0) > score($1) }.prefix(5))
    }
}

/// Title and episode from a video file name (the same rules as jimaku_parse_name.py).
enum JimakuName {
    struct Parsed {
        let title: String?
        let episode: Int?
    }

    static func parse(_ file: String) -> Parsed {
        var s = (file as NSString).deletingPathExtension
        s = s.replacingOccurrences(of: #"\[[^\]]*\]|\([^)]*\)"#, with: " ", options: .regularExpression)
        s = s.replacingOccurrences(of: "_", with: " ")
        if !s.contains(" "), s.filter({ $0 == "." }).count >= 2 {
            s = s.replacingOccurrences(of: ".", with: " ")
        }
        s = s.split(separator: " ").joined(separator: " ")
        let rules = [
            #"\bS\d{1,2}\s*E(\d{1,3})\b"#,
            #"\b\d{1,2}x(\d{1,3})\b"#,
            #"(?:^|\s)-\s*(\d{1,3})(?:v\d+)?(?=\s|$|-)"#,
            #"\b(?:EP|E|Episode|Ep\.)\s*(\d{1,3})\b"#,
            #"#(\d{1,3})\b"#,
            #"第\s*(\d{1,3})\s*話"#,
            #"(?:^|\s)(\d{1,3})(?:\s?v\d+)?$"#,
        ]
        for rule in rules {
            guard let re = try? NSRegularExpression(pattern: rule, options: [.caseInsensitive]) else { continue }
            let ns = s as NSString
            guard let m = re.firstMatch(in: s, range: NSRange(location: 0, length: ns.length)),
                  m.numberOfRanges > 1 else { continue }
            let episode = Int(ns.substring(with: m.range(at: 1)))
            var head = ns.substring(to: m.range.location)
            head = head.replacingOccurrences(of: #"\b(\d(st|nd|rd|th) Season|Season\s*\d+|Part\s*\d+|Final Season)\b"#,
                                             with: " ", options: [.regularExpression, .caseInsensitive])
            let title = head.trimmingCharacters(in: CharacterSet(charactersIn: " -_.:"))
            return Parsed(title: title.isEmpty ? nil : title, episode: episode)
        }
        return Parsed(title: s.isEmpty ? nil : s, episode: nil)
    }

    /// "BD" or "WEB" when the file name says so, to prefer subtitles of the same release
    static func release(_ file: String) -> String? {
        let upper = file.uppercased()
        if upper.contains("BD") { return "BD" }
        if upper.contains("WEB") { return "WEB" }
        return nil
    }
}

/// Key entry for the Jimaku API key.
@available(iOS 16.0, *)
struct JimakuKeySheet: View {
    @Environment(\.dismiss) private var dismiss
    @State private var key = JimakuKeychain.read() ?? ""

    var body: some View {
        NavigationView {
            Form {
                Section("API-ключ Jimaku") {
                    SecureField("Ключ", text: $key)
                    Text("Ключ хранится в Keychain. Нужен, чтобы находить японские субтитры при импорте видео.")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }
            .navigationTitle("Jimaku")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Отмена") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Сохранить") {
                        JimakuKeychain.write(key.trimmingCharacters(in: .whitespacesAndNewlines))
                        dismiss()
                    }
                }
            }
        }
    }
}

/// Jimaku search for one video: used by the video list and by the player settings.
@available(iOS 16.0, *)
@MainActor
enum JimakuFinder {
    /// Returns the saved subtitle file, or nil. Every step is reported through `report`.
    static func run(_ video: URL, report: @escaping (String) -> Void) async -> URL? {
        guard let key = JimakuKeychain.read() else {
            report("Jimaku: нет ключа, добавьте его кнопкой в списке видео")
            return nil
        }
        let name = video.lastPathComponent
        let parsed = JimakuName.parse(name)
        guard let title = parsed.title, let episode = parsed.episode else {
            report("Jimaku: не удалось разобрать название")
            return nil
        }
        report("Jimaku: ищу «\(title)»…")
        do {
            let entries = try await JimakuService.search(title, key: key)
            guard let entry = JimakuService.pickEntry(title: title, entries: entries) else {
                report("Jimaku: нет однозначного совпадения")
                return nil
            }
            let files = try await JimakuService.files(entry: entry.id, episode: episode, key: key)
            for file in JimakuService.pickFiles(files, release: JimakuName.release(name)) {
                let temp = try await JimakuService.download(file, key: key)
                let ext = (file.name as NSString).pathExtension.lowercased()
                let dest = video.deletingPathExtension().appendingPathExtension("jimaku." + ext)
                let check = await Task.detached(priority: .utility) { () -> (matches: Int, total: Int, delay: Double)? in
                    let reference = EmbeddedSubtitles.referenceStarts(url: video)
                    guard reference.count >= 8 else { return nil }
                    let external = EmbeddedSubtitles.cues(fromFile: temp).map { $0.start }
                    guard let r = SubtitleSync.bestOffset(reference: reference, external: external) else { return nil }
                    return (r.matches, r.total, r.delay)
                }.value
                guard let r = check, r.matches >= max(8, r.total / 2) else { continue }
                try? FileManager.default.removeItem(at: dest)
                try FileManager.default.moveItem(at: temp, to: dest)
                UserDefaults.standard.set(r.delay, forKey: "subdelay." + name)
                UserDefaults.standard.set("file:" + dest.lastPathComponent, forKey: "subchoice." + name)
                report("Jimaku: совпало \(r.matches) из \(r.total)")
                return dest
            }
            report("Jimaku: совпадений мало")
            return nil
        } catch JimakuService.Failure.status(let code) {
            report(code == 401 ? "Jimaku: неверный ключ" : code == 429 ? "Jimaku: слишком много запросов" : "Jimaku: ошибка сервера \(code)")
            return nil
        } catch {
            report("Jimaku: нет связи с сайтом")
            return nil
        }
    }
}

'''

JIMAKU_FUNCS = r'''    /// KSPlayer selects its own default track just after the start, which would switch the chosen file off.
    /// The file is put back a few times, unless the user has chosen something else meanwhile.
    @MainActor
    private func holdExternalChoice(_ file: URL) {
        let chosen = "file:" + file.lastPathComponent
        Task { @MainActor in
            for _ in 0..<6 {
                try? await Task.sleep(nanoseconds: 700_000_000)
                guard UserDefaults.standard.string(forKey: subChoiceKey) == chosen else { return }
                if coordinator.subtitleModel.selectedSubtitleInfo != nil {
                    coordinator.subtitleModel.selectedSubtitleInfo = nil
                    usingExternal = true
                    activeExternal = file
                }
            }
        }
    }

    /// Searches Jimaku for the open video (the same search as on import) and switches to the file found.
    @MainActor
    private func searchJimaku() {
        syncMessage = "Jimaku: ищу…"
        Task { @MainActor in
            if let file = await JimakuFinder.run(url, report: { message in self.syncMessage = message }) {
                if !externalURLs.contains(file) { externalURLs.append(file) }
                chooseExternal(file)
                holdExternalChoice(file)
                subDelay = UserDefaults.standard.double(forKey: delayKey)
            }
        }
    }
'''

p = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = p.read_text(encoding="utf-8")

# Jimaku: Keychain, service and finder (a self-contained Swift block)
if "import Security" not in s:
    s = "import Security\n" + s
s = replace_once(s, "/// One folder of the video library", JIMAKU_ENUMS + "/// One folder of the video library", "jimaku enums")

# Jimaku: player functions and the hold of the chosen file
s = replace_once(s, "    @MainActor\n    private func loadSubtitles() async {",
                 JIMAKU_FUNCS + "    @MainActor\n    private func loadSubtitles() async {", "jimaku funcs")
s = replace_once(s, "                restoredFile = true\n                restoredURL = file\n",
                 "                restoredFile = true\n                restoredURL = file\n                holdExternalChoice(file)\n", "hold saved choice")

# Jimaku: buttons in the subtitles section
s = replace_once(s, '                    Button("Добавить свои субтитры") { showImporter = true }\n', r'''                    Button("Найти японские субтитры на Jimaku") { searchJimaku() }
                    Button("Добавить свои субтитры") { showImporter = true }
                    Button("Найти в Jimaku") {
                        Task { @MainActor in
                            if let file = await JimakuFinder.run(url, report: { syncMessage = $0 }) {
                                if !externalURLs.contains(file) { externalURLs.append(file) }
                                subDelay = UserDefaults.standard.double(forKey: delayKey)
                                chooseExternal(file)
                            }
                        }
                    }
''', "jimaku buttons")

# highlight: rank by the written form (kana word -> kana rank), strict pairs only
s = replace_once(s, "static func rank(base: String, reading: String, dict: String) -> Int? {",
                 'static func rank(base: String, reading: String, dict: String, text: String = "") -> Int? {', "rank signature")
s = replace_once(s, "let kanaOnly = base.unicodeScalars.allSatisfy { (0x3040...0x30FF).contains($0.value) }",
                 r'''let written = text.isEmpty ? base : text
        let kanaOnly = written.unicodeScalars.allSatisfy { (0x3040...0x30FF).contains($0.value) }''', "kanaOnly")
s = replace_once(s, "rank(base: token.base, reading: reading, dict: settings.dict)",
                 "rank(base: token.base, reading: reading, dict: settings.dict, text: token.text)", "rank call")
s = replace_once(s, "find(t, width: 3, hash(base)) else { return nil }",
                 "(reading.isEmpty ? find(t, width: 3, hash(base)) : nil) else { return nil }", "rank strict")
s = replace_once(s, "find(t, width: 2, hash(base)) else { return 0 }",
                 "(reading.isEmpty ? find(t, width: 2, hash(base)) : nil) else { return 0 }", "jlpt strict")

# highlight: only content words (nouns, verbs, adjectives, adverbs), as on the web
s = replace_once(s, 'var reading: String = ""\n}', 'var reading: String = ""\n    var pos: String = ""\n}', "token pos field")
s = replace_once(s, 'reading: t["reading"] as? String ?? ""))',
                 'reading: t["reading"] as? String ?? "",\n                                      pos: t["pos"] as? String ?? ""))', "token pos read")
s = replace_once(s, "        for token in tokens where !token.base.isEmpty && !mined.contains(token.base) {",
                 r'''        let contentPOS: Set<String> = ["名詞", "動詞", "形容詞", "形状詞", "副詞"]
        for token in tokens where !token.base.isEmpty && !mined.contains(token.base) && contentPOS.contains(token.pos) {''', "content pos")

# subtitle bar: line breaks become spaces; text the tokenizer does not return is kept as a plain tail
s = replace_once(s, '''    private func refresh(_ text: String) {
        let result = NativeLookup.tokenize(text, charAt: 0).tokens
        tokens = result
        tokenColors = HighlightData.colors(for: result)
    }''', r'''    private func refresh(_ text: String) {
        // line breaks inside a cue become spaces; text the tokenizer does not return is shown as a plain tail
        let clean = text.replacingOccurrences(of: "\\N", with: " ")
            .replacingOccurrences(of: "\n", with: " ")
            .trimmingCharacters(in: .whitespaces)
        var result = NativeLookup.tokenize(clean, charAt: 0).tokens
        let covered = result.map { $0.text }.joined().replacingOccurrences(of: " ", with: "")
        let whole = clean.replacingOccurrences(of: " ", with: "")
        if covered != whole {
            if !whole.isEmpty && whole.hasPrefix(covered) {
                let tail = String(whole.dropFirst(covered.count))
                result.append(LookupToken(id: result.count, text: tail, start: covered.count))
            } else {
                result = [LookupToken(id: 0, text: clean, start: 0)]
            }
        }
        tokens = result
        tokenColors = HighlightData.colors(for: result)
    }''', "refresh")

# seek through the player layer (restores the video output after a jump)
s = replace_once(s, "coordinator.playerLayer?.player.seek(time: time) { _ in }",
                 "coordinator.playerLayer?.seek(time: time, autoPlay: playing) { _ in }", "seek to")
s = replace_once(s, "current.player.seek(time: time) { _ in }",
                 "current.seek(time: time, autoPlay: true) { _ in }", "seek recover")

# landscape: the lookup window goes to the bottom edge
s = replace_once(s, "                landscapeLookup\n",
                 "                landscapeLookup\n                    .ignoresSafeArea(edges: .bottom)\n", "landscape bottom")

# Jimaku key: the key icon in the video list toolbar (opens the key sheet)
s = replace_once(s, '    @State private var newFolderName = ""\n',
                 '    @State private var newFolderName = ""\n    @State private var showKey = false\n', "key state")
s = replace_once(s, '''                    Image(systemName: "folder.badge.plus")
                }
            }
        }
        .sheet(isPresented: $showImporter) {
''', '''                    Image(systemName: "folder.badge.plus")
                }
            }
            ToolbarItem(placement: .navigationBarTrailing) {
                Button {
                    showKey = true
                } label: {
                    Image(systemName: "key")
                }
            }
        }
        .sheet(isPresented: $showKey) {
            JimakuKeySheet()
        }
        .sheet(isPresented: $showImporter) {
''', "key toolbar and sheet")

p.write_text(s, encoding="utf-8")
print("fixes applied")
