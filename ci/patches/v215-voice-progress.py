# v2.15: the grammar sentences read by a neural voice, the progress in place of the 7 days.
# - Every example of the grammar decks is read in advance by Microsoft's neural Nanami (ci/assets/grammar/audio,
#   made by ci/assets/grammar/voice.py, one MP3 per sentence named by the SHA-256 of its text); the cards play the
#   file, a sentence without one is read by the voice of «Настройки → Озвучка».
# - «Статистика»: the bars of the last 7 days (reading or watching) gave their place to the two charts of the
#   progress (the words, the hours, with the forecast), both in the accent colour; the mode «Прогресс» is gone.
import pathlib


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")

# --- the recorded sentences
s = once(s, "import AVFoundation\n", "import AVFoundation\nimport CryptoKit\n", "import cryptokit")
s = once(s, '''enum GrammarVoice {
    static func speak(_ text: String) {
        SatoriVoice.speak(text)
    }
}
''', '''enum GrammarVoice {
    private static var player: AVAudioPlayer? = nil

    /// The sentence read in advance by the neural voice (res/grammar/audio), else by the voice of «Озвучка».
    static func speak(_ text: String) {
        player?.stop()
        player = nil
        guard let url = recorded(text), let made = try? AVAudioPlayer(contentsOf: url) else {
            SatoriVoice.speak(text)
            return
        }
        if synthesizer.isSpeaking {
            synthesizer.stopSpeaking(at: .immediate)
        }
        try? AVAudioSession.sharedInstance().setCategory(.playback, mode: .spokenAudio)
        try? AVAudioSession.sharedInstance().setActive(true)
        player = made
        made.play()
    }

    /// res/grammar/audio/<the first 16 hex digits of the SHA-256 of the text>.mp3 (as voice.py names them)
    static func recorded(_ text: String) -> URL? {
        let digest = SHA256.hash(data: Data(text.utf8))
        let name: String = digest.map { String(format: "%02x", $0) }.joined()
        return Bundle.main.url(forResource: String(name.prefix(16)), withExtension: "mp3", subdirectory: "res/grammar/audio")
    }
}
''', "grammar voice")

# --- the progress in place of the bars of 7 days
s = once(s, '''        let bars = mode == 0 ? model.bars() : model.watchBars()
        let maxRead = max(1, bars.map { $0.read }.max() ?? 1)
''', "", "bars values")
a = s.index('''                VStack(alignment: .leading, spacing: 10) {
                    Text(mode == 0 ? "Прочитано слов за 7 дней" : "Время просмотра за 7 дней")''')
b = s.index('''                .cornerRadius(14)
''', a) + len('''                .cornerRadius(14)
''')
s = s[:a] + '''                if #available(iOS 16.0, *) {
                    ProgressStatsView(model: model)
                }
''' + s[b:]
s = once(s, '''                    Text("Просмотр").tag(1)
                    Text("Прогресс").tag(3)
''', '''                    Text("Просмотр").tag(1)
''', "progress mode")
s = once(s, '''                } else if mode == 3 {
                    if #available(iOS 16.0, *) {
                        ProgressStatsView(model: model)
                    }
                } else {
''', '''                } else {
''', "progress branch")
s = once(s, '''            LazyVGrid(columns: [GridItem(.flexible(), spacing: 12), GridItem(.flexible(), spacing: 12)], spacing: 12) {
                StatCard(title: "Слов в зрелых карточках", value: words.points.isEmpty ? "—" : statNumber(Int(words.now)))
                StatCard(title: "Часов с языком", value: statNumber(Int(hours.now.rounded())))
            }
''', "", "progress tiles")
s = once(s, '''                    ProgressChart(series: hours, color: .orange, unit: " ч")''',
         '''                    ProgressChart(series: hours, color: tint, unit: " ч")''', "hours colour")
hv.write_text(s, encoding="utf-8")
print("v2.15 voice and progress applied")
