
// MARK: - Satori v2.03: how this install is signed

/// What the signer gave this install: the entitlements in the code signature of the app, its provisioning profile and
/// the libraries it loads. Signers that rewrite entitlements (GBox, ESign) are known to break the system pickers; this
/// shows what they wrote.
enum SignatureInfo {
    static func report() -> String {
        let info = Bundle.main.infoDictionary ?? [:]
        var lines: [String] = []
        lines.append("Bundle ID: " + (Bundle.main.bundleIdentifier ?? "?"))
        lines.append("Версия: " + ((info["CFBundleShortVersionString"] as? String) ?? "?"))
        lines.append("Система: " + ProcessInfo.processInfo.operatingSystemVersionString)
        lines.append("LSSupportsOpeningDocumentsInPlace: " + value(info["LSSupportsOpeningDocumentsInPlace"]))
        lines.append("UIFileSharingEnabled: " + value(info["UIFileSharingEnabled"]))
        lines.append("Documents: " + FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0].path)
        lines.append("")
        lines.append("— Права в подписи —")
        lines.append(entitlements() ?? "не найдены")
        lines.append("")
        lines.append("— Профиль —")
        lines.append(profile())
        lines.append("")
        lines.append("— Библиотеки вне системы —")
        lines.append(libraries())
        return lines.joined(separator: "\n")
    }

    private static func value(_ item: Any?) -> String {
        guard let item else { return "нет" }
        return String(describing: item)
    }

    private static func executable() -> Data? {
        guard let url = Bundle.main.executableURL else { return nil }
        return try? Data(contentsOf: url, options: .alwaysMapped)
    }

    private static func le32(_ data: Data, _ at: Int) -> UInt32? {
        guard at >= 0, at + 4 <= data.count else { return nil }
        var result: UInt32 = 0
        for i in 0 ..< 4 {
            result |= UInt32(data[data.startIndex + at + i]) << UInt32(8 * i)
        }
        return result
    }

    private static func be32(_ data: Data, _ at: Int) -> UInt32? {
        le32(data, at)?.byteSwapped
    }

    /// where the arm64 code of the executable starts in the file
    private static func sliceStart(_ data: Data) -> Int? {
        guard let magic = le32(data, 0) else { return nil }
        if magic == 0xfeedfacf {
            return 0
        }
        guard magic == 0xbebafeca, let count = be32(data, 4) else { return nil }
        for i in 0 ..< Int(min(count, 16)) {
            let entry = 8 + i * 20
            guard let type = be32(data, entry), let offset = be32(data, entry + 8) else { return nil }
            if type == 0x0100000c {
                return Int(offset)
            }
        }
        return nil
    }

    /// the load commands of the arm64 code: the command and where it is
    private static func commands(_ data: Data, _ base: Int) -> [(command: UInt32, at: Int)] {
        guard le32(data, base) == 0xfeedfacf, let count = le32(data, base + 16) else { return [] }
        var result: [(command: UInt32, at: Int)] = []
        var at = base + 32
        for _ in 0 ..< Int(min(count, 1000)) {
            guard let command = le32(data, at), let size = le32(data, at + 4), size >= 8 else { break }
            result.append((command: command, at: at))
            at += Int(size)
        }
        return result
    }

    /// The entitlements XML of the code signature (LC_CODE_SIGNATURE → SuperBlob → blob 0xfade7171).
    static func entitlements() -> String? {
        guard let data = executable(), let base = sliceStart(data) else { return nil }
        for item in commands(data, base) where item.command == 0x1d {
            guard let offset = le32(data, item.at + 8) else { return nil }
            let blob = base + Int(offset)
            guard be32(data, blob) == 0xfade0cc0, let count = be32(data, blob + 8) else { return nil }
            for i in 0 ..< Int(min(count, 64)) {
                guard let start = be32(data, blob + 16 + i * 8) else { break }
                let entry = blob + Int(start)
                guard be32(data, entry) == 0xfade7171, let length = be32(data, entry + 4), length > 8 else { continue }
                let begin = data.startIndex + entry + 8
                let end = data.startIndex + entry + Int(length)
                guard end <= data.endIndex else { return nil }
                return String(decoding: data[begin ..< end], as: UTF8.self)
            }
        }
        return nil
    }

    static func profile() -> String {
        guard let url = Bundle.main.url(forResource: "embedded", withExtension: "mobileprovision"),
              let data = try? Data(contentsOf: url) else { return "embedded.mobileprovision нет" }
        guard let start = data.range(of: Data("<?xml".utf8)),
              let end = data.range(of: Data("</plist>".utf8), in: start.lowerBound ..< data.endIndex) else {
            return "профиль не прочитан"
        }
        let slice = data[start.lowerBound ..< end.upperBound]
        let parsed = try? PropertyListSerialization.propertyList(from: slice, options: [], format: nil)
        guard let plist = parsed as? [String: Any] else { return "профиль не прочитан" }
        var lines: [String] = []
        lines.append("Имя: " + ((plist["Name"] as? String) ?? "?"))
        let team: String = (plist["TeamName"] as? String) ?? "?"
        let teamID: String = (plist["TeamIdentifier"] as? [String])?.joined(separator: ",") ?? ""
        lines.append("Команда: " + team + " " + teamID)
        if let date = plist["ExpirationDate"] as? Date {
            lines.append("Действует до: " + date.formatted(date: .abbreviated, time: .omitted))
        }
        lines.append("Все устройства (Enterprise): " + ((plist["ProvisionsAllDevices"] as? Bool) == true ? "да" : "нет"))
        lines.append("Устройств в профиле: " + String((plist["ProvisionedDevices"] as? [Any])?.count ?? 0))
        if let entitlements = plist["Entitlements"] as? [String: Any] {
            for key in entitlements.keys.sorted() {
                lines.append(key + " = " + value(entitlements[key]))
            }
        }
        return lines.joined(separator: "\n")
    }

    /// Libraries the executable loads from outside the system, and the Frameworks folder (an injected library shows).
    static func libraries() -> String {
        guard let data = executable(), let base = sliceStart(data) else { return "нет файла" }
        var names: [String] = []
        // LC_LOAD_DYLIB, LC_LOAD_WEAK_DYLIB, LC_REEXPORT_DYLIB
        let loading: [UInt32] = [0xc, 0x80000018, 0x8000001f]
        for item in commands(data, base) where loading.contains(item.command) {
            guard let offset = le32(data, item.at + 8) else { continue }
            var bytes: [UInt8] = []
            var i = item.at + Int(offset)
            while i < data.count, bytes.count < 300 {
                let byte = data[data.startIndex + i]
                if byte == 0 {
                    break
                }
                bytes.append(byte)
                i += 1
            }
            let name = String(decoding: bytes, as: UTF8.self)
            if !name.hasPrefix("/System/") && !name.hasPrefix("/usr/lib/") {
                names.append(name)
            }
        }
        let folder = Bundle.main.bundlePath + "/Frameworks"
        let frameworks = ((try? FileManager.default.contentsOfDirectory(atPath: folder)) ?? []).sorted()
        let loaded: String = names.isEmpty ? "—" : names.joined(separator: "\n")
        return loaded + "\nFrameworks: " + frameworks.joined(separator: ", ")
    }
}

/// Настройки → Anki → «Подпись приложения»: the report, to copy and send.
struct SignatureReportView: View {
    @Environment(\.dismiss) private var dismiss
    @State private var report = ""
    @State private var copied = false

    var body: some View {
        NavigationView {
            ScrollView {
                Text(report.isEmpty ? "Читаю подпись…" : report)
                    .font(.caption.monospaced())
                    .textSelection(.enabled)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding()
            }
            .navigationTitle("Подпись приложения")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Готово") {
                        dismiss()
                    }
                }
                ToolbarItem(placement: .primaryAction) {
                    Button(copied ? "Скопировано" : "Скопировать") {
                        UIPasteboard.general.string = report
                        copied = true
                    }
                    .disabled(report.isEmpty)
                }
            }
        }
        .task {
            report = await Task.detached(priority: .userInitiated) {
                SignatureInfo.report()
            }.value
        }
    }
}
