
// MARK: - Satori v2.18: the mining queue goes to AnkiMobile as one package

/// The notes of the mining queue as one Anki package (.apkg): AnkiMobile imports them at once, instead of a trip to
/// its add screen and back for every note. The note types and decks come from the newest backup of AnkiMobile
/// (ankiImport.ts sends them as "ankiModels"): Anki's importer puts the notes into the note type with the same id,
/// fields and card types, and into the deck with the same name; the same package twice adds nothing (every note
/// keeps the id of its entry as its guid). Checked with the importer of Anki 26.09 (scratchpad apkg_test.py).
enum MiningBatch {
    struct Template: Codable {
        let name: String
        let qfmt: String
        let afmt: String
    }

    struct Notetype: Codable {
        let id: Int64
        let name: String
        let kind: Int
        let sortf: Int
        let css: String
        let fields: [String]
        let templates: [Template]
    }

    struct Deck: Codable {
        let id: Int64
        let name: String
    }

    struct Models: Codable {
        let notetypes: [Notetype]
        let decks: [Deck]
    }

    enum Failure: Error {
        /// a note type the backup does not have (or a cloze one), or the package could not be written: one by one
        case unknown
        /// a sound or a picture of a note did not download
        case offline(String)
    }

    /// One note of the package.
    struct Note {
        let guid: String
        let notetype: Notetype
        let deck: String
        let tags: String
        let fields: [String]
        let cards: [Int]
    }

    static let sounds: Set<String> = ["mp3", "m4a", "aac", "ogg", "opus", "wav"]
    static let media = ["mp3", "m4a", "aac", "ogg", "opus", "wav", "jpg", "jpeg", "png", "gif", "webp"]

    private static var file: URL {
        let base = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
        try? FileManager.default.createDirectory(at: base, withIntermediateDirectories: true)
        return base.appendingPathComponent("anki-models.json")
    }

    static var folder: URL {
        FileManager.default.temporaryDirectory.appendingPathComponent("satori-package", isDirectory: true)
    }

    /// The note types and decks of the newest backup, from the import page.
    static func save(_ json: String) {
        guard let data = json.data(using: .utf8), (try? JSONDecoder().decode(Models.self, from: data)) != nil else {
            return
        }
        try? data.write(to: file, options: .atomic)
    }

    static func models() -> Models? {
        guard let data = try? Data(contentsOf: file) else { return nil }
        return try? JSONDecoder().decode(Models.self, from: data)
    }

    static var known: Bool {
        FileManager.default.fileExists(atPath: file.path)
    }

    /// The front of a card type shows a field that is not empty: Anki makes that card of the note.
    static func renders(_ format: String, _ values: [String: String]) -> Bool {
        func filled(_ name: String) -> Bool {
            let value = values[name.trimmingCharacters(in: .whitespaces)] ?? ""
            return !value.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        }
        var open: [Bool] = []
        var rest = Substring(format)
        while let start = rest.range(of: "{{"), let end = rest.range(of: "}}", range: start.upperBound ..< rest.endIndex) {
            let tag = rest[start.upperBound ..< end.lowerBound].trimmingCharacters(in: .whitespacesAndNewlines)
            rest = rest[end.upperBound...]
            if tag.hasPrefix("#") || tag.hasPrefix("^") {
                let shown = filled(String(tag.dropFirst()))
                open.append(tag.hasPrefix("#") ? shown : !shown)
            } else if tag.hasPrefix("/") {
                _ = open.popLast()
            } else if !open.contains(false), let name = tag.split(separator: ":").last, filled(String(name)) {
                return true
            }
        }
        return false
    }

