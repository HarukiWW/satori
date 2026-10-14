
/// Tokens of subtitle lines: each line is tokenized once, and the players prepare the next line in the background, so
/// a new line shows without waiting for the tokenizer on the main thread.
final class SubtitleTokenCache: @unchecked Sendable {
    static let shared = SubtitleTokenCache()
    private let lock = NSLock()
    private var store: [String: [LookupToken]] = [:]
    private var order: [String] = []

    /// The text the subtitle bar shows: the line breaks of a cue become spaces.
    static func clean(_ text: String) -> String {
        text.replacingOccurrences(of: "\\N", with: " ")
            .replacingOccurrences(of: "\n", with: " ")
            .trimmingCharacters(in: .whitespaces)
    }

    func tokens(_ line: String) -> [LookupToken] {
        lock.lock()
        let saved = store[line]
        lock.unlock()
        if let saved {
            return saved
        }
        let result = autoreleasepool { NativeLookup.tokenize(line, charAt: 0).tokens }
        lock.lock()
        if store[line] == nil {
            order.append(line)
            if order.count > 300 {
                store[order.removeFirst()] = nil
            }
        }
        store[line] = result
        lock.unlock()
        return result
    }

    /// The next line, tokenized off the main thread.
    static func prefetch(_ text: String?) {
        guard let text else { return }
        let line = clean(text)
        guard !line.isEmpty else { return }
        Task.detached(priority: .utility) {
            _ = SubtitleTokenCache.shared.tokens(line)
        }
    }
}
