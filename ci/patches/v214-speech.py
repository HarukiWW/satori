# v2.14: subtitles from the sound of a video (iOS 26, on the device).
# - A video without subtitles (no file next to it, no Japanese track in it) gets them from its sound: the speech
#   recognition of iOS 26 (SpeechTranscriber) listens ahead of the playback in pieces of 90 s, from the place it plays
#   to the end, then the beginning; the lines show as soon as their piece is done, and the whole file is kept as
#   <name>.ja.srt for the next time. «Сделать субтитры из звука» in the player settings does it for any video.
# - YouTube is played by its own player: its sound is not given to the app, so it keeps its captions (2.13 groups
#   the automatic ones into phrases).
import pathlib


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


here = pathlib.Path(__file__).resolve().parent
hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")

s = once(s, "import AVFoundation\n", "import AVFoundation\nimport Speech\n", "import speech")
s = once(s, '''    @State private var lastRecovery: CFTimeInterval = 0
''', '''    @State private var lastRecovery: CFTimeInterval = 0
    /// the subtitles made from the sound (iOS 26)
    @State private var speechTask: Task<Void, Never>? = nil
''', "speech state")
s = once(s, '''                if coordinator.subtitleModel.selectedSubtitleInfo != nil {
                    coordinator.subtitleModel.selectedSubtitleInfo = nil
                    usingExternal = !externalCues.isEmpty
                    activeExternal = restored
                }
            }
        }
    }
''', '''                if coordinator.subtitleModel.selectedSubtitleInfo != nil {
                    coordinator.subtitleModel.selectedSubtitleInfo = nil
                    usingExternal = !externalCues.isEmpty
                    activeExternal = restored
                }
            }
        }
        startSpeechSubtitles(force: false)
    }

    /// Subtitles from the sound (iOS 26): by themselves when the video has none (no file, no Japanese track), or
    /// when asked in the settings.
    @MainActor
    private func startSpeechSubtitles(force: Bool) {
        guard #available(iOS 26.0, *) else {
            if force {
                syncMessage = "Субтитры из звука: нужна iOS 26"
            }
            return
        }
        if force {
            speechTask?.cancel()
            speechTask = nil
        }
        guard speechTask == nil, force || externalURLs.isEmpty else { return }
        let video = url
        speechTask = Task { @MainActor in
            if !force {
                let japanese = ["jpn", "ja", "jap"]
                let hasTrack = await Task.detached(priority: .utility) {
                    EmbeddedSubtitles.subtitleStreams(url: video).contains { japanese.contains($0.language) }
                }.value
                guard !hasTrack else { return }
            }
            // the length and the place of the playback, once the player knows them
            for _ in 0 ..< 20 where duration <= 0 {
                try? await Task.sleep(nanoseconds: 500_000_000)
            }
            guard !Task.isCancelled, duration > 0 else { return }
            await SpeechSubtitles.run(video: video, from: max(0, position - 2), duration: duration, report: { message in
                syncMessage = message
            }, update: { cues in
                externalCues = cues
                usingExternal = !cues.isEmpty
                activeExternal = nil
            })
        }
    }
''', "speech start")
s = once(s, '''                    Button("Найти японские субтитры на Jimaku") { searchJimaku() }
''', '''                    Button("Найти японские субтитры на Jimaku") { searchJimaku() }
                    if #available(iOS 26.0, *) {
                        Button("Сделать субтитры из звука") { startSpeechSubtitles(force: true) }
                    }
''', "speech button")
s = once(s, '''        .onDisappear {
            CrashTrail.mark("плеер: закрытие")
''', '''        .onDisappear {
            CrashTrail.mark("плеер: закрытие")
            speechTask?.cancel()
''', "speech stop")
s = s.rstrip("\n") + "\n" + (here / "v214-speech.swift").read_text(encoding="utf-8")
hv.write_text(s, encoding="utf-8")

plist = pathlib.Path("src/safari/iOS (App)/Info.plist")
p = plist.read_text(encoding="utf-8")
if "NSSpeechRecognitionUsageDescription" not in p:
    head, tail, end = p.rpartition("</dict>\n</plist>")
    assert tail, "Info.plist end"
    p = (head + "\t<key>NSSpeechRecognitionUsageDescription</key>\n"
         "\t<string>Satori распознаёт речь видео на устройстве, чтобы сделать японские субтитры.</string>\n"
         + tail + end)
    plist.write_text(p, encoding="utf-8")
print("v2.14 speech subtitles applied")