    /// The package of the notes that can go in it (a note without a card stays in the queue).
    @MainActor
    static func build(_ entries: [MiningQueue.Entry]) async throws -> (package: URL, ids: [UUID]) {
        guard let models = models() else { throw Failure.unknown }
        var notes: [Note] = []
        var ids: [UUID] = []
        var files: [(name: String, data: Data)] = []
        for entry in entries {
            let items = URLComponents(string: entry.url)?.percentEncodedQueryItems ?? []
            func param(_ key: String) -> String {
                let value = items.first { $0.name == key }?.value ?? ""
                return value.removingPercentEncoding ?? value
            }
            guard let notetype = models.notetypes.first(where: { $0.name == param("type") }), notetype.kind == 0 else {
                throw Failure.unknown
            }
            var values: [String: String] = [:]
            for field in MiningReady.fields(of: entry.url) {
                let packed = try await MiningQueue.packed(field.value, of: entry)
                values[field.name] = packed.value
                if let made = packed.file {
                    files.append(made)
                }
            }
            var cards: [Int] = []
            for (ord, template) in notetype.templates.enumerated() where renders(template.qfmt, values) {
                cards.append(ord)
            }
            guard !cards.isEmpty else { continue }
            let deck = param("deck")
            notes.append(Note(guid: entry.id.uuidString, notetype: notetype, deck: deck.isEmpty ? "Default" : deck,
                              tags: param("tags"), fields: notetype.fields.map { values[$0] ?? "" }, cards: cards))
            ids.append(entry.id)
        }
        guard !notes.isEmpty else { throw Failure.unknown }
        let manager = FileManager.default
        try? manager.removeItem(at: folder)
        try manager.createDirectory(at: folder, withIntermediateDirectories: true)
        let database = folder.appendingPathComponent("collection.anki2")
        try write(notes, models: models, to: database.path)
        let collection = try Data(contentsOf: database)
        var parts: [(name: String, data: Data)] = [(name: "collection.anki2", data: collection)]
        var index: [String: String] = [:]
        for (number, made) in files.enumerated() {
            index[String(number)] = made.name
        }
        let list = try JSONSerialization.data(withJSONObject: index)
        parts.append((name: "media", data: list))
        for (number, made) in files.enumerated() {
            parts.append((name: String(number), data: made.data))
        }
        let format = DateFormatter()
        format.dateFormat = "yyyy-MM-dd-HHmm"
        let package = folder.appendingPathComponent("Satori-" + format.string(from: Date()) + ".apkg")
        try zip(parts).write(to: package)
        return (package, ids)
    }

    // MARK: the collection of the package: the old schema (11) every Anki imports, as genanki writes it

    private static let schema = """
    CREATE TABLE col (id integer primary key, crt integer not null, mod integer not null, scm integer not null,
      ver integer not null, dty integer not null, usn integer not null, ls integer not null, conf text not null,
      models text not null, decks text not null, dconf text not null, tags text not null);
    CREATE TABLE notes (id integer primary key, guid text not null, mid integer not null, mod integer not null,
      usn integer not null, tags text not null, flds text not null, sfld integer not null, csum integer not null,
      flags integer not null, data text not null);
    CREATE TABLE cards (id integer primary key, nid integer not null, did integer not null, ord integer not null,
      mod integer not null, usn integer not null, type integer not null, queue integer not null, due integer not null,
      ivl integer not null, factor integer not null, reps integer not null, lapses integer not null,
      left integer not null, odue integer not null, odid integer not null, flags integer not null, data text not null);
    CREATE TABLE revlog (id integer primary key, cid integer not null, usn integer not null, ease integer not null,
      ivl integer not null, lastIvl integer not null, factor integer not null, time integer not null,
      type integer not null);
    CREATE TABLE graves (usn integer not null, oid integer not null, type integer not null);
    """

    private static func deckJSON(_ id: Int64, _ name: String) -> [String: Any] {
        ["collapsed": false, "conf": 1, "desc": "", "dyn": 0, "extendNew": 10, "extendRev": 50, "id": id,
         "lrnToday": [0, 0], "mod": 0, "name": name, "newToday": [0, 0], "revToday": [0, 0], "timeToday": [0, 0],
         "usn": -1]
    }

    private static func modelJSON(_ notetype: Notetype, deck: Int64) -> [String: Any] {
        var templates: [[String: Any]] = []
        for (ord, template) in notetype.templates.enumerated() {
            templates.append(["name": template.name, "ord": ord, "qfmt": template.qfmt, "afmt": template.afmt,
                              "bqfmt": "", "bafmt": "", "did": NSNull(), "bfont": "", "bsize": 0])
        }
        var fields: [[String: Any]] = []
        for (ord, name) in notetype.fields.enumerated() {
            fields.append(["name": name, "ord": ord, "sticky": false, "rtl": false, "font": "Arial", "size": 20,
                           "media": [Any]()])
        }
        var requirements: [[Any]] = []
        for ord in notetype.templates.indices {
            requirements.append([ord, "any", [0]])
        }
        // mod 0: never newer than the note type in the collection, so its card types and CSS stay as they are
        var model: [String: Any] = ["id": notetype.id, "name": notetype.name, "type": 0, "mod": 0, "usn": -1]
        model["sortf"] = notetype.sortf
        model["did"] = deck
        model["tmpls"] = templates
        model["flds"] = fields
        model["css"] = notetype.css
        model["latexPre"] = ""
        model["latexPost"] = ""
        model["latexsvg"] = false
        model["req"] = requirements
        model["tags"] = [Any]()
        model["vers"] = [Any]()
        return model
    }

