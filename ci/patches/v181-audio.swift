
// MARK: - Mining v1.81: the sound of the line as a real [sound:] of AnkiMobile

/// The clips of the lines, kept until AnkiMobile has them. AnkiMobile downloads a field that is a link to an audio
/// file into its own media, so the field gets a real [sound:] that plays after the word audio.
enum ClipFiles {
    static let port: UInt16 = 47611

    static var folder: URL {
        let base = FileManager.default.urls(for: .libraryDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("mining-sounds")
        try? FileManager.default.createDirectory(at: base, withIntermediateDirectories: true)
        return base
    }

    /// Only this phone reaches it (localhost: no network, no ATS).
    static func link(_ name: String) -> String {
        "http://localhost:" + String(port) + "/" + name
    }

    static func keep(_ data: Data) -> String? {
        let name = UUID().uuidString + ".m4a"
        guard (try? data.write(to: folder.appendingPathComponent(name))) != nil else { return nil }
        return name
    }

    /// Clips older than two days go, unless a note of the queue still has them.
    static func cleanUp(keeping notes: [String]) {
        let manager = FileManager.default
        let files = (try? manager.contentsOfDirectory(at: folder, includingPropertiesForKeys: [.contentModificationDateKey])) ?? []
        for file in files {
            let date = (try? file.resourceValues(forKeys: [.contentModificationDateKey]))?.contentModificationDate ?? Date()
            let name = file.lastPathComponent
            if Date().timeIntervalSince(date) > 2 * 86400, !notes.contains(where: { $0.contains(name) }) {
                try? manager.removeItem(at: file)
            }
        }
    }

    /// One request, one answer: "GET /<uuid>.m4a" gets the clip, anything else 404.
    static func serve(_ connection: NWConnection) {
        connection.start(queue: .global(qos: .userInitiated))
        connection.receive(minimumIncompleteLength: 1, maximumLength: 16384) { data, _, _, _ in
            let request = String(decoding: data ?? Data(), as: UTF8.self)
            let path = request.split(separator: " ").dropFirst().first.map { String($0) } ?? ""
            let name = String(path.drop(while: { $0 == "/" }))
            var body: Data? = nil
            // a clip name only: nothing else of the app can be asked for
            if name.range(of: "^[0-9A-F-]{36}\\.m4a$", options: .regularExpression) != nil {
                body = try? Data(contentsOf: folder.appendingPathComponent(name))
            }
            var header = "HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n"
            if let body {
                header = "HTTP/1.1 200 OK\r\nContent-Type: audio/mp4\r\nContent-Length: " + String(body.count) + "\r\n"
            }
            var response = Data((header + "Connection: close\r\n\r\n").utf8)
            if let body {
                response.append(body)
            }
            connection.send(content: response, completion: .contentProcessed { _ in
                connection.cancel()
            })
        }
    }
}

/// The server of the clips: started when a line is cut out or the queue is sent; it keeps going for the ~30 s iOS
/// gives after Satori opens AnkiMobile, which is when AnkiMobile downloads the clip.
@MainActor
final class ClipServer {
    static let shared = ClipServer()
    private var listener: NWListener? = nil
    private var background: UIBackgroundTaskIdentifier = .invalid
    private var observers: [NSObjectProtocol] = []

    func start() {
        if observers.isEmpty {
            let center = NotificationCenter.default
            observers.append(center.addObserver(forName: UIApplication.didEnterBackgroundNotification, object: nil,
                                                queue: .main) { _ in
                Task { @MainActor in
                    ClipServer.shared.holdOn()
                }
            })
            observers.append(center.addObserver(forName: UIApplication.willEnterForegroundNotification, object: nil,
                                                queue: .main) { _ in
                Task { @MainActor in
                    ClipServer.shared.letGo()
                }
            })
            ClipFiles.cleanUp(keeping: MiningQueue.shared.entries.map { $0.url })
        }
        guard listener == nil, let port = NWEndpoint.Port(rawValue: ClipFiles.port) else { return }
        let parameters = NWParameters.tcp
        parameters.requiredInterfaceType = .loopback
        parameters.allowLocalEndpointReuse = true
        guard let created = try? NWListener(using: parameters, on: port) else { return }
        created.newConnectionHandler = { connection in
            ClipFiles.serve(connection)
        }
        created.stateUpdateHandler = { state in
            switch state {
            case .failed, .cancelled:
                Task { @MainActor in
                    ClipServer.shared.listener = nil
                }
            default:
                break
            }
        }
        created.start(queue: .global(qos: .userInitiated))
        listener = created
    }

    private func holdOn() {
        guard listener != nil, background == .invalid else { return }
        background = UIApplication.shared.beginBackgroundTask(withName: "sentence audio") {
            Task { @MainActor in
                ClipServer.shared.letGo()
            }
        }
    }

    private func letGo() {
        guard background != .invalid else { return }
        UIApplication.shared.endBackgroundTask(background)
        background = .invalid
    }
}
