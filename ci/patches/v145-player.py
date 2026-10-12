# v1.45 (player): precise seeks; one precise re-sync seek when coming back from Anki or the background (instead of
# pause/play); the dictionary window inset from the rounded corners of the iOS 26 sheet; picture enhancement settings.
import pathlib

p = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = p.read_text(encoding="utf-8")


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


# 1) every seek lands on the exact time (decoded from the key frame, earlier frames are skipped)
s = once(s, 'o.hardwareDecode = d.object(forKey: "ykHWDecode") as? Bool ?? true',
         'o.hardwareDecode = d.object(forKey: "ykHWDecode") as? Bool ?? true\n                  o.isAccurateSeek = true',
         "accurate seek")

# 2) back from Anki: play, then one precise seek to the same position (the decoder lost its reference frames)
s = once(s, '''                for delay in [0.1, 0.4, 1.0] {
                    try? await Task.sleep(nanoseconds: UInt64(delay * 1_000_000_000))
                    showLookup = false
                    coordinator.playerLayer?.play()
                    if delay == 0.4 { restartOutput() }
                }
''', '''                for delay in [0.1, 0.4, 1.0] {
                    try? await Task.sleep(nanoseconds: UInt64(delay * 1_000_000_000))
                    showLookup = false
                    if delay == 0.1 {
                        coordinator.playerLayer?.play()
                    } else if delay == 0.4 {
                        resyncAfterReturn()
                    } else if coordinator.playerLayer?.player.isPlaying == false {
                        coordinator.playerLayer?.play()
                    }
                }
''', "anki return")

# 3) back from the background while playing: the same re-sync instead of pause/play
s = once(s, '''        Task { @MainActor in
            try? await Task.sleep(nanoseconds: 400_000_000)
            guard let current = coordinator.playerLayer, current.player.isPlaying else { return }
            current.pause()
            try? await Task.sleep(nanoseconds: 60_000_000)
            current.play()
        }
''', '''        Task { @MainActor in
            try? await Task.sleep(nanoseconds: 400_000_000)
            resyncAfterReturn()
        }
''', "background return")

s = once(s, '''    /// After a jump the picture can stay on one frame while the sound goes on.
''', '''    /// Back from another app the hardware decoder has lost its reference frames. One precise seek to the current
    /// position decodes again from the key frame up to this moment, and playback goes on at the same place.
    private func resyncAfterReturn() {
        let now = CACurrentMediaTime()
        guard now - lastResync > 1.5, let layer = coordinator.playerLayer else { return }
        lastResync = now
        let position = layer.player.currentPlaybackTime
        guard position > 0.5 else {
            layer.play()
            return
        }
        layer.seek(time: position, autoPlay: true) { _ in }
    }

    /// After a jump the picture can stay on one frame while the sound goes on.
''', "resync func")
s = once(s, '@State private var resumeHandled = false\n',
         '@State private var resumeHandled = false\n    @State private var lastResync: CFTimeInterval = 0\n', "resync state")

# 4) the dictionary window: a rounded card inside the sheet, away from the large corners of iOS 26
s = once(s, '''                YomikiriWebView(url: url)
                    .scrollable(false)
                    .overscroll(false)
                    .edgeToEdge(true)
                    .ignoresSafeArea(.keyboard)
''', '''                YomikiriWebView(url: url)
                    .scrollable(false)
                    .overscroll(false)
                    .edgeToEdge(true)
                    .ignoresSafeArea(.keyboard)
                    .clipShape(RoundedRectangle(cornerRadius: 22, style: .continuous))
                    .padding(.horizontal, 8)
                    .padding(.top, 10)
                    .padding(.bottom, 6)
''', "lookup card")

# 5) picture enhancement in the player settings
s = once(s, '@AppStorage("ykSmoothPacing") private var ykSmoothPacing = false',
         '@AppStorage("ykSmoothPacing") private var ykSmoothPacing = false\n'
         '              @AppStorage("ykDeband") private var ykDeband = false\n'
         '              @AppStorage("ykAnime4K") private var ykAnime4K = false\n'
         '              @AppStorage("ykSharpen") private var ykSharpen: Double = 0', "filter storage")
s = once(s, 'Section("Субтитры") {', '''Section("Улучшение картинки") {
                              Toggle("Убрать полосы в градиентах", isOn: $ykDeband)
                              Toggle("Восстановление линий (Anime4K)", isOn: $ykAnime4K)
                                  .disabled(!YKVideoFilters.anime4KAvailable)
                              HStack {
                                  Text("Резкость")
                                  Slider(value: $ykSharpen, in: 0...1, step: 0.1)
                              }
                              TimelineView(.periodic(from: .now, by: 1)) { _ in
                                  Text("Статус: " + (YKVideoFilters.isEnabled ? YKVideoFilters.status : "выключено"))
                                      .font(.caption)
                                      .foregroundColor(.secondary)
                              }
                          }
                          Section("Субтитры") {''', "filter section")

p.write_text(s, encoding="utf-8")
print("v1.45 player patch applied")