    private static let conf: [String: Any] = [
        "activeDecks": [1], "addToCur": true, "collapseTime": 1200, "curDeck": 1, "curModel": NSNull(),
        "dueCounts": true, "estTimes": true, "newBury": true, "newSpread": 0, "nextPos": 1, "sortBackwards": false,
        "sortType": "noteFld", "timeLim": 0,
    ]

    private static let dconf: [String: Any] = [
        "1": [
            "autoplay": true, "id": 1, "maxTaken": 60, "mod": 0, "name": "Default", "replayq": true, "timer": 0,
            "usn": 0,
            "lapse": ["delays": [10], "leechAction": 0, "leechFails": 8, "minInt": 1, "mult": 0] as [String: Any],
            "new": ["bury": true, "delays": [1, 10], "initialFactor": 2500, "ints": [1, 4, 7], "order": 1,
                    "perDay": 20, "separate": true] as [String: Any],
            "rev": ["bury": true, "ease4": 1.3, "fuzz": 0.05, "ivlFct": 1, "maxIvl": 36500, "minSpace": 1,
                    "perDay": 100] as [String: Any],
        ] as [String: Any],
    ]

    private static func json(_ object: Any) throws -> String {
        let data = try JSONSerialization.data(withJSONObject: object)
        return String(data: data, encoding: .utf8) ?? "{}"
    }

    private static func write(_ notes: [Note], models: Models, to path: String) throws {
        var opened: OpaquePointer? = nil
        guard sqlite3_open(path, &opened) == SQLITE_OK, let db = opened else { throw Failure.unknown }
        defer {
            sqlite3_close(db)
        }
        let transient = unsafeBitCast(-1, to: sqlite3_destructor_type.self)
        guard sqlite3_exec(db, schema + "\nBEGIN;", nil, nil, nil) == SQLITE_OK else { throw Failure.unknown }
        func insert(_ sql: String, _ values: [Any]) throws {
            var made: OpaquePointer? = nil
            guard sqlite3_prepare_v2(db, sql, -1, &made, nil) == SQLITE_OK, let statement = made else {
                throw Failure.unknown
            }
            defer {
                sqlite3_finalize(statement)
            }
            for (index, value) in values.enumerated() {
                let at = Int32(index + 1)
                if let number = value as? Int64 {
                    sqlite3_bind_int64(statement, at, number)
                } else if let number = value as? Int {
                    sqlite3_bind_int64(statement, at, Int64(number))
                } else {
                    sqlite3_bind_text(statement, at, String(describing: value), -1, transient)
                }
            }
            guard sqlite3_step(statement) == SQLITE_DONE else { throw Failure.unknown }
        }
        let base = Int64(Date().timeIntervalSince1970 * 1000)
        let now = base / 1000
        var decks: [String: Any] = ["1": deckJSON(1, "Default")]
        var used: [String: Any] = [:]
        // a deck the backup does not have: Anki makes it by its name
        var newDecks: [String: Int64] = [:]
        for (number, note) in notes.enumerated() {
            let position = Int64(number)
            let deck: Int64
            if let known = models.decks.first(where: { $0.name == note.deck })?.id ?? newDecks[note.deck] {
                deck = known
            } else {
                deck = base + 500_000 + Int64(newDecks.count)
                newDecks[note.deck] = deck
            }
            decks[String(deck)] = deckJSON(deck, note.deck)
            used[String(note.notetype.id)] = modelJSON(note.notetype, deck: deck)
            let sortIndex = note.notetype.sortf < note.fields.count ? note.notetype.sortf : 0
            let sortSource = note.fields.isEmpty ? "" : note.fields[sortIndex]
            let sort = sortSource.replacingOccurrences(of: "<[^>]*>", with: "", options: .regularExpression)
            let digest = Array(Insecure.SHA1.hash(data: Data(sort.utf8)))
            var checksum: Int64 = 0
            for byte in digest.prefix(4) {
                checksum = checksum * 256 + Int64(byte)
            }
            let words = note.tags.split(separator: " ").map { String($0) }
            let tags = words.isEmpty ? "" : " " + words.joined(separator: " ") + " "
            let noteID = base + position
            let row: [Any] = [noteID, note.guid, note.notetype.id, now, -1, tags, note.fields.joined(separator: "\u{1f}"),
                              sort, checksum, 0, ""]
            try insert("insert into notes values (?,?,?,?,?,?,?,?,?,?,?)", row)
            for ord in note.cards {
                let cardID = base + 100_000 + position * 20 + Int64(ord)
                let card: [Any] = [cardID, noteID, deck, ord, now, -1, 0, 0, number + 1, 0, 0, 0, 0, 0, 0, 0, 0, ""]
                try insert("insert into cards values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", card)
            }
        }
        let confText = try json(conf)
        let modelsText = try json(used)
        let decksText = try json(decks)
        let dconfText = try json(dconf)
        let col: [Any] = [now, base, base, confText, modelsText, decksText, dconfText, "{}"]
        try insert("insert into col values (1,?,?,?,11,0,0,0,?,?,?,?,?)", col)
        guard sqlite3_exec(db, "COMMIT;", nil, nil, nil) == SQLITE_OK else { throw Failure.unknown }
    }

