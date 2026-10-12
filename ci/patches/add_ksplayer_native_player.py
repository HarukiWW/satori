# Moved out of build-ios-v141-player.yml, step "Add KSPlayer (SPM), Files access, native player with word lookup" (GitHub limits workflow files to 500 KB).
import pathlib, re, plistlib

# ---------- 1. Xcode project: KSPlayer (SPM, exact 2.3.4) for target "Yomikiri (iOS)" ----------
pb = pathlib.Path("src/safari/Yomikiri.xcodeproj/project.pbxproj")
s = pb.read_text(encoding="utf-8")
if "XCRemoteSwiftPackageReference" in s:
    print("pbxproj: already present")
else:
    PKG = "C6A1B2C3D4E5F60718293A01"
    PROD = "C6A1B2C3D4E5F60718293A02"
    BF = "C6A1B2C3D4E5F60718293A03"
    for uid in (PKG, PROD, BF):
        assert s.count(uid) == 0, "id collision: " + uid

    def once(text, old, new, label):
        n = text.count(old)
        assert n == 1, "pbxproj: %s found %d times" % (label, n)
        return text.replace(old, new)

    s = once(s, "/* Begin PBXBuildFile section */\n",
             "/* Begin PBXBuildFile section */\n"
             "\t\t%s /* KSPlayer in Frameworks */ = {isa = PBXBuildFile; productRef = %s /* KSPlayer */; };\n" % (BF, PROD),
             "PBXBuildFile begin")
    s = once(s,
             "\t\t\t\t697EFFAB2BA2A9E00035360C /* YomikiriTokenizer.framework in Frameworks */,\n",
             "\t\t\t\t697EFFAB2BA2A9E00035360C /* YomikiriTokenizer.framework in Frameworks */,\n"
             "\t\t\t\t%s /* KSPlayer in Frameworks */,\n" % BF,
             "iOS frameworks phase")
    s = once(s,
             '\t\t\tname = "Yomikiri (iOS)";\n\t\t\tproductName = "Yomikiri (iOS)";\n',
             '\t\t\tpackageProductDependencies = (\n\t\t\t\t%s /* KSPlayer */,\n\t\t\t);\n'
             '\t\t\tname = "Yomikiri (iOS)";\n\t\t\tproductName = "Yomikiri (iOS)";\n' % PROD,
             "iOS native target")
    s = once(s, "\t\t\tisa = PBXProject;\n",
             "\t\t\tisa = PBXProject;\n\t\t\tpackageReferences = (\n\t\t\t\t%s /* XCRemoteSwiftPackageReference \"KSPlayer\" */,\n\t\t\t);\n" % PKG,
             "PBXProject")
    sections = (
        "/* Begin XCRemoteSwiftPackageReference section */\n"
        "\t\t%s /* XCRemoteSwiftPackageReference \"KSPlayer\" */ = {\n"
        "\t\t\tisa = XCRemoteSwiftPackageReference;\n"
        "\t\t\trepositoryURL = \"https://github.com/kingslay/KSPlayer.git\";\n"
        "\t\t\trequirement = {\n"
        "\t\t\t\tkind = exactVersion;\n"
        "\t\t\t\tversion = 2.3.4;\n"
        "\t\t\t};\n"
        "\t\t};\n"
        "/* End XCRemoteSwiftPackageReference section */\n\n"
        "/* Begin XCSwiftPackageProductDependency section */\n"
        "\t\t%s /* KSPlayer */ = {\n"
        "\t\t\tisa = XCSwiftPackageProductDependency;\n"
        "\t\t\tpackage = %s /* XCRemoteSwiftPackageReference \"KSPlayer\" */;\n"
        "\t\t\tproductName = KSPlayer;\n"
        "\t\t};\n"
        "/* End XCSwiftPackageProductDependency section */\n\n"
    ) % (PKG, PROD, PKG)
    s = once(s, "/* Begin XCBuildConfiguration section */\n",
             sections + "/* Begin XCBuildConfiguration section */\n", "XCBuildConfiguration begin")
    pb.write_text(s, encoding="utf-8")
    print("pbxproj: KSPlayer 2.3.4 added to Yomikiri (iOS)")

# ---------- 1b. Xcode project: FFmpegKit product (C modules Libavformat/Libavcodec/Libavutil) ----------
pb2 = pathlib.Path("src/safari/Yomikiri.xcodeproj/project.pbxproj")
s2 = pb2.read_text(encoding="utf-8")
if "FFmpegKit" in s2:
    print("pbxproj: FFmpegKit already present")
else:
    FPKG = "C6A1B2C3D4E5F60718293B01"
    FPROD = "C6A1B2C3D4E5F60718293B02"
    FBF = "C6A1B2C3D4E5F60718293B03"
    for uid in (FPKG, FPROD, FBF):
        assert s2.count(uid) == 0, "id collision: " + uid

    def once2(text, old, new, label):
        n = text.count(old)
        assert n == 1, "pbxproj FFmpegKit: %s found %d times" % (label, n)
        return text.replace(old, new)

    s2 = once2(s2, "/* Begin PBXBuildFile section */\n",
               "/* Begin PBXBuildFile section */\n"
               "\t\t%s /* FFmpegKit in Frameworks */ = {isa = PBXBuildFile; productRef = %s /* FFmpegKit */; };\n" % (FBF, FPROD),
               "PBXBuildFile begin")
    s2 = once2(s2, "\t\t\t\t%s /* KSPlayer in Frameworks */,\n" % "C6A1B2C3D4E5F60718293A03",
               "\t\t\t\tC6A1B2C3D4E5F60718293A03 /* KSPlayer in Frameworks */,\n\t\t\t\t%s /* FFmpegKit in Frameworks */,\n" % FBF,
               "frameworks phase")
    s2 = once2(s2, "\t\t\t\tC6A1B2C3D4E5F60718293A02 /* KSPlayer */,\n",
               "\t\t\t\tC6A1B2C3D4E5F60718293A02 /* KSPlayer */,\n\t\t\t\t%s /* FFmpegKit */,\n" % FPROD,
               "packageProductDependencies")
    s2 = once2(s2, "\t\t\t\tC6A1B2C3D4E5F60718293A01 /* XCRemoteSwiftPackageReference \"KSPlayer\" */,\n",
               "\t\t\t\tC6A1B2C3D4E5F60718293A01 /* XCRemoteSwiftPackageReference \"KSPlayer\" */,\n\t\t\t\t%s /* XCRemoteSwiftPackageReference \"FFmpegKit\" */,\n" % FPKG,
               "packageReferences")
    s2 = once2(s2, "/* End XCRemoteSwiftPackageReference section */\n",
               "\t\t%s /* XCRemoteSwiftPackageReference \"FFmpegKit\" */ = {\n"
               "\t\t\tisa = XCRemoteSwiftPackageReference;\n"
               "\t\t\trepositoryURL = \"https://github.com/kingslay/FFmpegKit.git\";\n"
               "\t\t\trequirement = {\n"
               "\t\t\t\tkind = upToNextMajorVersion;\n"
               "\t\t\t\tminimumVersion = 6.1.3;\n"
               "\t\t\t};\n"
               "\t\t};\n"
               "/* End XCRemoteSwiftPackageReference section */\n" % FPKG,
               "end package refs")
    s2 = once2(s2, "/* End XCSwiftPackageProductDependency section */\n",
               "\t\t%s /* FFmpegKit */ = {\n"
               "\t\t\tisa = XCSwiftPackageProductDependency;\n"
               "\t\t\tpackage = %s /* XCRemoteSwiftPackageReference \"FFmpegKit\" */;\n"
               "\t\t\tproductName = FFmpegKit;\n"
               "\t\t};\n"
               "/* End XCSwiftPackageProductDependency section */\n" % (FPROD, FPKG),
               "end product deps")
    pb2.write_text(s2, encoding="utf-8")
    print("pbxproj: FFmpegKit linked to Yomikiri (iOS)")

# ---------- 2. Info.plist: make Documents visible in the Files app ----------
plist_path = pathlib.Path("src/safari/iOS (App)/Info.plist")
with plist_path.open("rb") as f:
    info = plistlib.load(f)
info["UIFileSharingEnabled"] = True
info["LSSupportsOpeningDocumentsInPlace"] = True
with plist_path.open("wb") as f:
    plistlib.dump(info, f, fmt=plistlib.FMT_XML)
print("Info.plist: file sharing enabled")

# ---------- 3. Swift ----------
hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
h = hv.read_text(encoding="utf-8")
if "NativeLookup" in h:
    print("swift: already patched")
