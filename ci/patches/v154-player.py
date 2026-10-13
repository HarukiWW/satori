# v1.54 (player): skip button for the opening / ending found from the MKV chapters (it jumps to the exact end of the
# chapter); seeking by a horizontal swipe on the picture with live frames (like nPlayer); the side buttons jump to the
# previous / next subtitle line; the next episode of the folder starts when a video ends.
import pathlib

hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


# ---------- state ----------
s = once(s, "    @State private var lastArtwork: CFTimeInterval = 0\n", """    @State private var lastArtwork: CFTimeInterval = 0
    @State private var swipeStart: Double? = nil
    @State private var swipeTarget: Double = 0
    @State private var swipeWasPlaying = false
    @State private var lastSwipeSeek: CFTimeInterval = 0
    @State private var skipSegments: [SkipSegment] = []
    @State private var segmentsChecked = false
    @State private var endHandled = false
""", "state")

# ---------- swipe on the picture ----------
s = once(s, '''                    Color.black.opacity(0.001)
                        .contentShape(Rectangle())
                        .onTapGesture {
                            if showLookup {
                                showLookup = false
                            } else {
                                toggleControls()
                            }
                        }
''', '''                    Color.black.opacity(0.001)
                        .contentShape(Rectangle())
                        .onTapGesture {
                            if showLookup {
                                showLookup = false
                            } else {
                                toggleControls()
                            }
                        }
                        .gesture(
                            DragGesture(minimumDistance: 15)
                                .onChanged { swipeChanged($0, width: geo.size.width) }
                                .onEnded { _ in swipeEnded() }
                        )
''', "swipe gesture")
s = once(s, '''                    subtitleLayer(rect, portrait: geo.size.height > geo.size.width)
                }
                .frame(width: geo.size.width, height: geo.size.height)''', '''                    subtitleLayer(rect, portrait: geo.size.height > geo.size.width)
                    swipeOverlay
                    skipButton
                }
                .frame(width: geo.size.width, height: geo.size.height)''', "overlays")

# ---------- side buttons: subtitle lines ----------
s = once(s, '                    circleButton("gobackward.15") { skip(-15) }\n',
         '                    circleButton("backward.end.fill") { skipLine(-1) }\n', "back button")
s = once(s, '                    circleButton("goforward.15") { skip(15) }\n',
         '                    circleButton("forward.end.fill") { skipLine(1) }\n', "forward button")

# ---------- every tick: chapters once, the end of the video ----------
s = once(s, "        updateLine()\n        recordWatching()\n        updateNowPlaying()\n    }\n",
         "        updateLine()\n        recordWatching()\n        updateNowPlaying()\n        detectSkipSegments()\n        checkEnd()\n    }\n", "tick")