    // MARK: the zip of the package: the files as they are (stored), what Anki's importer reads

    private static let crcTable: [UInt32] = (0 ..< 256).map { number -> UInt32 in
        var value = UInt32(number)
        for _ in 0 ..< 8 {
            value = (value & 1) != 0 ? 0xEDB8_8320 ^ (value >> 1) : value >> 1
        }
        return value
    }

    private static func crc32(_ data: Data) -> UInt32 {
        var crc: UInt32 = 0xFFFF_FFFF
        for byte in data {
            crc = crcTable[Int((crc ^ UInt32(byte)) & 0xFF)] ^ (crc >> 8)
        }
        return crc ^ 0xFFFF_FFFF
    }

    private static func put16(_ data: inout Data, _ value: Int) {
        data.append(UInt8(value & 0xFF))
        data.append(UInt8((value >> 8) & 0xFF))
    }

    private static func put32(_ data: inout Data, _ value: UInt32) {
        for shift in [0, 8, 16, 24] {
            data.append(UInt8((value >> UInt32(shift)) & 0xFF))
        }
    }

    static func zip(_ files: [(name: String, data: Data)]) -> Data {
        var out = Data()
        var central = Data()
        for file in files {
            let name = Data(file.name.utf8)
            let crc = crc32(file.data)
            let size = UInt32(file.data.count)
            let offset = UInt32(out.count)
            // the local header: version 2.0, no flags, stored, 1980-01-01
            put32(&out, 0x0403_4B50)
            put16(&out, 20)
            put16(&out, 0)
            put16(&out, 0)
            put16(&out, 0)
            put16(&out, 0x21)
            put32(&out, crc)
            put32(&out, size)
            put32(&out, size)
            put16(&out, name.count)
            put16(&out, 0)
            out.append(name)
            out.append(file.data)
            put32(&central, 0x0201_4B50)
            put16(&central, 20)
            put16(&central, 20)
            put16(&central, 0)
            put16(&central, 0)
            put16(&central, 0)
            put16(&central, 0x21)
            put32(&central, crc)
            put32(&central, size)
            put32(&central, size)
            put16(&central, name.count)
            for _ in 0 ..< 4 {
                put16(&central, 0)
            }
            put32(&central, 0)
            put32(&central, offset)
            central.append(name)
        }
        let start = UInt32(out.count)
        out.append(central)
        put32(&out, 0x0605_4B50)
        put16(&out, 0)
        put16(&out, 0)
        put16(&out, files.count)
        put16(&out, files.count)
        put32(&out, UInt32(central.count))
        put32(&out, start)
        put16(&out, 0)
        return out
    }