else:
    m = re.search(r"^import SwiftUI\n", h, re.M)
    assert m, "HelpView.swift: 'import SwiftUI' not found"
    if "import KSPlayer" not in h:
        h = h[: m.end()] + "import AVFoundation\nimport KSPlayer\nimport UniformTypeIdentifiers\nimport UIKit\nimport ImageIO\nimport Vision\nimport Libavcodec\nimport Libavformat\nimport Libavutil\n" + h[m.end():]

    # 3a. video folder: Documents/Videos (visible in Files), migrate old App Group files once
    old_dir = (
        "    static func videosDirectory() -> URL? {\n"
        "        guard let base = try? getSharedDirectory() else { return nil }\n"
        "        let dir = base.appendingPathComponent(\"Videos\", isDirectory: true)\n"
        "        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)\n"
        "        return dir\n"
        "    }\n"
    )
    assert h.count(old_dir) == 1, "videosDirectory block not found exactly once"
    new_dir = r'''    static func videosDirectory() -> URL? {
        guard let docs = try? FileManager.default.url(
            for: .documentDirectory, in: .userDomainMask, appropriateFor: nil, create: true) else { return nil }
        let dir = docs.appendingPathComponent("Videos", isDirectory: true)
        if !FileManager.default.fileExists(atPath: dir.path) {
            try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
            // one-time move of files that were imported into the old App Group folder
            if let legacyBase = try? getSharedDirectory() {
                let legacy = legacyBase.appendingPathComponent("Videos", isDirectory: true)
                let items = (try? FileManager.default.contentsOfDirectory(at: legacy, includingPropertiesForKeys: nil)) ?? []
                for item in items {
                    try? FileManager.default.moveItem(at: item, to: dir.appendingPathComponent(item.lastPathComponent))
                }
            }
        }
        return dir
    }
'''
    h = h.replace(old_dir, new_dir, 1)

    # 3b. video tab: native player only (HTML player copied words instead of lookup)
    old_tab = (
        "struct VideoTabView: View {\n"
        "    var body: some View {\n"
        "        PlayerWebView()\n"
        "            .ignoresSafeArea(edges: .bottom)\n"
        "    }\n"
        "}\n"
    )
    assert h.count(old_tab) == 1, "VideoTabView block not found exactly once"
    new_tab = r'''struct VideoTabView: View {
    var body: some View {
        if #available(iOS 16.0, *) {
            NavigationView {
                NativeVideoListView()
            }
            .navigationViewStyle(.stack)
        } else {
            Text("Видео требует iOS 16 или новее.")
                .foregroundColor(.secondary)
                .padding()
        }
    }
}

// MARK: - Native video player (KSPlayer) with dictionary lookup on subtitle words

enum NativeVideoEngine {
    /// AVPlayer cannot play MKV, so MKV goes to KSPlayer's FFmpeg engine (KSMEPlayer).
    /// MP4/MOV use the system AVPlayer (hardware decoding, Picture in Picture).
    static func prepare(for url: URL) {
        switch url.pathExtension.lowercased() {
        case "mkv", "webm":
            KSOptions.firstPlayerType = KSMEPlayer.self
        default:
            KSOptions.firstPlayerType = KSAVPlayer.self
        }
        // subtitles are drawn by our own bar (with clickable words), not by KSPlayer
        SubtitleModel.textColor = .clear
        // decode/convert frames on a separate thread: fewer dropped frames on heavy MKV files
        KSOptions.asynchronousDecompression = true
    }

    static func isJapanese(_ code: String?) -> Bool {
        guard let c = code?.lowercased() else { return false }
        return c == "jpn" || c == "ja" || c == "jap" || c == "japanese"
    }

    /// The system language decides: Japanese UI -> Japanese audio and subtitles by default.
    static var prefersJapanese: Bool {
        Locale.preferredLanguages.first?.hasPrefix("ja") == true
    }

    /// KSPlayer overwrites coordinator.onStateChanged, so tracks are polled until they appear.
    /// Text Japanese subtitles win over bitmap ones (bitmap subtitles cannot be looked up).
    @MainActor
    /// Puts back the subtitle track of the last session. It does not depend on the system language.
    /// KSPlayer selects its own default track shortly after the start, so the choice is repeated a few
    /// times, unless the user picks something else in the meantime.
    static func restoreSavedSubtitle(coordinator: KSVideoPlayer.Coordinator, saved: String, key: String) async {
        for _ in 0..<60 {
            if !coordinator.subtitleModel.subtitleInfos.isEmpty { break }
            try? await Task.sleep(nanoseconds: 250_000_000)
        }
        let match = coordinator.subtitleModel.subtitleInfos.first { $0.subtitleID == saved }
        if !saved.isEmpty, match == nil { return }
        for _ in 0..<5 {
            try? await Task.sleep(nanoseconds: 700_000_000)
            if UserDefaults.standard.string(forKey: key) != saved { return }   // the user chose something else
            if let match {
                if coordinator.subtitleModel.selectedSubtitleInfo?.subtitleID != match.subtitleID {
                    coordinator.subtitleModel.selectedSubtitleInfo = match
                }
            } else if coordinator.subtitleModel.selectedSubtitleInfo != nil {
                coordinator.subtitleModel.selectedSubtitleInfo = nil
            }
        }
    }

    static func autoSelectJapanese(coordinator: KSVideoPlayer.Coordinator, pickSubtitle: Bool,
                                   excluded: Set<Int> = [], savedChoice: String? = nil) async {
        guard prefersJapanese else { return }
        var audioDone = false
        var subtitleDone = !pickSubtitle
        for _ in 0..<60 {                       // up to ~15 seconds
            if audioDone && subtitleDone { return }
            try? await Task.sleep(nanoseconds: 250_000_000)
            guard let layer = coordinator.playerLayer else { continue }
            if !audioDone {
                let audios = layer.player.tracks(mediaType: .audio)
                if !audios.isEmpty {
                    if let ja = audios.first(where: { isJapanese($0.languageCode) }) {
                        layer.player.select(track: ja)
                    }
                    audioDone = true
                }
            }
            if !subtitleDone {
                let infos = coordinator.subtitleModel.subtitleInfos.filter { info in
                    !((info as? FFmpegAssetTrack).map { excluded.contains(Int($0.trackID)) } ?? false)
                }
                if !infos.isEmpty {
                    let japanese = infos.filter { info in
                        guard let track = info as? FFmpegAssetTrack else { return false }
                        return isJapanese(track.languageCode)
                    }
                    let textJapanese = japanese.first { info in
                        guard let track = info as? FFmpegAssetTrack else { return false }
                        return !track.isImageSubtitle
                    }
                    if let saved = savedChoice {
                        // the choice of the last session wins; "" means no subtitles
                        if !saved.isEmpty,
                           let match = coordinator.subtitleModel.subtitleInfos.first(where: { $0.subtitleID == saved }) {
                            coordinator.subtitleModel.selectedSubtitleInfo = match
                            // KSPlayer picks its own default track right after: select the saved one again
                            try? await Task.sleep(nanoseconds: 2_000_000_000)
                            if coordinator.subtitleModel.selectedSubtitleInfo?.subtitleID != match.subtitleID {
                                coordinator.subtitleModel.selectedSubtitleInfo = nil
                                try? await Task.sleep(nanoseconds: 300_000_000)
                                coordinator.subtitleModel.selectedSubtitleInfo = match
                            }
                        }
                    } else if let pick = textJapanese ?? japanese.first {
                        coordinator.subtitleModel.selectedSubtitleInfo = pick
                        // a track chosen at load time is often not attached yet: once playback runs,
                        // select it again, the same as switching tracks by hand (unless the user changed it)
                        try? await Task.sleep(nanoseconds: 2_000_000_000)
                        if coordinator.subtitleModel.selectedSubtitleInfo?.subtitleID == pick.subtitleID {
                            coordinator.subtitleModel.selectedSubtitleInfo = nil
                            try? await Task.sleep(nanoseconds: 300_000_000)
                            coordinator.subtitleModel.selectedSubtitleInfo = pick
                        }
                    }
                    subtitleDone = true
                }
            }
        }
    }

    static func fileURL(_ name: String) -> URL {
        let dir = YomikiriMediaSchemeHandler.videosDirectory() ?? FileManager.default.temporaryDirectory
        return dir.appendingPathComponent(name)
    }

    /// External subtitle with the same name as the video: .srt / .ass / .ssa / .vtt
    static func sidecarSubtitle(for url: URL) -> URL? {
        let base = url.deletingPathExtension()
        for ext in ["srt", "ass", "ssa", "vtt"] {
            let candidate = base.appendingPathExtension(ext)
            if FileManager.default.fileExists(atPath: candidate.path) {
                return candidate
            }
        }
        return nil
    }

    /// Rectangle the video occupies inside `size` (aspect fit, like KSPlayer draws it).
    static func fitRect(in size: CGSize, content: CGSize) -> CGRect {
        let c = (content.width > 0 && content.height > 0) ? content : CGSize(width: 16, height: 9)
        let scale = min(size.width / c.width, size.height / c.height)
        let w = c.width * scale
        let h = c.height * scale
        return CGRect(x: (size.width - w) / 2, y: (size.height - h) / 2, width: w, height: h)
    }
}

/// A bitmap subtitle object (PGS/VobSub) with its position on the subtitle canvas.
struct PicturePart {
    let image: UIImage
    let origin: CGPoint
}

/// Where a video was stopped and whether it was watched to the end (kept per file name).
enum VideoProgress {
    static func position(_ name: String) -> Double {
        UserDefaults.standard.double(forKey: "resume." + name)
    }

    static func save(_ name: String, position: Double, duration: Double) {
        guard duration > 0 else { return }
        UserDefaults.standard.set(position, forKey: "resume." + name)
        if position >= duration * 0.92 {
            UserDefaults.standard.set(true, forKey: "watched." + name)
        }
    }

    static func isWatched(_ name: String) -> Bool {
        UserDefaults.standard.bool(forKey: "watched." + name)
    }

    static func clockText(_ seconds: Double) -> String {
        let total = Int(max(0, seconds))
        let h = total / 3600
        let m = (total % 3600) / 60
        let sec = total % 60
        return h > 0 ? String(format: "%d:%02d:%02d", h, m, sec) : String(format: "%d:%02d", m, sec)
    }
}

struct LookupToken: Identifiable {
    let id: Int
    let text: String
    let start: Int
    var base: String = ""
    var reading: String = ""
}

struct LookupEntry: Identifiable {
    let id: Int
    let headword: String
    let reading: String
    let pos: String
    let senses: [String]
}

enum NativeLookup {
    /// Calls the app's own dictionary backend (same engine as the web dictionary).
    /// `charAt` is a code point index inside `sentence`; `entries` are for the token at that index.
    static func tokenize(_ sentence: String, charAt: Int) -> (tokens: [LookupToken], entries: [LookupEntry]) {
        guard let backend = try? Backend.get(),
              let json = try? backend.tokenize(sentence: sentence, charAt: UInt32(max(0, charAt))),
              let data = json.data(using: .utf8),
              let root = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] else {
            return ([], [])
        }
        var tokens: [LookupToken] = []
        for (i, t) in ((root["tokens"] as? [[String: Any]]) ?? []).enumerated() {
            tokens.append(LookupToken(id: i,
                                      text: t["text"] as? String ?? "",
                                      start: t["start"] as? Int ?? 0,
                                      base: t["base"] as? String ?? "",
                                      reading: t["reading"] as? String ?? ""))
        }
        var entries: [LookupEntry] = []
        for (i, e) in ((root["entries"] as? [[String: Any]]) ?? []).enumerated() where (e["type"] as? String) == "word" {
            entries.append(parseEntry(e, id: i))
        }
        return (tokens, entries)
    }

    private static func parseEntry(_ e: [String: Any], id: Int) -> LookupEntry {
        let kanjis = ((e["kanjis"] as? [[String: Any]]) ?? []).compactMap { $0["kanji"] as? String }
        let readings = ((e["readings"] as? [[String: Any]]) ?? []).compactMap { $0["reading"] as? String }
        var pos: [String] = []
        var senses: [String] = []
        var number = 0
        for group in (e["groupedSenses"] as? [[String: Any]]) ?? [] {
            let groupPos = (group["pos"] as? [String]) ?? []
            if !groupPos.isEmpty {
                pos.append(groupPos.joined(separator: ", "))
            }
            for sense in (group["senses"] as? [[String: Any]]) ?? [] {
                let meanings = (sense["meanings"] as? [String]) ?? []
                if meanings.isEmpty { continue }
                number += 1
                senses.append("\(number). " + meanings.joined(separator: ", "))
            }
        }
        return LookupEntry(
            id: id,
            headword: kanjis.first ?? readings.first ?? "",
            reading: readings.first ?? "",
            pos: pos.joined(separator: " · "),
            senses: senses)
    }
}

enum SubtitleSync {
    static func readText(_ url: URL) -> String? {
        guard let data = try? Data(contentsOf: url), !data.isEmpty else { return nil }
        // byte order marks first: UTF-16 files (common for Japanese .srt) look like garbage as UTF-8
        if data.starts(with: [0xFF, 0xFE]) {
            return String(data: Data(data.dropFirst(2)), encoding: .utf16LittleEndian)
        }
        if data.starts(with: [0xFE, 0xFF]) {
            return String(data: Data(data.dropFirst(2)), encoding: .utf16BigEndian)
        }
        let bytes = data.starts(with: [0xEF, 0xBB, 0xBF]) ? Data(data.dropFirst(3)) : data
        return String(data: bytes, encoding: .utf8)
            ?? String(data: bytes, encoding: .shiftJIS)
            ?? String(data: bytes, encoding: .utf16)
    }

    /// Start time (seconds) of every cue in .srt / .vtt / .ass / .ssa text, sorted.
    static func cueStarts(_ text: String) -> [Double] {
        let ns = text as NSString
        let whole = NSRange(location: 0, length: ns.length)
        var starts: [Double] = []
        if text.contains("Dialogue:") {
            let pattern = #"^Dialogue:\s*[^,]*,\s*(\d+):(\d{2}):(\d{2})\.(\d{1,2})"#
            guard let re = try? NSRegularExpression(pattern: pattern, options: [.anchorsMatchLines]) else { return [] }
            for match in re.matches(in: text, range: whole) {
                starts.append(seconds(ns, match, digits: [1, 2, 3], fraction: 4))
            }
        } else {
            let pattern = #"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})\s*-->"#
            guard let re = try? NSRegularExpression(pattern: pattern) else { return [] }
            for match in re.matches(in: text, range: whole) {
                starts.append(seconds(ns, match, digits: [1, 2, 3], fraction: 4))
            }
        }
        return starts.sorted()
    }

    private static func seconds(_ ns: NSString, _ match: NSTextCheckingResult, digits: [Int], fraction: Int) -> Double {
        func part(_ i: Int) -> String { ns.substring(with: match.range(at: i)) }
        let frac = part(fraction)
        let f = (Double(frac) ?? 0) / pow(10, Double(frac.count))
        let h: Double = Double(part(digits[0])) ?? 0
        let mi: Double = Double(part(digits[1])) ?? 0
        let s: Double = Double(part(digits[2])) ?? 0
        let total: Double = h * 3600 + mi * 60 + s
        return total + f
    }

    private static func firstIndex(_ sorted: [Double], atLeast t: Double) -> Int {
        var lo = 0
        var hi = sorted.count
        while lo < hi {
            let mid = (lo + hi) / 2
            if sorted[mid] < t { lo = mid + 1 } else { hi = mid }
        }
        return lo
    }

    /// Delay d so that external[i] + d lands on a reference cue.
    /// Most matched cues wins; among equal counts the smallest average timing error wins.
    static func bestOffset(reference: [Double], external: [Double],
                           lo: Double = -30, hi: Double = 30, step: Double = 0.05,
                           tol: Double = 0.3) -> (delay: Double, matches: Int, total: Int)? {
        guard !reference.isEmpty, !external.isEmpty else { return nil }
        let ref = reference.sorted()
        let ext = external.sorted()
        let steps = Int(((hi - lo) / step).rounded())
        var bestCount = -1
        var bestMean = Double.infinity
        var bestDelay = 0.0
        for k in 0...steps {
            let d = lo + Double(k) * step
            var count = 0
            var errSum = 0.0
            for s in ext {
                let t = s + d
                let i = firstIndex(ref, atLeast: t)
                var err = Double.infinity
                if i < ref.count { err = min(err, ref[i] - t) }
                if i > 0 { err = min(err, t - ref[i - 1]) }
                if err <= tol {
                    count += 1
                    errSum += err
                }
            }
            let mean = count > 0 ? errSum / Double(count) : Double.infinity
            if count > bestCount
                || (count == bestCount && (mean < bestMean || (mean == bestMean && abs(d) < abs(bestDelay)))) {
                bestCount = count
                bestMean = mean
                bestDelay = d
            }
        }
        let delay = (bestDelay * 1000).rounded() / 1000
        return (delay, bestCount, ext.count)
    }
}

/// Lays its items out in rows and wraps to the next row when they do not fit.
@available(iOS 16.0, *)
struct FlowLayout: Layout {
    var spacing: CGFloat = 0

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let maxWidth = proposal.width ?? .infinity
        var x: CGFloat = 0
        var y: CGFloat = 0
        var rowHeight: CGFloat = 0
        var widest: CGFloat = 0
        for view in subviews {
            let size = view.sizeThatFits(.unspecified)
            if x > 0 && x + size.width > maxWidth {
                x = 0
                y += rowHeight + spacing
                rowHeight = 0
            }
            x += size.width + spacing
            rowHeight = max(rowHeight, size.height)
            widest = max(widest, x - spacing)
        }
        return CGSize(width: min(widest, maxWidth), height: y + rowHeight)
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        var x = bounds.minX
        var y = bounds.minY
        var rowHeight: CGFloat = 0
        for view in subviews {
            let size = view.sizeThatFits(.unspecified)
            if x > bounds.minX && x + size.width > bounds.maxX {
                x = bounds.minX
                y += rowHeight + spacing
                rowHeight = 0
            }
            view.place(at: CGPoint(x: x, y: y), anchor: .topLeading, proposal: ProposedViewSize(size))
            x += size.width + spacing
            rowHeight = max(rowHeight, size.height)
        }
    }
}

/// Frequency and JLPT tables of the web app (res/hl), read with the same hash and search as the web highlight.
@available(iOS 16.0, *)
enum HighlightData {
    struct Settings {
        var enabled = false
        var freq = true
        var dict = "main"
        var lo = 3000
        var hi = 8000
        var color = "#ff9f0a"
        var jlpt: [Int: Bool] = [:]

        /// the same settings as the web highlight, from the shared config
        static func load() -> Settings {
            var s = Settings()
            guard let json = (try? Storage.config.get())?.data(using: .utf8),
                  let root = (try? JSONSerialization.jsonObject(with: json)) as? [String: Any] else { return s }
            s.enabled = root["highlight.enabled"] as? Bool ?? false
            s.freq = root["highlight.freq"] as? Bool ?? true
            s.dict = root["highlight.dict"] as? String ?? "main"
            let a = (root["highlight.min"] as? NSNumber)?.intValue ?? 3000
            let b = (root["highlight.max"] as? NSNumber)?.intValue ?? 8000
            s.lo = max(1, min(a, b))
            s.hi = max(a, b)
            s.color = root["highlight.color"] as? String ?? "#ff9f0a"
            for n in 1...5 {
                s.jlpt[n] = root["highlight.jlpt.n\(n)"] as? Bool ?? false
            }
            return s
        }
    }

    static let jlptColors: [Int: String] = [5: "#34c759", 4: "#0a84ff", 3: "#d9a400", 2: "#ff9500", 1: "#ff3b30"]

    private static var jlptCache: [UInt32]?
    private static var freqCache: [(id: String, name: String, table: [UInt32])]?

    private static func resource(_ name: String, _ ext: String) -> URL? {
        Bundle.main.url(forResource: name, withExtension: ext, subdirectory: "res/hl")
    }

    /// little-endian 32-bit numbers of a table file
    private static func words(_ url: URL) -> [UInt32]? {
        guard let data = try? Data(contentsOf: url) else { return nil }
        var out: [UInt32] = []
        out.reserveCapacity(data.count / 4)
        var i = 0
        while i + 3 < data.count {
            out.append(UInt32(data[i]) | UInt32(data[i + 1]) << 8 | UInt32(data[i + 2]) << 16 | UInt32(data[i + 3]) << 24)
            i += 4
        }
        return out
    }

    private static func jlptTable() -> [UInt32]? {
        if jlptCache == nil, let url = resource("jlpt", "bin") {
            jlptCache = words(url)
        }
        return jlptCache
    }

    private static func freqTables() -> [(id: String, name: String, table: [UInt32])] {
        if let cached = freqCache { return cached }
        var loaded: [(id: String, name: String, table: [UInt32])] = []
        if let url = resource("index", "json"), let data = try? Data(contentsOf: url),
           let list = (try? JSONSerialization.jsonObject(with: data)) as? [[String: String]] {
            for entry in list {
                guard let file = entry["file"], let id = entry["id"], let name = entry["name"],
                      let fileURL = Bundle.main.url(forResource: (file as NSString).deletingPathExtension,
                                                    withExtension: "bin", subdirectory: "res/hl"),
                      let table = words(fileURL) else { continue }
                loaded.append((id: id, name: name, table: table))
            }
        }
        freqCache = loaded
        return loaded
    }

    /// FNV-1a over UTF-16 units, the same as charCodeAt in the web code
    static func hash(_ s: String) -> UInt32 {
        var h: UInt32 = 0x811C9DC5
        for unit in s.utf16 {
            h ^= UInt32(unit)
            h = h &* 0x01000193
        }
        return h
    }

    /// Position of the record with this key; records are `width` numbers, sorted by key.
    private static func find(_ t: [UInt32], width: Int, _ key: UInt32) -> Int? {
        var lo = 0
        var hi = t.count / width - 1
        while lo <= hi {
            let mid = (lo + hi) / 2
            let k = t[mid * width]
            if k == key { return mid * width }
            if k < key { lo = mid + 1 } else { hi = mid - 1 }
        }
        return nil
    }

    static func hiragana(_ s: String) -> String {
        var out = String.UnicodeScalarView()
        for sc in s.unicodeScalars {
            if (0x30A1...0x30F6).contains(sc.value), let h = Unicode.Scalar(sc.value - 0x60) {
                out.append(h)
            } else {
                out.append(sc)
            }
        }
        return String(out)
    }

    static func jlptLevel(base: String, reading: String) -> Int {
        guard let t = jlptTable(),
              let i = find(t, width: 2, hash(base + "|" + reading)) ?? find(t, width: 2, hash(base)) else { return 0 }
        return Int(t[i + 1])
    }

    /// Rank in one frequency list, chosen the way the web does it (kana rank for kana-only words).
    static func rank(base: String, reading: String, dict: String) -> Int? {
        let tables = freqTables()
        let isWebNovel = { (name: String) in name.range(of: "webnovel", options: .caseInsensitive) != nil }
        var index = tables.firstIndex { $0.id == dict } ?? -1
        if index < 0 {
            index = dict == "wn"
                ? (tables.firstIndex { isWebNovel($0.name) } ?? -1)
                : (tables.firstIndex { !isWebNovel($0.name) } ?? -1)
        }
        guard index >= 0 else { return nil }
        let t = tables[index].table
        guard let i = find(t, width: 3, hash(base + "|" + reading)) ?? find(t, width: 3, hash(base)) else { return nil }
        let kanji = Int(t[i + 1])
        let kana = Int(t[i + 2])
        let kanaOnly = base.unicodeScalars.allSatisfy { (0x3040...0x30FF).contains($0.value) }
        let value = kanaOnly ? (kana > 0 ? kana : kanji) : (kanji > 0 ? kanji : kana)
        return value > 0 ? value : nil
    }

    static func color(hex: String) -> Color? {
        var h = hex.trimmingCharacters(in: CharacterSet(charactersIn: "#"))
        if h.count == 3 {
            h = h.map { "\($0)\($0)" }.joined()
        }
        guard h.count == 6, let v = UInt32(h, radix: 16) else { return nil }
        return Color(red: Double((v >> 16) & 0xFF) / 255,
                     green: Double((v >> 8) & 0xFF) / 255,
                     blue: Double(v & 0xFF) / 255)
    }

    /// Dictionary forms of the words added to Anki: the same list the extension reads (stats.v1).
    static func minedWords() -> Set<String> {
        guard let json = (try? Storage.stats.get())?.data(using: .utf8),
              let root = (try? JSONSerialization.jsonObject(with: json)) as? [String: Any],
              let days = root["days"] as? [String: Any] else { return [] }
        var words = Set<String>()
        for case let day as [String: Any] in days.values {
            for word in (day["mined"] as? [String]) ?? [] {
                words.insert(word)
            }
        }
        return words
    }

    /// Color of each word: the JLPT level color first, then the frequency color; the same rules as in Safari.
    static func colors(for tokens: [LookupToken]) -> [Int: Color] {
        let settings = Settings.load()
        guard settings.enabled else { return [:] }
        var result: [Int: Color] = [:]
        let mined = minedWords()
        for token in tokens where !token.base.isEmpty && !mined.contains(token.base) {
            let reading = hiragana(token.reading)
            let level = jlptLevel(base: token.base, reading: reading)
            if level > 0, settings.jlpt[level] == true, let hex = jlptColors[level], let c = color(hex: hex) {
                result[token.id] = c
            } else if settings.freq, let r = rank(base: token.base, reading: reading, dict: settings.dict),
                      r >= settings.lo, r <= settings.hi, let c = color(hex: settings.color) {
                result[token.id] = c
            }
        }
        return result
    }
}

@available(iOS 16.0, *)
struct SubtitleLookupBar: View {
    let line: String
    let onTap: (LookupToken) -> Void
    @State private var tokens: [LookupToken] = []
    @State private var tokenColors: [Int: Color] = [:]

    var body: some View {
        Group {
            if tokens.isEmpty {
                // no words could be split: the line itself is shown
                Text(line)
                    .font(.system(size: 22, weight: .medium))
                    .foregroundColor(.white)
                    .multilineTextAlignment(.center)
            } else {
                FlowLayout(spacing: 0) {
                    ForEach(tokens) { token in
                        Text(token.text)
                            .font(.system(size: 22, weight: .medium))
                            .foregroundColor(tokenColors[token.id] ?? .white)
                            .padding(.vertical, 4)
                            .padding(.horizontal, 2)
                            .contentShape(Rectangle())
                            .onTapGesture { onTap(token) }
                    }
                }
            }
        }
        .frame(maxWidth: .infinity)
        .padding(.horizontal, 12)
        .padding(.vertical, 6)
        .background(Color.black.opacity(0.55))
        .cornerRadius(10)
        .padding(.horizontal, 8)
        .onAppear { refresh(line) }
        .onChange(of: line) { newValue in refresh(newValue) }
    }

    private func refresh(_ text: String) {
        let result = NativeLookup.tokenize(text, charAt: 0).tokens
        tokens = result
        tokenColors = HighlightData.colors(for: result)
    }
}

@available(iOS 16.0, *)
struct LookupSheet: View {
    let word: String
    let entries: [LookupEntry]

    var body: some View {
        NavigationView {
            List {
                if entries.isEmpty {
                    Text("«\(word)» не найдено в словаре.")
                        .foregroundColor(.secondary)
                }
                ForEach(entries) { entry in
                    VStack(alignment: .leading, spacing: 6) {
                        Text(entry.headword)
                            .font(.title3.bold())
                        if !entry.reading.isEmpty && entry.reading != entry.headword {
                            Text(entry.reading)
                                .foregroundColor(.secondary)
                        }
                        if !entry.pos.isEmpty {
                            Text(entry.pos)
                                .font(.footnote)
                                .foregroundColor(.secondary)
                        }
                        ForEach(entry.senses, id: \.self) { sense in
                            Text(sense)
                        }
                    }
                    .padding(.vertical, 4)
                }
            }
            .navigationTitle(word)
            .navigationBarTitleDisplayMode(.inline)
        }
    }
}

@available(iOS 16.0, *)
struct NativeVideoPlayerScreen: View {
    let url: URL
    @Environment(\.dismiss) private var dismiss
    @StateObject private var coordinator = KSVideoPlayer.Coordinator()
    @State private var options = KSOptions()

    // playback, polled from the player
    @State private var playing = false
    @State private var position: Double = 0
    @State private var duration: Double = 0
    @State private var scrubTo: Double? = nil
    @State private var videoSize = CGSize.zero
    @State private var controlsVisible = true
    @State private var hideTask: Task<Void, Never>? = nil
    @State private var audioTracks: [MediaPlayerTrack] = []

    // subtitles
    @State private var line = ""                  // the line shown and searched
    @State private var kpSubtitle = ""            // text or OCR result from KSPlayer's track
    @State private var lastOCRKey = -1
    @State private var pictures: [PicturePart] = []
    @State private var embeddedCues: [EmbeddedSubtitles.Cue] = []
    @State private var externalCues: [EmbeddedSubtitles.Cue] = []
    @State private var externalURLs: [URL] = []   // added subtitle files, shown in the track list
    @State private var activeExternal: URL? = nil
    @State private var usingExternal = false
    @State private var trackKey = ""              // KSPlayer track we already reacted to
    @State private var loadToken = 0
    @State private var cueCache: [Int: [EmbeddedSubtitles.Cue]] = [:]
    @State private var subDelay: Double = 0
    @State private var extractMessage = ""
    @State private var syncMessage = ""

    // sheets and lookup
    @State private var showTracks = false
    @State private var showMenu = false
    @State private var showImporter = false
    @State private var showLookup = false
    @State private var lookupWord = ""

    private var delayKey: String { "subdelay." + url.lastPathComponent }
    private var subChoiceKey: String { "subchoice." + url.lastPathComponent }
    @State private var resumeHandled = false
    @AppStorage("sheetOpacity") private var sheetOpacity: Double = 1.0
    @State private var lastSavedPosition: Double = -1

    var body: some View {
        // the engine must be chosen before the player layer is created
        let _ = NativeVideoEngine.prepare(for: url)
        ZStack {
            GeometryReader { geo in
                let rect = NativeVideoEngine.fitRect(in: geo.size, content: videoSize)
                ZStack {
                    KSVideoPlayer(coordinator: coordinator, url: url, options: options)
                        .frame(width: geo.size.width, height: geo.size.height)
                    // a tap on the picture shows or hides the controls
                    Color.black.opacity(0.001)
                        .contentShape(Rectangle())
                        .onTapGesture { toggleControls() }
                    pictureLayer(rect)
                    subtitleLayer(rect, portrait: geo.size.height > geo.size.width)
                }
                .frame(width: geo.size.width, height: geo.size.height)
            }
            .ignoresSafeArea()
            // controls are inside the safe area: never under the status bar or the home indicator
            if controlsVisible {
                controlsLayer
            }
        }
        .toolbar(.hidden, for: .tabBar)
        .navigationBarHidden(true)
        .onDisappear {
            if resumeHandled {
                VideoProgress.save(url.lastPathComponent, position: position, duration: duration)
            }
        }
        .onReceive(Timer.publish(every: 0.1, on: .main, in: .common).autoconnect()) { _ in
            tick()
        }
        .onReceive(coordinator.subtitleModel.$parts) { parts in
            partsChanged(parts)
        }
        .task(id: url) {
            await loadSubtitles()
        }
        .sheet(isPresented: $showTracks) {
            tracksSheet
        }
        .sheet(isPresented: $showMenu) {
            menuSheet
        }
        .sheet(isPresented: $showLookup) {
            WordLookupSheet(text: lookupWord)
        }
        .onChange(of: showLookup) { shown in
            if !shown {
                coordinator.playerLayer?.play()
            }
        }
    }

    // MARK: - layers

    /// Bitmap subtitles are drawn like PGS renderers do: the subtitle canvas (the video size) is mapped onto
    /// the video rectangle, and each object is placed at its own position on that canvas.
    private func pictureLayer(_ rect: CGRect) -> some View {
        let canvas = videoSize.width > 0 ? videoSize.width : 1920
        let k = rect.width / canvas
        return ZStack(alignment: .topLeading) {
            ForEach(pictures.indices, id: \.self) { i in
                let part = pictures[i]
                Image(uiImage: part.image)
                    .resizable()
                    .frame(width: part.image.size.width * k, height: part.image.size.height * k)
                    .offset(x: part.origin.x * k, y: part.origin.y * k)
            }
        }
        .frame(width: rect.width, height: rect.height, alignment: .topLeading)
        .position(x: rect.midX, y: rect.midY)
        .allowsHitTesting(false)
    }

    private func subtitleLayer(_ rect: CGRect, portrait: Bool) -> some View {
        Group {
            if portrait {
                // portrait: the lines go under the picture, across the width of the video
                VStack(spacing: 6) {
                    if !line.isEmpty {
                        SubtitleLookupBar(line: line, onTap: { _ in openLookup() })
                    }
                    Spacer(minLength: 0)
                }
                .frame(width: rect.width, alignment: .top)
                .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
                .padding(.leading, rect.minX)
                .padding(.top, rect.maxY + 10)
            } else {
                VStack(spacing: 6) {
                    Spacer()
                    if !line.isEmpty {
                        SubtitleLookupBar(line: line, onTap: { _ in openLookup() })
                    }
                }
                .padding(.bottom, 26)
                .frame(width: rect.width, height: rect.height, alignment: .bottom)
                .position(x: rect.midX, y: rect.midY)
            }
        }
    }

    private var controlsLayer: some View {
        VStack {
            HStack(spacing: 12) {
                circleButton("xmark") { dismiss() }
                Text(url.lastPathComponent)
                    .font(.subheadline.weight(.semibold))
                    .foregroundColor(.white)
                    .lineLimit(1)
                    .truncationMode(.tail)
                    .frame(maxWidth: .infinity)
                    .shadow(color: .black.opacity(0.6), radius: 2)
            }
            .padding(.horizontal, 16)
            .padding(.top, 10)

            Spacer()

            VStack(spacing: 12) {
                progressBar
                HStack(spacing: 22) {
                    circleButton("captions.bubble") { showTracks = true }
                    Spacer()
                    circleButton("gobackward.15") { skip(-15) }
                    circleButton(playing ? "pause.fill" : "play.fill", size: 58) { togglePlay() }
                    circleButton("goforward.15") { skip(15) }
                    Spacer()
                    circleButton("ellipsis") { showMenu = true }
                }
            }
            .padding(.horizontal, 16)
            .padding(.bottom, 10)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private var progressBar: some View {
        let shown = scrubTo ?? position
        let fraction = duration > 0 ? min(max(shown / duration, 0), 1) : 0
        return VStack(spacing: 4) {
            GeometryReader { bar in
                ZStack(alignment: .leading) {
                    Capsule()
                        .fill(Color.white.opacity(0.3))
                        .frame(height: 4)
                    Capsule()
                        .fill(Color.white)
                        .frame(width: bar.size.width * fraction, height: 4)
                }
                .frame(height: 24)
                .contentShape(Rectangle())
                .gesture(
                    DragGesture(minimumDistance: 0)
                        .onChanged { value in
                            let f = min(max(value.location.x / max(bar.size.width, 1), 0), 1)
                            scrubTo = Double(f) * duration
                        }
                        .onEnded { _ in
                            if let target = scrubTo {
                                seek(to: target)
                            }
                            scrubTo = nil
                        }
                )
            }
            .frame(height: 24)
            HStack {
                Text(clock(shown))
                Spacer()
                Text(clock(duration))
            }
            .font(.caption2.monospacedDigit())
            .foregroundColor(.white.opacity(0.85))
        }
    }

    private func circleButton(_ symbol: String, size: CGFloat = 40,
                              action: @escaping () -> Void) -> some View {
        Button {
            action()
            scheduleHide()
        } label: {
            Image(systemName: symbol)
                .font(.system(size: size * 0.42, weight: .semibold))
                .foregroundColor(.white)
                .frame(width: size, height: size)
                .background(Color.black.opacity(0.45))
                .clipShape(Circle())
        }
    }

    // MARK: - sheets

    private var tracksSheet: some View {
        NavigationView {
            List {
                Section {
                    trackRow("Выкл", selected: !usingExternal && selectedEmbeddedID == nil) {
                        chooseNone()
                    }
                }
                if !embeddedTracks.isEmpty {
                    Section("Встроенные") {
                        ForEach(embeddedTracks, id: \.subtitleID) { track in
                            trackRow(trackTitle(track),
                                     selected: !usingExternal && selectedEmbeddedID == track.subtitleID) {
                                chooseEmbedded(track)
                            }
                        }
                    }
                }
                if !externalURLs.isEmpty {
                    Section("Добавленные") {
                        ForEach(externalURLs, id: \.self) { file in
                            trackRow(externalLabel(file),
                                     selected: usingExternal && activeExternal == file) {
                                chooseExternal(file)
                            }
                        }
                    }
                }
            }
            .navigationTitle("Субтитры")
            .navigationBarTitleDisplayMode(.inline)
        }
        .presentationDetents([.medium, .large])
    }

    private var menuSheet: some View {
        NavigationView {
            List {
                Section("Аудио") {
                    if audioTracks.isEmpty {
                        Text("Дорожек пока нет").foregroundColor(.secondary)
                    }
                    ForEach(audioTracks.indices, id: \.self) { i in
                        let track = audioTracks[i]
                        trackRow(audioTitle(track), selected: track.isEnabled) {
                            chooseAudio(track)
                        }
                    }
                }
                Section("Окна словаря") {
                    HStack {
                        Text("Прозрачность")
                        Spacer()
                        Text("\(Int(sheetOpacity * 100))%").foregroundColor(.secondary)
                    }
                    Slider(value: $sheetOpacity, in: 0.3...1.0, step: 0.05)
                }
                Section("Субтитры") {
                    Button("Добавить свои субтитры") { showImporter = true }
                    delayRow
                    Button("Подобрать задержку (Авто)") { autoSync() }
                    if !syncMessage.isEmpty {
                        Text(syncMessage).font(.caption).foregroundColor(.secondary)
                    }
                    if !extractMessage.isEmpty {
                        Text(extractMessage).font(.caption).foregroundColor(.secondary)
                    }
                }
            }
            .navigationTitle("Настройки")
            .navigationBarTitleDisplayMode(.inline)
        }
        .presentationDetents([.medium, .large])
        .onAppear {
            audioTracks = coordinator.playerLayer?.player.tracks(mediaType: .audio) ?? []
        }
        .sheet(isPresented: $showImporter) {
            DocumentPicker(onPick: { picked in
                showImporter = false
                addExternalSubtitle(picked)
            }, onCancel: {
                showImporter = false
            })
        }
    }

    private var delayRow: some View {
        HStack(spacing: 6) {
            delayButton("−0.5") { shiftDelay(-0.5) }
            delayButton("−0.1") { shiftDelay(-0.1) }
            Text(String(format: "%+.2f с", subDelay))
                .font(.callout.monospacedDigit())
                .lineLimit(1)
                .fixedSize()
                .frame(maxWidth: .infinity)
            delayButton("+0.1") { shiftDelay(0.1) }
            delayButton("+0.5") { shiftDelay(0.5) }
        }
    }

    /// Buttons keep their natural width: the labels never wrap onto two lines.
    private func delayButton(_ title: String, _ action: @escaping () -> Void) -> some View {
        Button(title, action: action)
            .buttonStyle(.bordered)
            .controlSize(.small)
            .lineLimit(1)
            .fixedSize()
    }

    private func trackRow(_ title: String, selected: Bool, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack {
                Text(title)
                    .foregroundColor(.primary)
                    .lineLimit(2)
                Spacer()
                if selected {
                    Image(systemName: "checkmark")
                        .foregroundColor(.accentColor)
                }
            }
        }
    }

    // MARK: - tracks

    private var embeddedTracks: [FFmpegAssetTrack] {
        coordinator.subtitleModel.subtitleInfos.compactMap { $0 as? FFmpegAssetTrack }
    }

    private var selectedEmbeddedID: String? {
        (coordinator.subtitleModel.selectedSubtitleInfo as? FFmpegAssetTrack)?.subtitleID
    }

    private func externalLabel(_ file: URL) -> String {
        let name = file.deletingPathExtension().lastPathComponent
        return name + " · " + file.pathExtension.uppercased()
    }

    private func trackTitle(_ track: FFmpegAssetTrack) -> String {
        let language = (track.languageCode ?? "").uppercased()
        let kind = track.isImageSubtitle ? "картинки" : "текст"
        return [language, track.name, kind].filter { !$0.isEmpty }.joined(separator: " · ")
    }

    private func audioTitle(_ track: MediaPlayerTrack) -> String {
        let language = (track.languageCode ?? "").uppercased()
        let title = [language, track.name].filter { !$0.isEmpty }.joined(separator: " · ")
        return title.isEmpty ? "Дорожка \(track.trackID)" : title
    }

    private func chooseNone() {
        UserDefaults.standard.set("", forKey: subChoiceKey)
        usingExternal = false
        activeExternal = nil
        coordinator.subtitleModel.selectedSubtitleInfo = nil
        showTracks = false
    }

    private func chooseEmbedded(_ track: FFmpegAssetTrack) {
        UserDefaults.standard.set(track.subtitleID, forKey: subChoiceKey)
        usingExternal = false
        activeExternal = nil
        coordinator.subtitleModel.selectedSubtitleInfo = track
        showTracks = false
    }

    private func chooseExternal(_ file: URL) {
        activeExternal = file
        UserDefaults.standard.set("file:" + file.lastPathComponent, forKey: subChoiceKey)
        externalCues = EmbeddedSubtitles.cues(fromFile: file)
        usingExternal = !externalCues.isEmpty
        coordinator.subtitleModel.selectedSubtitleInfo = nil
        showTracks = false
        syncMessage = externalCues.isEmpty
            ? "В файле не найдено реплик"
            : "Субтитры: \(externalCues.count) реплик"
    }

    private func chooseAudio(_ track: MediaPlayerTrack) {
        coordinator.playerLayer?.player.select(track: track)
        audioTracks = coordinator.playerLayer?.player.tracks(mediaType: .audio) ?? []
    }

    /// Follows the track chosen in KSPlayer: text -> cues from the file, picture -> OCR.
    @MainActor
    private func checkTrack() {
        let selected = coordinator.subtitleModel.selectedSubtitleInfo
        let key = selected.map { ($0 is FFmpegAssetTrack ? "e" : "x") + $0.subtitleID } ?? ""
        guard key != trackKey else { return }
        trackKey = key
        guard let selected else {
            embeddedCues = []
            return
        }
        guard let track = selected as? FFmpegAssetTrack else { return }
        usingExternal = false
        activeExternal = nil
        if track.isImageSubtitle {
            embeddedCues = []
            extractMessage = "дорожка картинками: текст распознаётся (OCR)"
            return
        }
        loadToken += 1
        let token = loadToken
        let index = Int(track.trackID)
        if let cached = cueCache[index] {
            // this track was read already in this session: no second pass over the file
            embeddedCues = cached
            extractMessage = trackMessage(cached.count)
            return
        }
        let videoURL = url
        Task { @MainActor in
            let cues = await Task.detached(priority: .utility) {
                EmbeddedSubtitles.extract(url: videoURL, streamIndex: index) ?? []
            }.value
            cueCache[index] = cues
            guard token == loadToken else { return }
            embeddedCues = cues
            extractMessage = trackMessage(cues.count)
        }
    }

    private func trackMessage(_ count: Int) -> String {
        count == 0 ? "в этой дорожке текста не найдено" : "субтитры из дорожки: \(count) реплик"
    }

    // MARK: - playback

    @MainActor
    private func tick() {
        checkTrack()
        if let layer = coordinator.playerLayer {
            let player = layer.player
            if playing != player.isPlaying {
                playing = player.isPlaying
            }
            if scrubTo == nil {
                position = player.currentPlaybackTime
            }
            if player.duration > 0, player.duration != duration {
                duration = player.duration
            }
            if !resumeHandled, duration > 0 {
                // start where the video was stopped last time
                resumeHandled = true
                let saved = VideoProgress.position(url.lastPathComponent)
                if saved > 10, saved < duration - 30 {
                    seek(to: saved)
                }
            }
            if resumeHandled, duration > 0, abs(position - lastSavedPosition) >= 5 {
                lastSavedPosition = position
                VideoProgress.save(url.lastPathComponent, position: position, duration: duration)
            }
            let size = player.naturalSize
            if size.width > 0, size.height > 0, size != videoSize {
                videoSize = size
            }
        }
        updateLine()
    }

    private func updateLine() {
        let t = position - subDelay
        let source = usingExternal ? externalCues : embeddedCues
        let next: String
        if source.isEmpty {
            next = kpSubtitle
        } else {
            next = source.filter { $0.start <= t && t < $0.end }.map { $0.text }.joined(separator: "\n")
        }
        if next != line {
            line = next
        }
    }

    @MainActor
    private func partsChanged(_ parts: [SubtitlePart]) {
        pictures = parts.compactMap { part in
            part.image.map { PicturePart(image: $0, origin: part.origin) }
        }
        let text = parts.compactMap { $0.text?.string }
            .joined(separator: " ")
            .trimmingCharacters(in: .whitespacesAndNewlines)
        if !text.isEmpty {
            kpSubtitle = text
        } else if let part = parts.first(where: { $0.image != nil }), let image = part.image {
            let key = Int((part.start * 100).rounded())
            if key != lastOCRKey {
                lastOCRKey = key
                SubtitleOCR.recognize(image) { recognized in
                    DispatchQueue.main.async {
                        if key == lastOCRKey {
                            kpSubtitle = recognized
                        }
                    }
                }
            }
        } else {
            kpSubtitle = ""
        }
    }

    private func togglePlay() {
        guard let layer = coordinator.playerLayer else { return }
        if layer.player.isPlaying {
            layer.pause()
        } else {
            layer.play()
        }
        playing = !playing
    }

    private func skip(_ by: Double) {
        seek(to: min(max(position + by, 0), duration))
    }

    private func seek(to time: Double) {
        position = time
        coordinator.playerLayer?.player.seek(time: time) { _ in }
    }

    private func clock(_ seconds: Double) -> String {
        guard seconds.isFinite, seconds > 0 else { return "0:00" }
        let total = Int(seconds)
        let h = total / 3600
        let m = (total % 3600) / 60
        let s = total % 60
        return h > 0 ? String(format: "%d:%02d:%02d", h, m, s) : String(format: "%d:%02d", m, s)
    }

    // MARK: - controls visibility

    private func toggleControls() {
        if controlsVisible {
            controlsVisible = false
            hideTask?.cancel()
        } else {
            controlsVisible = true
            scheduleHide()
        }
    }

    private func scheduleHide() {
        hideTask?.cancel()
        hideTask = Task { @MainActor in
            try? await Task.sleep(nanoseconds: 3_500_000_000)
            if !Task.isCancelled, playing {
                controlsVisible = false
            }
        }
    }

    // MARK: - loading, delay, import, lookup

    @MainActor
    private func loadSubtitles() async {
        subDelay = UserDefaults.standard.double(forKey: delayKey)
        if let sidecar = NativeVideoEngine.sidecarSubtitle(for: url) {
            externalURLs = [sidecar]
            activeExternal = sidecar
            externalCues = EmbeddedSubtitles.cues(fromFile: sidecar)
            usingExternal = !externalCues.isEmpty
            runAutoSync(file: sidecar, automatic: true)
        } else if let generated = generatedSubtitleURL() {
            // SRT made from the video's own picture track: same timings, text for lookup and mining
            externalURLs = [generated]
            activeExternal = generated
            externalCues = EmbeddedSubtitles.cues(fromFile: generated)
            usingExternal = !externalCues.isEmpty
        }
        extractMessage = "субтитры: выберите дорожку"
        let hasExternal = NativeVideoEngine.sidecarSubtitle(for: url) != nil || generatedSubtitleURL() != nil
        let videoURL = url
        let skipped = await Task.detached(priority: .utility) {
            EmbeddedSubtitles.nonDialogueStreams(url: videoURL)
        }.value
        // every subtitle file that belongs to this video (name.srt, name.ass, name.ja.srt ...) is listed
        let base = url.deletingPathExtension().lastPathComponent
        let folder = url.deletingLastPathComponent()
        let found = ((try? FileManager.default.contentsOfDirectory(at: folder, includingPropertiesForKeys: nil)) ?? [])
            .filter { $0.lastPathComponent.hasPrefix(base + ".")
                && ["srt", "ass", "ssa", "vtt"].contains($0.pathExtension.lowercased()) }
        for file in found where !externalURLs.contains(file) {
            externalURLs.append(file)
        }
        // the last choice comes back: an added file, or an embedded track ("" means no subtitles)
        let savedChoice = UserDefaults.standard.string(forKey: subChoiceKey)
        var restoredFile = false
        if let savedChoice, savedChoice.hasPrefix("file:") {
            let file = folder.appendingPathComponent(String(savedChoice.dropFirst(5)))
            if FileManager.default.fileExists(atPath: file.path) {
                chooseExternal(file)
                restoredFile = true
            }
        }
        // an embedded track chosen last time ("" = subtitles off); a missing file is no choice
        let embeddedChoice: String? = (savedChoice?.hasPrefix("file:") == true) ? nil : savedChoice
        await NativeVideoEngine.autoSelectJapanese(coordinator: coordinator,
                                                   pickSubtitle: !hasExternal && !restoredFile && embeddedChoice == nil,
                                                   excluded: skipped,
                                                   savedChoice: nil)
        if !restoredFile, let embeddedChoice {
            await NativeVideoEngine.restoreSavedSubtitle(coordinator: coordinator, saved: embeddedChoice,
                                                         key: subChoiceKey)
        }
    }

    private func generatedSubtitleURL() -> URL? {
        let file = url.deletingPathExtension().appendingPathExtension("ja.srt")
        return FileManager.default.fileExists(atPath: file.path) ? file : nil
    }

    private func shiftDelay(_ by: Double) {
        subDelay = ((subDelay + by) * 100).rounded() / 100
        applyDelay()
    }

    private func applyDelay() {
        UserDefaults.standard.set(subDelay, forKey: delayKey)
    }

    @MainActor
    private func autoSync() {
        guard let file = activeExternal else {
            syncMessage = "Сначала добавьте свои субтитры"
            return
        }
        runAutoSync(file: file, automatic: false)
    }

    /// Reference timings come from the video file itself: text cues of a text track when there is one,
    /// otherwise the packet times of a picture track (no decoding). Works without playing the video.
    @MainActor
    private func runAutoSync(file: URL, automatic: Bool) {
        if !automatic {
            syncMessage = "подбираю задержку…"
        }
        let video = url
        Task { @MainActor in
            let outcome = await Task.detached(priority: .utility) { () -> (reference: Int, result: (delay: Double, matches: Int, total: Int)?) in
                let reference = EmbeddedSubtitles.referenceStarts(url: video)
                guard reference.count >= 8 else { return (reference.count, nil) }
                let external = EmbeddedSubtitles.cues(fromFile: file).map { $0.start }
                return (reference.count, SubtitleSync.bestOffset(reference: reference, external: external))
            }.value
            guard let result = outcome.result, result.matches >= max(8, result.total / 2) else {
                if let result = outcome.result {
                    syncMessage = "Совпадений мало: \(result.matches) из \(result.total) (эталон \(outcome.reference) точек)"
                } else {
                    syncMessage = "Недостаточно данных для подбора: эталон \(outcome.reference) точек"
                }
                return
            }
            subDelay = result.delay
            applyDelay()
            syncMessage = String(format: "Подобрано: %+.2f с (совпало %d из %d)",
                                 result.delay, result.matches, result.total)
        }
    }

    @MainActor
    private func addExternalSubtitle(_ src: URL) {
        let access = src.startAccessingSecurityScopedResource()
        defer {
            if access { src.stopAccessingSecurityScopedResource() }
        }
        let ext = src.pathExtension.lowercased()
        guard ["srt", "ass", "ssa", "vtt"].contains(ext) else {
            syncMessage = "Поддерживаются .srt, .ass, .ssa и .vtt"
            return
        }
        // saved next to the video under the video's name: it is picked up automatically next time
        let dest = url.deletingPathExtension().appendingPathExtension(ext)
        do {
            if FileManager.default.fileExists(atPath: dest.path) {
                try FileManager.default.removeItem(at: dest)
            }
            try FileManager.default.copyItem(at: src, to: dest)
        } catch {
            syncMessage = "Не удалось скопировать субтитры: \(error.localizedDescription)"
            return
        }
        if !externalURLs.contains(dest) {
            externalURLs.append(dest)
        }
        chooseExternal(dest)
        runAutoSync(file: dest, automatic: true)
        if externalCues.isEmpty {
            let raw = SubtitleSync.readText(dest) ?? ""
            let firstLine = raw.components(separatedBy: .newlines)
                .first { !$0.trimmingCharacters(in: .whitespaces).isEmpty } ?? ""
            syncMessage = "В файле не найдено реплик: символов \(raw.count), первая строка: «\(String(firstLine.prefix(40)))»"
        }
    }

    private func openLookup() {
        lookupWord = line
        coordinator.playerLayer?.pause()
        playing = false
        showLookup = true
    }
}

/// Text subtitles read straight from the file, ahead of playback.
/// Packets of the subtitle track already contain the text (SRT, ASS/SSA, mov_text, WebVTT),
/// so no decoder is needed. Bitmap tracks (PGS, VobSub) have no text and are not read here.
enum EmbeddedSubtitles {
    struct Cue {
        let start: Double
        let end: Double
        let text: String
    }

    static func extract(url: URL, streamIndex: Int? = nil,
                        preferredLanguages: [String] = ["jpn", "ja", "jap"],
                        progress: ((Double) -> Void)? = nil) -> [Cue]? {
        var opened: UnsafeMutablePointer<AVFormatContext>? = nil
        guard avformat_open_input(&opened, url.path, nil, nil) == 0, let fmt = opened else { return nil }
        defer {
            var closing: UnsafeMutablePointer<AVFormatContext>? = fmt
            avformat_close_input(&closing)
        }
        guard avformat_find_stream_info(fmt, nil) >= 0, let streams = fmt.pointee.streams else { return nil }
        let count = Int(fmt.pointee.nb_streams)

        // choose a text subtitle track: Japanese first, then any other text track
        var target: Int? = nil
        if let wanted = streamIndex {
            // the track the user chose in KSPlayer's subtitle menu
            if wanted >= 0, wanted < count, let st = streams[wanted], let par = st.pointee.codecpar,
               par.pointee.codec_type == AVMEDIA_TYPE_SUBTITLE, isTextCodec(par.pointee.codec_id) {
                target = wanted
            }
        } else {
            var targetIsPreferred = false
            for i in 0..<count {
                guard let st = streams[i], let par = st.pointee.codecpar else { continue }
                guard par.pointee.codec_type == AVMEDIA_TYPE_SUBTITLE, isTextCodec(par.pointee.codec_id) else { continue }
                let preferred = preferredLanguages.contains(language(of: st))
                if target == nil || (preferred && !targetIsPreferred) {
                    target = i
                    targetIsPreferred = preferred
                }
            }
        }
        guard let index = target, let stream = streams[index], let par = stream.pointee.codecpar else { return nil }
        let codec = par.pointee.codec_id
        let timeBase = av_q2d(stream.pointee.time_base)
        // only the subtitle track is read: the other streams are skipped by the demuxer
        for i in 0..<count where i != index {
            streams[i]?.pointee.discard = AVDISCARD_ALL
        }

        guard let packet = av_packet_alloc() else { return nil }
        defer {
            var freed: UnsafeMutablePointer<AVPacket>? = packet
            av_packet_free(&freed)
        }
        var cues: [Cue] = []
        let fileSize = Double((try? FileManager.default.attributesOfItem(atPath: url.path)[.size] as? Int) ?? 0)
        var reported = 0.0
        while av_read_frame(fmt, packet) >= 0 {
            defer { av_packet_unref(packet) }
            guard Int(packet.pointee.stream_index) == index, let data = packet.pointee.data else { continue }
            if let progress, fileSize > 0, let pb = fmt.pointee.pb {
                let fraction = min(1, Double(pb.pointee.pos) / fileSize)
                if fraction - reported >= 0.01 {
                    reported = fraction
                    progress(fraction)
                }
            }
            var ts = packet.pointee.pts
            if ts == Int64.min { ts = packet.pointee.dts }
            guard ts != Int64.min else { continue }
            let start = Double(ts) * timeBase
            let duration = Double(packet.pointee.duration) * timeBase
            let raw = Data(bytes: data, count: Int(packet.pointee.size))
            let text = cueText(raw, codec: codec)
            if !text.isEmpty {
                cues.append(Cue(start: start, end: duration > 0 ? start + duration : start + 4, text: text))
            }
        }
        return cues.sorted { $0.start < $1.start }
    }

    /// Cues of an external file (.srt, .vtt, .ass, .ssa).
    static func cues(fromFile url: URL) -> [Cue] {
        guard let text = SubtitleSync.readText(url) else { return [] }
        let lines = text.components(separatedBy: .newlines)
        var cues: [Cue] = []
        if text.contains("Dialogue:") {
            for line in lines where line.hasPrefix("Dialogue:") {
                let fields = line.dropFirst("Dialogue:".count)
                    .split(separator: ",", maxSplits: 9, omittingEmptySubsequences: false)
                guard fields.count == 10,
                      let start = seconds(String(fields[1])),
                      let end = seconds(String(fields[2])) else { continue }
                let body = clean(String(fields[9]))
                if !body.isEmpty { cues.append(Cue(start: start, end: end, text: body)) }
            }
        } else {
            // SRT and WebVTT, whole text in one pass (hours are optional in WebVTT)
            let t = #"(?:(\d{1,2}):)?(\d{2}):(\d{2})[,.](\d{1,3})"#
            guard let re = try? NSRegularExpression(pattern: t + #"\s*-->\s*"# + t + #"[^\r\n]*"#) else { return [] }
            let ns = text as NSString
            let matches = re.matches(in: text, range: NSRange(location: 0, length: ns.length))
            for (k, m) in matches.enumerated() {
                let start = timeValue(ns, m, from: 1)
                let end = timeValue(ns, m, from: 5)
                let bodyStart = m.range.location + m.range.length
                let bodyEnd = k + 1 < matches.count ? matches[k + 1].range.location : ns.length
                var lines = ns.substring(with: NSRange(location: bodyStart, length: bodyEnd - bodyStart))
                    .components(separatedBy: .newlines)
                    .filter { !$0.trimmingCharacters(in: .whitespaces).isEmpty }
                if let last = lines.last?.trimmingCharacters(in: .whitespaces),
                   !last.isEmpty, last.allSatisfy({ $0.isASCII && $0.isNumber }) {
                    lines.removeLast()          // number of the next cue
                }
                let body = clean(lines.joined(separator: "\n"))
                if !body.isEmpty { cues.append(Cue(start: start, end: end, text: body)) }
            }
        }
        return cues.sorted { $0.start < $1.start }
    }

    /// Picture subtitles (PGS): every display set is decoded with libavcodec, each picture is upscaled
    /// and read with Vision (Japanese). Cues get their times from the packets and the display times.
    static func pictureCues(url: URL, streamIndex index: Int, accurate: Bool = true,
                            progress: ((Double) -> Void)? = nil) -> [Cue] {
        var opened: UnsafeMutablePointer<AVFormatContext>? = nil
        guard avformat_open_input(&opened, url.path, nil, nil) == 0, let fmt = opened else { return [] }
        defer {
            var closing: UnsafeMutablePointer<AVFormatContext>? = fmt
            avformat_close_input(&closing)
        }
        guard avformat_find_stream_info(fmt, nil) >= 0, let streams = fmt.pointee.streams else { return [] }
        let count = Int(fmt.pointee.nb_streams)
        guard index >= 0, index < count, let stream = streams[index], let par = stream.pointee.codecpar,
              let decoder = avcodec_find_decoder(par.pointee.codec_id),
              let ctx = avcodec_alloc_context3(decoder) else { return [] }
        defer {
            var freed: UnsafeMutablePointer<AVCodecContext>? = ctx
            avcodec_free_context(&freed)
        }
        guard avcodec_parameters_to_context(ctx, par) >= 0, avcodec_open2(ctx, decoder, nil) >= 0 else { return [] }
        let timeBase = av_q2d(stream.pointee.time_base)
        for i in 0..<count where i != index {
            streams[i]?.pointee.discard = AVDISCARD_ALL
        }
        guard let packet = av_packet_alloc() else { return [] }
        defer {
            var freed: UnsafeMutablePointer<AVPacket>? = packet
            av_packet_free(&freed)
        }
        let fileSize = Double((try? FileManager.default.attributesOfItem(atPath: url.path)[.size] as? Int) ?? 0)
        var reported = 0.0
        var cues: [Cue] = []
        while av_read_frame(fmt, packet) >= 0 {
            defer { av_packet_unref(packet) }
            guard Int(packet.pointee.stream_index) == index else { continue }
            if let progress, fileSize > 0, let pb = fmt.pointee.pb {
                let fraction = min(1, Double(pb.pointee.pos) / fileSize)
                if fraction - reported >= 0.01 {
                    reported = fraction
                    progress(fraction)
                }
            }
            var sub = AVSubtitle()
            var got: Int32 = 0
            guard avcodec_decode_subtitle2(ctx, &sub, &got, packet) >= 0, got != 0 else { continue }
            defer { avsubtitle_free(&sub) }
            var pts = packet.pointee.pts
            if pts == Int64.min { pts = packet.pointee.dts }
            guard pts != Int64.min else { continue }
            let base = Double(pts) * timeBase
            let start = base + Double(sub.start_display_time) / 1000
            // 0xFFFFFFFF (or 0) means "no end given": the end becomes the next display set's start below
            let hasEnd = sub.end_display_time != UInt32.max && sub.end_display_time > 0
            let end = hasEnd ? base + Double(sub.end_display_time) / 1000 : start
            let text = recognizeRects(sub, accurate: accurate)
            if !text.isEmpty {
                cues.append(Cue(start: start, end: end, text: text))
            }
        }
        // a display set without an end time lasts until the next one (or 3 s at the end)
        for i in cues.indices where cues[i].end <= cues[i].start {
            let next = i + 1 < cues.count ? cues[i + 1].start : cues[i].start + 3
            cues[i] = Cue(start: cues[i].start, end: next, text: cues[i].text)
        }
        // the same text shown again and again (e.g. a music note) becomes one cue
        var merged: [Cue] = []
        for cue in cues.sorted(by: { $0.start < $1.start }) {
            if let last = merged.last, last.text == cue.text, cue.start - last.end <= 0.5 {
                merged[merged.count - 1] = Cue(start: last.start, end: max(last.end, cue.end), text: last.text)
            } else {
                merged.append(cue)
            }
        }
        return merged
    }

    /// Japanese text of one display set: every bitmap rect is read, top to bottom.
    private static func recognizeRects(_ sub: AVSubtitle, accurate: Bool) -> String {
        var pieces: [(y: Int32, text: String)] = []
        for i in 0..<Int(sub.num_rects) {
            guard let rect = sub.rects[i]?.pointee, rect.type == SUBTITLE_BITMAP,
                  let image = bitmapImage(rect, scale: accurate ? 2 : 1) else { continue }
            let text = readJapanese(image)
            if !text.isEmpty {
                pieces.append((rect.y, text))
            }
        }
        return pieces.sorted { $0.y < $1.y }.map { $0.text }.joined(separator: "\n")
    }

    /// PAL8 bitmap -> image over black, upscaled (accurate mode: 2x, Vision reads larger glyphs better).
    private static func bitmapImage(_ rect: AVSubtitleRect, scale: Int) -> CGImage? {
        let w = Int(rect.w)
        let h = Int(rect.h)
        guard w > 0, h > 0, let indices = rect.data.0, let palette = rect.data.1 else { return nil }
        let stride = Int(rect.linesize.0)
        var pixels = [UInt8](repeating: 0, count: w * h * 4)
        for y in 0..<h {
            for x in 0..<w {
                let index = Int(indices[y * stride + x])
                // palette entries are 0xAARRGGBB
                let argb = UnsafeRawPointer(palette).load(fromByteOffset: index * 4, as: UInt32.self)
                let a = Int((argb >> 24) & 0xFF)
                let o = (y * w + x) * 4
                pixels[o] = UInt8(Int((argb >> 16) & 0xFF) * a / 255)
                pixels[o + 1] = UInt8(Int((argb >> 8) & 0xFF) * a / 255)
                pixels[o + 2] = UInt8(Int(argb & 0xFF) * a / 255)
                pixels[o + 3] = 255
            }
        }
        let space = CGColorSpaceCreateDeviceRGB()
        let noAlpha = CGBitmapInfo(rawValue: CGImageAlphaInfo.noneSkipLast.rawValue)
        guard let provider = CGDataProvider(data: Data(pixels) as CFData),
              let small = CGImage(width: w, height: h, bitsPerComponent: 8, bitsPerPixel: 32,
                                  bytesPerRow: w * 4, space: space, bitmapInfo: noAlpha,
                                  provider: provider, decode: nil, shouldInterpolate: false,
                                  intent: .defaultIntent) else { return nil }
        guard let context = CGContext(data: nil, width: w * scale, height: h * scale, bitsPerComponent: 8,
                                      bytesPerRow: 0, space: space, bitmapInfo: noAlpha.rawValue) else { return nil }
        context.interpolationQuality = .high
        context.draw(small, in: CGRect(x: 0, y: 0, width: w * scale, height: h * scale))
        return context.makeImage()
    }

    /// Japanese text of one picture: horizontal lines (vertical text is not read).
    /// The fast mode uses the same recognizer: Vision's fast recognizer does not handle Japanese.
    private static func readJapanese(_ image: CGImage) -> String {
        recognize(image, orientation: .up)
    }

    private static func recognize(_ image: CGImage, orientation: CGImagePropertyOrientation) -> String {
        let request = VNRecognizeTextRequest()
        request.recognitionLanguages = ["ja-JP"]
        request.recognitionLevel = .accurate
        request.usesLanguageCorrection = false
        let handler = VNImageRequestHandler(cgImage: image, orientation: orientation, options: [:])
        guard (try? handler.perform([request])) != nil else { return "" }
        // Vision's origin is bottom-left: the top lines come first
        let lines = (request.results ?? []).sorted { $0.boundingBox.minY > $1.boundingBox.minY }
        return lines.compactMap { $0.topCandidates(1).first?.string }.joined()
    }

    /// SRT text for cues (times in seconds, text may have several lines).
    static func srtText(_ cues: [Cue]) -> String {
        var out = ""
        for (i, cue) in cues.enumerated() {
            out += "\(i + 1)\n\(srtTime(cue.start)) --> \(srtTime(cue.end))\n\(cue.text)\n\n"
        }
        return out
    }

    private static func srtTime(_ seconds: Double) -> String {
        let ms = Int((max(0, seconds) * 1000).rounded())
        let h = ms / 3_600_000
        let m = (ms % 3_600_000) / 60_000
        let sec = (ms % 60_000) / 1000
        let frac = ms % 1000
        return String(format: "%02d:%02d:%02d,%03d", h, m, sec, frac)
    }

    struct SubStream {
        let index: Int
        let isText: Bool
        let language: String
    }

    static func subtitleStreams(url: URL) -> [SubStream] {
        var opened: UnsafeMutablePointer<AVFormatContext>? = nil
        guard avformat_open_input(&opened, url.path, nil, nil) == 0, let fmt = opened else { return [] }
        defer {
            var closing: UnsafeMutablePointer<AVFormatContext>? = fmt
            avformat_close_input(&closing)
        }
        guard avformat_find_stream_info(fmt, nil) >= 0, let streams = fmt.pointee.streams else { return [] }
        var result: [SubStream] = []
        for i in 0..<Int(fmt.pointee.nb_streams) {
            guard let st = streams[i], let par = st.pointee.codecpar,
                  par.pointee.codec_type == AVMEDIA_TYPE_SUBTITLE else { continue }
            result.append(SubStream(index: i, isText: isTextCodec(par.pointee.codec_id),
                                    language: language(of: st)))
        }
        return result
    }

    /// Start times of the subtitle track used as the timing reference for auto-sync.
    static func referenceStarts(url: URL) -> [Double] {
        let japanese = ["jpn", "ja", "jap"]
        let all = subtitleStreams(url: url)
        let skipped = nonDialogueStreams(url: url)
        let candidates = all.filter { !skipped.contains($0.index) }
        // the dialogue track has the most lines: signs and songs tracks are much shorter
        var best: [Double] = []
        var bestScore = -1.0
        for stream in (candidates.isEmpty ? all : candidates) {
            let starts = stream.isText
                ? (extract(url: url, streamIndex: stream.index) ?? []).map { $0.start }
                : packetStarts(url: url, streamIndex: stream.index)
            // a small preference for Japanese when two tracks are about the same length
            let score = Double(starts.count) * (japanese.contains(stream.language) ? 1.05 : 1.0)
            if score > bestScore {
                bestScore = score
                best = starts
            }
        }
        return best
    }

    /// Packet times of one track: no decoding, so it is fast even for picture tracks.
    static func packetStarts(url: URL, streamIndex index: Int) -> [Double] {
        var opened: UnsafeMutablePointer<AVFormatContext>? = nil
        guard avformat_open_input(&opened, url.path, nil, nil) == 0, let fmt = opened else { return [] }
        defer {
            var closing: UnsafeMutablePointer<AVFormatContext>? = fmt
            avformat_close_input(&closing)
        }
        guard avformat_find_stream_info(fmt, nil) >= 0, let streams = fmt.pointee.streams else { return [] }
        let count = Int(fmt.pointee.nb_streams)
        guard index >= 0, index < count, let stream = streams[index] else { return [] }
        let timeBase = av_q2d(stream.pointee.time_base)
        for i in 0..<count where i != index {
            streams[i]?.pointee.discard = AVDISCARD_ALL
        }
        guard let packet = av_packet_alloc() else { return [] }
        defer {
            var freed: UnsafeMutablePointer<AVPacket>? = packet
            av_packet_free(&freed)
        }
        var starts: [Double] = []
        while av_read_frame(fmt, packet) >= 0 {
            defer { av_packet_unref(packet) }
            guard Int(packet.pointee.stream_index) == index else { continue }
            var ts = packet.pointee.pts
            if ts == Int64.min { ts = packet.pointee.dts }
            if ts != Int64.min, let data = packet.pointee.data,
               isShowSet(data, Int(packet.pointee.size)) {
                starts.append(Double(ts) * timeBase)
            }
        }
        return starts.sorted()
    }

    /// PGS display set that shows an object. A clear set (no objects) only ends a subtitle.
    /// Anything that is not PGS is kept.
    private static func isShowSet(_ data: UnsafeMutablePointer<UInt8>, _ size: Int) -> Bool {
        var off = 0
        var sawSegment = false
        while off + 13 <= size {
            guard data[off] == 0x50, data[off + 1] == 0x47 else { return !sawSegment }
            sawSegment = true
            let type = data[off + 10]
            let length = Int(data[off + 11]) << 8 | Int(data[off + 12])
            if type == 0x16 {
                // composition segment: number of objects is the 11th payload byte
                let objects = off + 13 + 10
                return objects < size && data[objects] > 0
            }
            off += 13 + length
        }
        return !sawSegment
    }

    /// Subtitle streams whose title says they are not dialogue (romaji, karaoke, signs, songs).
    static func nonDialogueStreams(url: URL) -> Set<Int> {
        var opened: UnsafeMutablePointer<AVFormatContext>? = nil
        guard avformat_open_input(&opened, url.path, nil, nil) == 0, let fmt = opened else { return [] }
        defer {
            var closing: UnsafeMutablePointer<AVFormatContext>? = fmt
            avformat_close_input(&closing)
        }
        guard avformat_find_stream_info(fmt, nil) >= 0, let streams = fmt.pointee.streams else { return [] }
        let markers = ["romaji", "rōmaji", "karaoke", "sign", "song", "ローマ", "看板", "ソング"]
        var result = Set<Int>()
        for i in 0..<Int(fmt.pointee.nb_streams) {
            guard let st = streams[i], let par = st.pointee.codecpar,
                  par.pointee.codec_type == AVMEDIA_TYPE_SUBTITLE,
                  let entry = av_dict_get(st.pointee.metadata, "title", nil, 0),
                  let value = entry.pointee.value else { continue }
            let title = String(cString: value).lowercased()
            if markers.contains(where: { title.contains($0) }) {
                result.insert(i)
            }
        }
        return result
    }

    private static func isTextCodec(_ id: AVCodecID) -> Bool {
        [AV_CODEC_ID_SUBRIP, AV_CODEC_ID_ASS, AV_CODEC_ID_SSA, AV_CODEC_ID_MOV_TEXT, AV_CODEC_ID_WEBVTT].contains(id)
    }

    private static func language(of stream: UnsafeMutablePointer<AVStream>) -> String {
        guard let entry = av_dict_get(stream.pointee.metadata, "language", nil, 0),
              let value = entry.pointee.value else { return "" }
        return String(cString: value).lowercased()
    }

    private static func cueText(_ raw: Data, codec: AVCodecID) -> String {
        if codec == AV_CODEC_ID_MOV_TEXT {
            // mov_text: 2-byte big-endian length, then UTF-8 text
            guard raw.count > 2 else { return "" }
            let length = Int(raw[0]) << 8 | Int(raw[1])
            let end = min(raw.count, 2 + length)
            return clean(String(data: raw.subdata(in: 2..<end), encoding: .utf8) ?? "")
        }
        var text = String(data: raw, encoding: .utf8) ?? ""
        if codec == AV_CODEC_ID_ASS || codec == AV_CODEC_ID_SSA {
            // packet layout: ReadOrder,Layer,Style,Name,MarginL,MarginR,MarginV,Effect,Text
            let fields = text.split(separator: ",", maxSplits: 8, omittingEmptySubsequences: false)
            if fields.count == 9 { text = String(fields[8]) }
        }
        return clean(text)
    }

    /// Seconds from regex groups: optional hours, minutes, seconds, fraction; starting at group `from`.
    private static func timeValue(_ ns: NSString, _ m: NSTextCheckingResult, from g: Int) -> Double {
        func part(_ i: Int) -> String? {
            let r = m.range(at: i)
            return r.location == NSNotFound ? nil : ns.substring(with: r)
        }
        let h = Double(part(g) ?? "0") ?? 0
        let mi = Double(part(g + 1) ?? "0") ?? 0
        let s = Double(part(g + 2) ?? "0") ?? 0
        let frac = part(g + 3) ?? "0"
        let f = (Double(frac) ?? 0) / pow(10, Double(frac.count))
        return h * 3600 + mi * 60 + s + f
    }

    /// "00:01:02,250", "00:01:02.250", "1:02.250" -> seconds
    private static func seconds(_ raw: String) -> Double? {
        let parts = raw.replacingOccurrences(of: ",", with: ".")
            .split(separator: ":").map(String.init)
        guard let last = parts.last, var total = Double(last) else { return nil }
        var factor = 60.0
        for part in parts.dropLast().reversed() {
            guard let value = Double(part) else { return nil }
            total += value * factor
            factor *= 60
        }
        return total
    }

    private static func clean(_ raw: String) -> String {
        var out = raw.replacingOccurrences(of: "\\N", with: "\n")
            .replacingOccurrences(of: "\\n", with: " ")
        out = out.replacingOccurrences(of: "\\{[^}]*\\}", with: "", options: .regularExpression)
        out = out.replacingOccurrences(of: "<[^>]+>", with: "", options: .regularExpression)
        return out.trimmingCharacters(in: .whitespacesAndNewlines)
    }
}

/// Bitmap subtitles have no text: Japanese text is read from the picture with Vision.
enum SubtitleOCR {
    static func recognize(_ image: UIImage, completion: @escaping (String) -> Void) {
        let size = image.size
        let format = UIGraphicsImageRendererFormat.default()
        format.scale = 1
        // transparent areas confuse OCR: draw the subtitle on black first
        let flat = UIGraphicsImageRenderer(size: size, format: format).image { ctx in
            UIColor.black.setFill()
            ctx.fill(CGRect(origin: .zero, size: size))
            image.draw(in: CGRect(origin: .zero, size: size))
        }
        guard let cg = flat.cgImage else {
            completion("")
            return
        }
        let request = VNRecognizeTextRequest { request, _ in
            let observations = request.results as? [VNRecognizedTextObservation] ?? []
            completion(observations.compactMap { $0.topCandidates(1).first?.string }.joined())
        }
        request.recognitionLanguages = ["ja-JP"]
        request.recognitionLevel = .accurate
        request.usesLanguageCorrection = false
        DispatchQueue.global(qos: .userInitiated).async {
            try? VNImageRequestHandler(cgImage: cg, options: [:]).perform([request])
        }
    }
}

/// System file picker. asCopy: the chosen file is copied, no security-scoped access is needed.
struct DocumentPicker: UIViewControllerRepresentable {
    let onPick: (URL) -> Void
    let onCancel: () -> Void

    func makeCoordinator() -> Coordinator { Coordinator(onPick: onPick, onCancel: onCancel) }

    func makeUIViewController(context: Context) -> UIDocumentPickerViewController {
        let picker = UIDocumentPickerViewController(forOpeningContentTypes: [.item], asCopy: true)
        picker.delegate = context.coordinator
        return picker
    }

    func updateUIViewController(_ controller: UIDocumentPickerViewController, context: Context) {}

    final class Coordinator: NSObject, UIDocumentPickerDelegate {
        let onPick: (URL) -> Void
        let onCancel: () -> Void

        init(onPick: @escaping (URL) -> Void, onCancel: @escaping () -> Void) {
            self.onPick = onPick
            self.onCancel = onCancel
        }

        func documentPicker(_ controller: UIDocumentPickerViewController, didPickDocumentsAt urls: [URL]) {
            if let url = urls.first { onPick(url) }
        }

        func documentPickerWasCancelled(_ controller: UIDocumentPickerViewController) {
            onCancel()
        }
    }
}

/// Browser-like lookup: the app's dictionary page (tokens, entries, mining to Anki),
/// opened on the subtitle text, the same page the dictionary tab shows.
@available(iOS 16.0, *)
struct WordLookupSheet: View {
    let text: String
    @AppStorage("sheetOpacity") private var sheetOpacity: Double = 1.0

    /// the sheet itself is clear on iOS 16.4+, so the chosen opacity shows the video behind
    private struct SheetTransparency: ViewModifier {
        func body(content: Content) -> some View {
            if #available(iOS 16.4, *) {
                content.presentationBackground(.clear)
            } else {
                content
            }
        }
    }

    private var pageURL: URL? {
        let page = Bundle.main.url(forResource: "dictionary", withExtension: "html", subdirectory: "res")
        return page?.withPathComponents([
            URLQueryItem(name: "context", value: "app"),
            URLQueryItem(name: "search", value: text),
        ])
    }

    var body: some View {
        Group {
            if let url = pageURL {
                YomikiriWebView(url: url)
                    .scrollable(false)
                    .overscroll(false)
                    .ignoresSafeArea(.keyboard)
            } else {
                Text("Страница словаря не найдена в приложении")
                    .foregroundColor(.secondary)
                    .padding()
            }
        }
        .presentationDetents([.medium, .large])
        .presentationDragIndicator(.visible)
        .opacity(sheetOpacity)
        .modifier(SheetTransparency())
    }
}

/// One folder of the video library: its files and folders, import, and the background subtitle job.
@available(iOS 16.0, *)
@MainActor
final class VideoLibraryStore: ObservableObject {
    struct Item: Identifiable {
        let url: URL
        let isFolder: Bool
        var id: String { url.path }
    }

    let folder: URL
    @Published var items: [Item] = []
    @Published var progress: [String: Double] = [:]
    @Published var status: [String: String] = [:]
    /// Video waiting for the user's choice of recognition mode.
    @Published var pendingChoice: URL? = nil

    private static let videoExtensions: Set<String> = ["mkv", "mp4", "mov", "m4v", "webm", "avi"]

    static func isVideo(_ name: String) -> Bool {
        videoExtensions.contains((name as NSString).pathExtension.lowercased())
    }

    init(folder: URL) {
        self.folder = folder
    }

    func reload() {
        let urls = (try? FileManager.default.contentsOfDirectory(
            at: folder, includingPropertiesForKeys: [.isDirectoryKey], options: [.skipsHiddenFiles])) ?? []
        items = urls.map { url -> Item in
            let isDir = (try? url.resourceValues(forKeys: [.isDirectoryKey]).isDirectory) ?? false
            return Item(url: url, isFolder: isDir)
        }
        .sorted { a, b in
            if a.isFolder != b.isFolder {
                return a.isFolder
            }
            return a.url.lastPathComponent.localizedStandardCompare(b.url.lastPathComponent) == .orderedAscending
        }
    }

    func createFolder(named name: String) {
        let clean = name.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !clean.isEmpty else { return }
        let dir = folder.appendingPathComponent(clean, isDirectory: true)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        reload()
    }

    func importVideo(_ src: URL) {
        let access = src.startAccessingSecurityScopedResource()
        defer {
            if access { src.stopAccessingSecurityScopedResource() }
        }
        var dest = folder.appendingPathComponent(src.lastPathComponent)
        if FileManager.default.fileExists(atPath: dest.path) {
            dest = folder.appendingPathComponent(String(UUID().uuidString.prefix(6)) + "_" + src.lastPathComponent)
        }
        do {
            try FileManager.default.copyItem(at: src, to: dest)
        } catch {
            status[src.lastPathComponent] = "не удалось скопировать"
            return
        }
        reload()
        if VideoLibraryStore.isVideo(dest.lastPathComponent) {
            askOrConvert(dest)
        }
    }

    /// Picture-only Japanese subtitles need OCR: the user chooses the mode first. Text tracks need no choice.
    private func askOrConvert(_ video: URL) {
        let name = video.lastPathComponent
        status[name] = "проверяю дорожки…"
        Task { @MainActor in
            let needsOCR = await Task.detached(priority: .utility) { () -> Bool in
                let japanese = ["jpn", "ja", "jap"]
                let streams = EmbeddedSubtitles.subtitleStreams(url: video)
                let hasText = streams.contains { $0.isText && japanese.contains($0.language) }
                let hasPicture = streams.contains { !$0.isText && japanese.contains($0.language) }
                return hasPicture && !hasText
            }.value
            if needsOCR {
                status[name] = nil
                pendingChoice = video
            } else {
                convertSubtitles(video, accurate: true)
            }
        }
    }

    func startPending(accurate: Bool) {
        guard let video = pendingChoice else { return }
        pendingChoice = nil
        convertSubtitles(video, accurate: accurate)
    }

    /// Background job for one video: reads its Japanese text track, or reads its Japanese pictures,
    /// and writes the result as SRT next to the video.
    func convertSubtitles(_ video: URL, accurate: Bool) {
        let name = video.lastPathComponent
        status[name] = "ищу японские субтитры…"
        progress[name] = 0
        let store = self
        Task { @MainActor in
            let text = await Task.detached(priority: .utility) { () -> String in
                let japanese = ["jpn", "ja", "jap"]
                let report: (Double) -> Void = { fraction in
                    Task { @MainActor in store.progress[name] = fraction }
                }
                let streams = EmbeddedSubtitles.subtitleStreams(url: video)
                let cues: [EmbeddedSubtitles.Cue]
                if let track = streams.first(where: { $0.isText && japanese.contains($0.language) }) {
                    cues = EmbeddedSubtitles.extract(url: video, streamIndex: track.index, progress: report) ?? []
                } else if let picture = streams.first(where: { !$0.isText && japanese.contains($0.language) }) {
                    cues = EmbeddedSubtitles.pictureCues(url: video, streamIndex: picture.index,
                                                         accurate: accurate, progress: report)
                } else {
                    return "японских субтитров нет"
                }
                guard !cues.isEmpty else { return "текста в дорожке не найдено" }
                let out = video.deletingPathExtension().appendingPathExtension("ja.srt")
                do {
                    try EmbeddedSubtitles.srtText(cues).write(to: out, atomically: true, encoding: .utf8)
                } catch {
                    return "не удалось записать SRT"
                }
                return "SRT готов: \(cues.count) реплик"
            }.value
            store.progress[name] = nil
            store.status[name] = text
            store.reload()
        }
    }
}

/// The video list of one folder. The root is the Videos folder; folders open their own list.
@available(iOS 16.0, *)
struct NativeVideoListView: View {
    let title: String
    @StateObject private var library: VideoLibraryStore
    @State private var showImporter = false
    @State private var showNewFolder = false
    @State private var newFolderName = ""

    init(folder: URL? = nil, title: String = "Видео") {
        let dir = folder ?? YomikiriMediaSchemeHandler.videosDirectory() ?? FileManager.default.temporaryDirectory
        _library = StateObject(wrappedValue: VideoLibraryStore(folder: dir))
        self.title = title
    }

    var body: some View {
        List {
            if library.items.isEmpty {
                Text("Пусто. Нажмите «+», чтобы добавить видео.")
                    .foregroundColor(.secondary)
            }
            ForEach(library.items) { item in
                row(item)
            }
        }
        .navigationTitle(title)
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                Button {
                    showImporter = true
                } label: {
                    Image(systemName: "plus")
                }
            }
            ToolbarItem(placement: .navigationBarTrailing) {
                Button {
                    showNewFolder = true
                } label: {
                    Image(systemName: "folder.badge.plus")
                }
            }
        }
        .sheet(isPresented: $showImporter) {
            DocumentPicker(onPick: { picked in
                showImporter = false
                library.importVideo(picked)
            }, onCancel: {
                showImporter = false
            })
        }
        .alert("Новая папка", isPresented: $showNewFolder) {
            TextField("Название", text: $newFolderName)
            Button("Создать") {
                library.createFolder(named: newFolderName)
                newFolderName = ""
            }
            Button("Отмена", role: .cancel) {
                newFolderName = ""
            }
        }
        .confirmationDialog("Японские субтитры-картинки",
                            isPresented: Binding(get: { library.pendingChoice != nil },
                                                 set: { if !$0 { library.pendingChoice = nil } }),
                            titleVisibility: .visible) {
            Button("Точный (медленнее)") { library.startPending(accurate: true) }
            Button("Быстрый") { library.startPending(accurate: false) }
            Button("Не распознавать", role: .cancel) { library.pendingChoice = nil }
        } message: {
            Text("Точный режим читает мелкий текст точнее. Быстрый заметно быстрее, но ошибок будет больше.")
        }
        .onAppear {
            library.reload()
        }
    }

    @ViewBuilder
    private func row(_ item: VideoLibraryStore.Item) -> some View {
        if item.isFolder {
            NavigationLink(destination: NativeVideoListView(folder: item.url, title: item.url.lastPathComponent)) {
                label(item)
            }
        } else if VideoLibraryStore.isVideo(item.url.lastPathComponent) {
            NavigationLink(destination: NativeVideoPlayerScreen(url: item.url)) {
                label(item)
            }
        } else {
            label(item)
        }
    }

    private func label(_ item: VideoLibraryStore.Item) -> some View {
        let name = item.url.lastPathComponent
        let ext = (name as NSString).pathExtension.uppercased()
        return HStack(spacing: 12) {
            Image(systemName: item.isFolder ? "folder" : symbol(for: name))
                .font(.title2)
                .foregroundColor(.accentColor)
                .frame(width: 32)
            VStack(alignment: .leading, spacing: 4) {
                Text(name).lineLimit(1)
                HStack(spacing: 8) {
                    if !item.isFolder {
                        Text(ext.isEmpty ? "—" : ext)
                            .font(.caption2.bold())
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(Color.secondary.opacity(0.2))
                            .cornerRadius(4)
                    }
                    if let text = library.status[name] ?? watchText(name, isFolder: item.isFolder) {
                        Text(text).font(.caption).foregroundColor(.secondary).lineLimit(1)
                    }
                }
                if let value = library.progress[name] {
                    ProgressView(value: value)
                }
            }
        }
    }

    private func watchText(_ name: String, isFolder: Bool) -> String? {
        guard !isFolder, VideoLibraryStore.isVideo(name) else { return nil }
        if VideoProgress.isWatched(name) {
            return "просмотрено"
        }
        let position = VideoProgress.position(name)
        return position > 10 ? "остановлено на \(VideoProgress.clockText(position))" : nil
    }

    private func symbol(for name: String) -> String {
        if VideoLibraryStore.isVideo(name) {
            return "film"
        }
        switch (name as NSString).pathExtension.lowercased() {
        case "srt", "ass", "ssa", "vtt":
            return "captions.bubble"
        default:
            return "doc"
        }
    }
}
'''
    h = h.replace(old_tab, new_tab, 1)
    hv.write_text(h, encoding="utf-8")
    print("swift: native player with lookup added")

# ---------- 4. MainView: Video tab between Dictionary and Settings ----------
mv = pathlib.Path("src/safari/iOS (App)/MainView.swift")
m_txt = mv.read_text(encoding="utf-8")
settings_block = (
    "            OptionsView()\n"
    "                .tabItem {\n"
    "                    Label(\"Настройки\", systemImage: \"gearshape.fill\")\n"
    "                }\n"
    "                .tag(Tabs.settings)\n"
)
video_block = (
    "            VideoTabView()\n"
    "                .tabItem {\n"
    "                    Label(\"Видео\", systemImage: \"play.rectangle.fill\")\n"
    "                }\n"
    "                .tag(Tabs.video)\n"
)
if m_txt.count(settings_block + video_block) == 1:
    m_txt = m_txt.replace(settings_block + video_block, video_block + settings_block, 1)
    mv.write_text(m_txt, encoding="utf-8")
    print("MainView: Video tab moved before Settings")
elif m_txt.count(video_block + settings_block) == 1:
    print("MainView: tab order already correct")
else:
    raise SystemExit("MainView: tab blocks not found as expected")
