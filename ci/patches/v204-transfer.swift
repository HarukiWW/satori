
// MARK: - Satori v2.04: moving the data between two installs

/// Two installs of Satori signed with the same certificate share its App Groups: one moves its data into a box there,
/// the other takes it. Moves are renames on one volume, so gigabytes of videos go at once. Nothing is overwritten in
/// the box, and the box is removed only when everything left it.
enum InstallTransfer {
    static func box() -> URL? {
        guard let shared = try? getSharedDirectory(), !shared.path.contains("/Containers/Data/Application/") else {
            return nil
        }
        return shared.appendingPathComponent("Satori-Transfer", isDirectory: true)
    }

    /// what moves: a name in the box and the folder of this install
    static func parts() -> [(name: String, url: URL)] {
        let manager = FileManager.default
        let library = manager.urls(for: .libraryDirectory, in: .userDomainMask)[0]
        let caches = manager.urls(for: .cachesDirectory, in: .userDomainMask)[0]
        return [
            (name: "Documents", url: manager.urls(for: .documentDirectory, in: .userDomainMask)[0]),
            (name: "ApplicationSupport", url: manager.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]),
            (name: "mining-frames", url: library.appendingPathComponent("mining-frames")),
            (name: "mining-sounds", url: library.appendingPathComponent("mining-sounds")),
            (name: "covers", url: caches.appendingPathComponent("covers")),
            (name: "catalog", url: caches.appendingPathComponent("catalog")),
        ]
    }

    /// The install that filled the box, and when.
    static func boxInfo() -> (from: String, date: Date)? {
        guard let box = box(), let data = try? Data(contentsOf: box.appendingPathComponent("info.plist")),
              let info = (try? PropertyListSerialization.propertyList(from: data, options: [], format: nil)) as? [String: Any],
              let from = info["from"] as? String else { return nil }
        let date = Date(timeIntervalSince1970: (info["date"] as? Double) ?? 0)
        return (from: from, date: date)
    }

    /// Keys that stay with the install: the backup folder chosen in it, and the keys of the system.
    private static func skipped(_ key: String) -> Bool {
        let prefixes = ["ykAnkiBackup", "NS", "Apple", "AK", "com.apple.", "WebKit", "WK", "PK", "MSV"]
        return prefixes.contains { key.hasPrefix($0) }
    }

    private static func items(_ folder: URL) -> [URL] {
        (try? FileManager.default.contentsOfDirectory(at: folder, includingPropertiesForKeys: nil)) ?? []
    }

    /// Moves everything of this install into the box (the data leaves this install).
    static func give() -> String {
        let manager = FileManager.default
        guard let box = box() else { return "Нет общей папки App Group: перенос невозможен." }
        try? manager.createDirectory(at: box, withIntermediateDirectories: true)
        var moved = 0
        var problems: [String] = []
        for part in parts() {
            let target = box.appendingPathComponent(part.name, isDirectory: true)
            try? manager.createDirectory(at: target, withIntermediateDirectories: true)
            for item in items(part.url) {
                do {
                    // fails when the name is already in the box: what is there stays
                    try manager.moveItem(at: item, to: target.appendingPathComponent(item.lastPathComponent))
                    moved += 1
                } catch {
                    problems.append(item.lastPathComponent + ": " + error.localizedDescription)
                }
            }
        }
        let domain = UserDefaults.standard.persistentDomain(forName: Bundle.main.bundleIdentifier ?? "") ?? [:]
        let settings = domain.filter { !skipped($0.key) }
        let defaultsFile = box.appendingPathComponent("defaults.plist")
        if !manager.fileExists(atPath: defaultsFile.path),
           let data = try? PropertyListSerialization.data(fromPropertyList: settings, format: .binary, options: 0) {
            try? data.write(to: defaultsFile)
        }
        let info: [String: Any] = ["from": Bundle.main.bundleIdentifier ?? "", "date": Date().timeIntervalSince1970]
        if let data = try? PropertyListSerialization.data(fromPropertyList: info, format: .xml, options: 0) {
            try? data.write(to: box.appendingPathComponent("info.plist"))
        }
        var text = "Отдано: файлов и папок — " + String(moved) + ", настроек — " + String(settings.count) + "."
        if !problems.isEmpty {
            text += " Не перенеслось: " + problems.prefix(5).joined(separator: "; ") + "."
        }
        return text
    }

    /// A folder of the box goes into the folder here; a file of the box replaces the one here. Returns how many items
    /// moved and how many stayed in the box.
    private static func merge(_ source: URL, into target: URL) -> (moved: Int, left: Int) {
        let manager = FileManager.default
        var targetIsFolder: ObjCBool = false
        var sourceIsFolder: ObjCBool = false
        if manager.fileExists(atPath: target.path, isDirectory: &targetIsFolder) {
            _ = manager.fileExists(atPath: source.path, isDirectory: &sourceIsFolder)
            if targetIsFolder.boolValue && sourceIsFolder.boolValue {
                var moved = 0
                var left = 0
                for child in items(source) {
                    let result = merge(child, into: target.appendingPathComponent(child.lastPathComponent))
                    moved += result.moved
                    left += result.left
                }
                if items(source).isEmpty {
                    try? manager.removeItem(at: source)
                }
                return (moved: moved, left: left)
            }
            try? manager.removeItem(at: target)
        }
        return (try? manager.moveItem(at: source, to: target)) != nil ? (moved: 1, left: 0) : (moved: 0, left: 1)
    }

    /// Takes the box: files into the folders here, settings into the settings here (the backup folder chosen here
    /// stays). The box goes away only when nothing is left in it, so a failed move can be repeated.
    static func take() -> String {
        let manager = FileManager.default
        guard let box = box() else { return "Нет общей папки App Group: перенос невозможен." }
        var moved = 0
        var left = 0
        for part in parts() {
            try? manager.createDirectory(at: part.url, withIntermediateDirectories: true)
            for item in items(box.appendingPathComponent(part.name, isDirectory: true)) {
                let result = merge(item, into: part.url.appendingPathComponent(item.lastPathComponent))
                moved += result.moved
                left += result.left
            }
        }
        var count = 0
        if let data = try? Data(contentsOf: box.appendingPathComponent("defaults.plist")),
           let settings = (try? PropertyListSerialization.propertyList(from: data, options: [], format: nil)) as? [String: Any] {
            for (key, value) in settings where !skipped(key) {
                UserDefaults.standard.set(value, forKey: key)
                count += 1
            }
            // the app is closed right after this
            UserDefaults.standard.synchronize()
        }
        var text = "Принято: файлов и папок — " + String(moved) + ", настроек — " + String(count) + "."
        if left == 0 {
            try? manager.removeItem(at: box)
        } else {
            text += " Не перенеслось: " + String(left) + " — они остались в общей папке, нажмите «Принять» ещё раз."
        }
        return text
    }
}