    /// The package goes to AnkiMobile through the share sheet («Anki» among its apps); `done` says whether it went.
    @MainActor
    static func share(_ package: URL, done: @escaping (Bool) -> Void) {
        let windows = UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }.flatMap { $0.windows }
        guard var top = (windows.first { $0.isKeyWindow } ?? windows.first)?.rootViewController else {
            done(false)
            return
        }
        while let shown = top.presentedViewController {
            top = shown
        }
        let sheet = UIActivityViewController(activityItems: [package], applicationActivities: nil)
        sheet.popoverPresentationController?.sourceView = top.view
        sheet.completionWithItemsHandler = { _, completed, _, _ in
            done(completed)
        }
        top.present(sheet, animated: true)
    }
}

@MainActor
extension MiningQueue {
    /// A field of a note in the package. A link to a sound or a picture, or the frame and sound of a note kept since
    /// 1.66, becomes a file of the package, as AnkiMobile does with such a field of a note it adds itself.
    static func packed(_ value: String, of entry: Entry) async throws -> (value: String, file: (name: String, data: Data)?) {
        let link = value.trimmingCharacters(in: .whitespacesAndNewlines)
        var data: Data? = nil
        var ext = ""
        if link == frameMarker || link == audioMarker {
            let name = link == frameMarker ? entry.frame : entry.audio
            data = name.flatMap { try? Data(contentsOf: frameFolder.appendingPathComponent($0)) }
            ext = link == frameMarker ? "jpg" : "m4a"
        } else if link.hasPrefix("http"), link.count < 4000, !link.contains(where: { $0.isWhitespace }),
                  let found = MiningBatch.media.first(where: { link.lowercased().hasSuffix("." + $0) }) {
            ext = found
            let local = ClipFiles.link("")
            if link.hasPrefix(local) {
                data = try? Data(contentsOf: ClipFiles.folder.appendingPathComponent(String(link.dropFirst(local.count))))
            } else if let url = URL(string: link) {
                let loaded: (Data, URLResponse)
                do {
                    loaded = try await URLSession.shared.data(from: url)
                } catch {
                    throw MiningBatch.Failure.offline(url.host ?? link)
                }
                // a server that answers without the file, JapanesePod101's "audio not available": no file
                let jpod = (url.host ?? "").contains("languagepod101")
                let placeholder = jpod && (loaded.0.count == 52288 || loaded.0.count < 2000)
                if (loaded.1 as? HTTPURLResponse)?.statusCode == 200, !loaded.0.isEmpty, !placeholder {
                    data = loaded.0
                }
            }
        } else {
            return (value, nil)
        }
        guard let data else { return ("", nil) }
        let name = "satori-" + UUID().uuidString.lowercased() + "." + ext
        let field = MiningBatch.sounds.contains(ext) ? "[sound:" + name + "]" : "<img src=\"" + name + "\">"
        return (field, (name: name, data: data))
    }

    /// Two notes or more go as one package when the backup of AnkiMobile knows their note type; else one by one.
    func sendTogether() {
        guard sending.count > 1, MiningBatch.known, !packing else {
            sendNext()
            return
        }
        let batch = sending
        sending = []
        packing = true
        Task { @MainActor in
            do {
                let made = try await MiningBatch.build(batch)
                packing = false
                MiningBatch.share(made.package) { completed in
                    if completed {
                        self.packed = made.ids
                    }
                }
            } catch MiningBatch.Failure.offline(let host) {
                packing = false
                packFailure = "Не скачался звук с " + host + ". Проверьте интернет и попробуйте ещё раз."
            } catch {
                // a note type the backup does not know: one by one, as before 2.18
                packing = false
                sending = batch
                sendNext()
            }
        }
    }

    /// The user says whether AnkiMobile has the notes of the package: then they leave the queue and count as mined.
    func packedArrived(_ arrived: Bool) {
        let ids = Set(packed)
        packed = []
        try? FileManager.default.removeItem(at: MiningBatch.folder)
        guard arrived else { return }
        for entry in entries where ids.contains(entry.id) {
            MiningQueue.recordMined(MiningQueue.statsWord(of: entry.url))
            MiningQueue.deleteFrame(entry)
        }
        entries.removeAll { ids.contains($0.id) }
        save()
    }
}
