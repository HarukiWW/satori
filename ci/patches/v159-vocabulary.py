# v1.59: the vocabulary for the episode analysis is its own setting ("Мой уровень японского"): the most frequent words
# surely known, and up to which rank half known. 0 = from the level. The highlight range is not used any more.
import pathlib

hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


a = s.index("    /// The vocabulary: words more frequent than the start of the highlight range are known")
b = s.index("    /// One pass over the subtitles.", a)
s = s[:a] + '''    /// The vocabulary of the settings: the most frequent words surely known (ykVocabSure) and up to which rank they
    /// are half known (ykVocabPartial); 0 means from the level (N5 800 … N1 10 000, half known up to twice that).
    static func frequencyBand(level: Int) -> (lower: Int, upper: Int) {
        let byLevel: [Int: Int] = [5: 800, 4: 1500, 3: 3700, 2: 6000, 1: 10000]
        let sure = UserDefaults.standard.integer(forKey: "ykVocabSure")
        let partial = UserDefaults.standard.integer(forKey: "ykVocabPartial")
        let lower = sure > 0 ? sure : (byLevel[level] ?? 800)
        let upper = partial > 0 ? max(partial, lower) : lower * 2
        return (lower, upper)
    }

''' + s[b:]

s = once(s, '    @AppStorage("ykUserLevel") private var userLevel = 5\n',
         '    @AppStorage("ykUserLevel") private var userLevel = 5\n'
         '    @AppStorage("ykVocabSure") private var vocabSure = 0\n'
         '    @AppStorage("ykVocabPartial") private var vocabPartial = 0\n', "vocab storage")
s = once(s, '''                    Text("N1").tag(1)
                }
''', '''                    Text("N1").tag(1)
                }
                HStack {
                    Text("Точно знаю первые")
                    Spacer()
                    TextField("по уровню", value: $vocabSure, format: .number)
                        .keyboardType(.numberPad)
                        .multilineTextAlignment(.trailing)
                        .foregroundColor(.secondary)
                        .frame(width: 100)
                }
                HStack {
                    Text("Наполовину знаю до")
                    Spacer()
                    TextField("по уровню", value: $vocabPartial, format: .number)
                        .keyboardType(.numberPad)
                        .multilineTextAlignment(.trailing)
                        .foregroundColor(.secondary)
                        .frame(width: 100)
                }
''', "vocab fields")
s = once(s, '"Знакомыми считаются ваши карточки, слова JLPT до этого уровня и самые частые слова в объёме этого уровня (N5 ≈ 800, N4 ≈ 1500, N3 ≈ 3700, N2 ≈ 6000, N1 ≈ 10 000). Так считаются покрытие и сложность серий."',
         '"Для покрытия и сложности серий знакомыми считаются ваши карточки, слова JLPT до этого уровня и самые частые слова: первые N точно, дальше до второго числа — наполовину. 0 — по уровню (N5 ≈ 800, N4 ≈ 1500, N3 ≈ 3700, N2 ≈ 6000, N1 ≈ 10 000, наполовину — вдвое больше). Подсветка на это не влияет."',
         "footer")
hv.write_text(s, encoding="utf-8")
print("v1.59 vocabulary applied")