extension SignatureInfo {
    /// The bundle ID the certificate is for (application-identifier without the team), when it differs from the
    /// bundle ID of this install: iOS then gives this install no folder in the picker.
    static let mismatch: String? = {
        guard let xml = entitlements(), let key = xml.range(of: "<key>application-identifier</key>"),
              let open = xml.range(of: "<string>", range: key.upperBound ..< xml.endIndex),
              let close = xml.range(of: "</string>", range: open.upperBound ..< xml.endIndex) else { return nil }
        let full = String(xml[open.upperBound ..< close.lowerBound])
        guard let dot = full.firstIndex(of: ".") else { return nil }
        let expected = String(full[full.index(after: dot)...])
        if expected.contains("*") || expected == Bundle.main.bundleIdentifier {
            return nil
        }
        return expected
    }()

    static var mismatchNote: String {
        guard let expected = mismatch else { return "" }
        return "Сертификат выдан для Bundle ID «" + expected + "», а у этой установки «"
            + (Bundle.main.bundleIdentifier ?? "?") + "»: из-за этого iOS не даёт ей папки. Установите Satori ещё раз "
            + "с Bundle ID «" + expected + "» и перенесите данные кнопкой «Перенос данных между установками»."
    }
}

/// Настройки → Anki → «Перенос данных между установками».
struct InstallTransferView: View {
    @Environment(\.dismiss) private var dismiss
    @State private var info = InstallTransfer.boxInfo()
    @State private var status = ""
    @State private var working = false
    @State private var confirmGive = false
    @State private var confirmTake = false
    @State private var finished = false

