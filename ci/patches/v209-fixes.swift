
// MARK: - Satori v2.09: «О приложении», the words of the queue

/// Настройки → «О приложении»: the version, the code, the data and the libraries, the licences.
struct AboutView: View {
    private static let licenses: URL? = Bundle.main.url(forResource: "THIRD_PARTY", withExtension: "txt",
                                                        subdirectory: "res")

    private var version: String {
        (Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String) ?? "?"
    }

    private func row(_ title: String, _ value: String) -> some View {
        HStack(alignment: .firstTextBaseline) {
            Text(title)
            Spacer(minLength: 16)
            Text(value)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.trailing)
        }
    }

    var body: some View {
        List {
            Section {
                HStack(spacing: 16) {
                    Text("悟")
                        .font(.system(size: 44, weight: .bold))
                        .foregroundColor(.accentColor)
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Satori")
                            .font(.title2.weight(.bold))
                        Text("Версия " + version)
                            .foregroundColor(.secondary)
                    }
                }
                .padding(.vertical, 6)
            }
            Section {
                Link("Satori на GitHub", destination: URL(string: "https://github.com/itsHiyori/satori")!)
                Link("Yomikiri — исходный проект (MIT)",
                     destination: URL(string: "https://github.com/BlueGreenMagick/yomikiri")!)
            } header: {
                Text("Исходный код")
            }
            Section {
                row("Словарь", "Kolobok на основе Jitendex и JMdict")
                row("Частотность и каталог", "Jiten (CC BY-SA 4.0)")
                row("Ударение", "Kanjium")
                row("Описания и оценки", "Shikimori, AniList, TMDB")
                row("Субтитры", "Jimaku")
                row("Плеер", "KSPlayer, FFmpeg, Anime4K")
            } header: {
                Text("Данные и библиотеки")
            }
            if let url = AboutView.licenses {
                Section {
                    NavigationLink(destination: LicensesView(url: url)) {
                        Text("Лицензии третьих сторон")
                    }
                }
            }
        }
        .navigationTitle("О приложении")
        .navigationBarTitleDisplayMode(.inline)
        .navigationBarHidden(false)
        .satoriBackdrop()
    }
}

/// The text of the third-party licences (a long text: UIKit draws it).
struct LicensesView: View {
    let url: URL
    @State private var text = ""

    var body: some View {
        LargeTextView(text: text)
            .navigationTitle("Лицензии")
            .navigationBarTitleDisplayMode(.inline)
            .navigationBarHidden(false)
            .task {
                let file = url
                text = await Task.detached(priority: .userInitiated) {
                    (try? String(contentsOf: file, encoding: .utf8)) ?? ""
                }.value
            }
    }
}

struct LargeTextView: UIViewRepresentable {
    let text: String

    func makeUIView(context: Context) -> UITextView {
        let view = UITextView()
        view.isEditable = false
        view.backgroundColor = .clear
        view.font = .monospacedSystemFont(ofSize: 11, weight: .regular)
        view.textColor = .secondaryLabel
        view.textContainerInset = UIEdgeInsets(top: 12, left: 12, bottom: 24, right: 12)
        return view
    }

    func updateUIView(_ view: UITextView, context: Context) {
        if view.text != text {
            view.text = text
        }
    }
}

extension MiningQueue {
    /// The words of the notes in the queue as the lists and the dictionary see them: the word the statistics count,
    /// every short field without HTML and furigana, and the kana of a field with furigana (いたずら for
    /// 悪戯[いたずら]); a word queued under another written form leaves the lists too.
    static func queuedWords() -> [String] {
        var words: [String] = []
        for entry in shared.entries {
            words.append(statsWord(of: entry.url))
            for item in URLComponents(string: entry.url)?.queryItems ?? [] where item.name.hasPrefix("fld") {
                var value = item.value ?? ""
                // sentences, meanings and links are no words
                guard !value.isEmpty, value.count <= 40 else { continue }
                if hasAnyScalar(value, of: "<") {
                    value = value.replacingOccurrences(of: "<[^>]*>", with: "", options: .regularExpression)
                }
                if hasAnyScalar(value, of: "[") {
                    // the kana of the furigana, katakana as hiragana (as the lists keep the words)
                    var kana = ""
                    for scalar in value.unicodeScalars where !statIsKanji(scalar) && !"[] ".unicodeScalars.contains(scalar) {
                        if (0x30A1 ... 0x30F6).contains(scalar.value), let hiragana = Unicode.Scalar(scalar.value - 0x60) {
                            kana.unicodeScalars.append(hiragana)
                        } else {
                            kana.unicodeScalars.append(scalar)
                        }
                    }
                    if !kana.isEmpty {
                        words.append(kana)
                    }
                    value = value.replacingOccurrences(of: "\\[[^\\]]*\\]", with: "", options: .regularExpression)
                }
                let plain = value.components(separatedBy: .whitespacesAndNewlines).joined()
                if !plain.isEmpty {
                    words.append(plain)
                }
            }
        }
        return words
    }
}