s = once(s, "    private func skip(_ by: Double) {\n", '''    // MARK: - subtitle lines

    /// The next line, or back to the start of the current one (the previous one in its first second).
    /// Without subtitles: 15 s.
    private func skipLine(_ direction: Int) {
        let source = (usingExternal ? externalCues : embeddedCues)
            .filter { !$0.text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }
        guard !source.isEmpty else {
            skip(Double(direction) * 15)
            return
        }
        let starts = source.map { $0.start + subDelay }.sorted()
        let target = direction > 0 ? starts.first(where: { $0 > position + 0.25 }) : starts.last(where: { $0 < position - 1.0 })
        if let target {
            seek(to: min(max(target, 0), duration))
        } else if direction < 0 {
            seek(to: 0)
        }
    }

    // MARK: - swipe seeking

    /// A horizontal swipe moves through the video with live frames; the full width is about 90 s, faster when longer.
    private func swipeChanged(_ value: DragGesture.Value, width: CGFloat) {
        if swipeStart == nil {
            guard abs(value.translation.width) > abs(value.translation.height), duration > 0 else { return }
            swipeStart = position
            swipeWasPlaying = playing
            if playing {
                coordinator.playerLayer?.pause()
            }
        }
        guard let start = swipeStart else { return }
        let fraction = Double(value.translation.width / max(width, 1))
        let seconds = fraction * 90 * (1 + abs(fraction))
        swipeTarget = min(max(start + seconds, 0), duration)
        let now = CACurrentMediaTime()
        if now - lastSwipeSeek > 0.2 {
            lastSwipeSeek = now
            coordinator.playerLayer?.seek(time: swipeTarget, autoPlay: false) { _ in }
        }
    }

    private func swipeEnded() {
        guard swipeStart != nil else { return }
        let target = swipeTarget
        swipeStart = nil
        position = target
        coordinator.playerLayer?.seek(time: target, autoPlay: swipeWasPlaying) { _ in }
    }

    @ViewBuilder
    private var swipeOverlay: some View {
        if let start = swipeStart {
            let delta = swipeTarget - start
            Text((delta < 0 ? "« " : "» ") + clock(swipeTarget) + "  (" + (delta < 0 ? "−" : "+") + clock(abs(delta)) + ")")
                .font(.system(size: 22, weight: .semibold, design: .rounded))
                .monospacedDigit()
                .foregroundColor(.white)
                .padding(.horizontal, 18)
                .padding(.vertical, 10)
                .background(.ultraThinMaterial, in: Capsule())
                .allowsHitTesting(false)
        }
    }

    // MARK: - opening and ending

    /// The opening / ending from the MKV chapters: named ones first, otherwise a chapter of about 1:30 (the TV size of
    /// an anime song) in the first or the last part of the video.
    private func detectSkipSegments() {
        guard !segmentsChecked, duration > 60, position > 1, let player = coordinator.playerLayer?.player else { return }
        segmentsChecked = true
        let chapters = player.chapters.filter { $0.end > $0.start }
        var found: [SkipSegment] = []
        for chapter in chapters {
            let title = chapter.title.lowercased()
            let length = chapter.end - chapter.start
            let named: Bool?
            if title.range(of: #"(^|[^a-z])(op|opening|intro)([^a-z]|$)|オープニング"#, options: .regularExpression) != nil {
                named = true
            } else if title.range(of: #"(^|[^a-z])(ed|ending|credits?|outro)([^a-z]|$)|エンディング"#, options: .regularExpression) != nil {
                named = false
            } else {
                named = nil
            }
            if let opening = named, length >= 20, length <= 240 {
                found.append(SkipSegment(start: chapter.start, end: chapter.end, isOpening: opening))
            }
        }
        if found.isEmpty {
            for chapter in chapters {
                let length = chapter.end - chapter.start
                guard length >= 80, length <= 100 else { continue }
                if chapter.start < duration * 0.4, !found.contains(where: { $0.isOpening }) {
                    found.append(SkipSegment(start: chapter.start, end: chapter.end, isOpening: true))
                } else if chapter.start > duration * 0.6, !found.contains(where: { !$0.isOpening }) {
                    found.append(SkipSegment(start: chapter.start, end: chapter.end, isOpening: false))
                }
            }
        }
        skipSegments = found
    }

    private var currentSegment: SkipSegment? {
        skipSegments.first { position >= $0.start - 0.5 && position < $0.end - 2 }
    }

    @ViewBuilder
    private var skipButton: some View {
        if let segment = currentSegment, swipeStart == nil {
            Button {
                seek(to: min(segment.end, duration))
            } label: {
                Text(segment.isOpening ? "Пропустить опенинг" : "Пропустить эндинг")
                    .font(.system(size: 16, weight: .semibold))
                    .foregroundColor(.white)
                    .padding(.horizontal, 16)
                    .padding(.vertical, 10)
                    .background(.ultraThinMaterial, in: Capsule())
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .bottomTrailing)
            .padding(.trailing, 20)
            .padding(.bottom, 150)
        }
    }

    // MARK: - next episode

    /// At the end the next video of the folder (natural order: E2 before E10) is opened by the video list.
    private func checkEnd() {
        guard !endHandled, duration > 30, position >= duration - 0.6, !playing, swipeStart == nil else { return }
        endHandled = true
        let folder = url.deletingLastPathComponent()
        let videos = ((try? FileManager.default.contentsOfDirectory(at: folder, includingPropertiesForKeys: nil)) ?? [])
            .filter { VideoLibraryStore.isVideo($0.lastPathComponent) }
            .sorted { $0.lastPathComponent.localizedStandardCompare($1.lastPathComponent) == .orderedAscending }
        guard let index = videos.firstIndex(where: { $0.lastPathComponent == url.lastPathComponent }),
              index + 1 < videos.count else { return }
        NotificationCenter.default.post(name: Notification.Name("yomikiri.playNext"), object: videos[index + 1])
        dismiss()
    }

    private func skip(_ by: Double) {
''', "functions")

s = s.rstrip("\n") + """

/// An opening or an ending found in the chapters of a video.
struct SkipSegment {
    let start: Double
    let end: Double
    let isOpening: Bool
}
"""

# ---------- the list opens the next episode ----------
s = once(s, "    @State private var pendingDelete: VideoLibraryStore.Item? = nil\n",
         "    @State private var pendingDelete: VideoLibraryStore.Item? = nil\n    @State private var nextVideo: URL? = nil\n", "list state")
s = once(s, '        .onAppear {\n            library.reload()\n        }\n    }\n\n    @ViewBuilder\n    private func row(_ item: VideoLibraryStore.Item) -> some View {\n',
         '''        .background(
            NavigationLink(destination: nextDestination,
                           isActive: Binding(get: { nextVideo != nil }, set: { if !$0 { nextVideo = nil } })) {
                EmptyView()
            }
            .hidden()
        )
        .onReceive(NotificationCenter.default.publisher(for: Notification.Name("yomikiri.playNext"))) { note in
            guard let next = note.object as? URL,
                  next.deletingLastPathComponent().standardizedFileURL == library.folder.standardizedFileURL else { return }
            // the finished episode closes first
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.7) {
                nextVideo = next
            }
        }
        .onAppear {
            library.reload()
        }
    }

    @ViewBuilder
    private var nextDestination: some View {
        if let next = nextVideo {
            NativeVideoPlayerScreen(url: next)
        } else {
            EmptyView()
        }
    }

    @ViewBuilder
    private func row(_ item: VideoLibraryStore.Item) -> some View {
''', "list next")

hv.write_text(s, encoding="utf-8")
print("v1.54 player patch applied")