    private var own: String {
        Bundle.main.bundleIdentifier ?? "?"
    }

    var body: some View {
        NavigationView {
            List {
                Section {
                    Text("Эта установка: " + own)
                        .font(.callout.monospaced())
                    if !SignatureInfo.mismatchNote.isEmpty {
                        Text(SignatureInfo.mismatchNote)
                            .foregroundColor(.orange)
                    }
                } footer: {
                    Text(InstallTransferView.about)
                }
                if let info {
                    Section {
                        Button(takeTitle(info.from)) {
                            confirmTake = true
                        }
                        .disabled(working)
                    } footer: {
                        Text(takeNote(info.date))
                    }
                } else {
                    Section {
                        Button("Отдать данные другой установке", role: .destructive) {
                            confirmGive = true
                        }
                        .disabled(working)
                    } footer: {
                        Text("Всё из этой установки переедет в общую папку сертификата, откуда его примет другая "
                            + "установка Satori. Здесь данные пропадут.")
                    }
                }
                if working || !status.isEmpty {
                    Section {
                        if working {
                            HStack(spacing: 10) {
                                ProgressView()
                                Text("Переношу…")
                            }
                        }
                        if !status.isEmpty {
                            Text(status)
                        }
                    }
                }
            }
            .navigationTitle("Перенос данных")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Готово") {
                        dismiss()
                    }
                    .disabled(working)
                }
            }
            .alert("Отдать все данные?", isPresented: $confirmGive) {
                Button("Отдать", role: .destructive) {
                    run(give: true)
                }
                Button("Отмена", role: .cancel) {}
            } message: {
                Text("Данные уйдут из этой установки. Потом откройте другую установку Satori и примите их там.")
            }
            .alert("Принять данные?", isPresented: $confirmTake) {
                Button("Принять") {
                    run(give: false)
                }
                Button("Отмена", role: .cancel) {}
            } message: {
                Text("Совпадающие файлы этой установки заменятся перенесёнными.")
            }
            .alert("Готово", isPresented: $finished) {
                Button("Закрыть Satori") {
                    // the stores in memory still hold the data from before the move: they must not write it back
                    exit(0)
                }
            } message: {
                Text(status + " Satori закроется — откройте её снова.")
            }
        }
        .interactiveDismissDisabled(working)
    }

    static let about: String = "Две установки Satori с одним сертификатом (например, со старым Bundle ID и с Bundle ID "
        + "сертификата) видят общую папку App Group. Сначала в старой нажмите «Отдать», потом в новой — «Принять». "
        + "Слова, статистика и общие настройки у них и так одни."

    private func takeTitle(_ from: String) -> String {
        from == own ? "Вернуть данные сюда" : "Принять данные из «" + from + "»"
    }

    private func takeNote(_ date: Date) -> String {
        let when: String = date.formatted(date: .abbreviated, time: .shortened)
        return "Данные отданы " + when + ". Видео, ранобэ, грамматика, очередь майнинга и настройки переедут сюда; "
            + "совпадающие файлы заменятся. Выбранная здесь папка бэкапов останется."
    }

    private func run(give: Bool) {
        working = true
        status = ""
        Task { @MainActor in
            let result = await Task.detached(priority: .userInitiated) {
                give ? InstallTransfer.give() : InstallTransfer.take()
            }.value
            working = false
            status = result
            info = InstallTransfer.boxInfo()
            finished = true
        }
    }
}
