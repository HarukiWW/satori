# v1.77: the level.
# - Calibration: the frequency bands reach from half to six times the number of frequent words (the boundary was
#   often beyond three times); the JLPT words asked are those rarer than the frequent words (only these does the
#   level decide), the more frequent the likelier (a word that never comes up in films and books changes no
#   coverage); the answers say so.
# - "Уровень JLPT": a rough level by the JLPT words your cards and the frequent words cover (75% of a level and the
#   easier ones), the progress to the next one, and how many of the 500 / 1000 / 2000 / 3000 most frequent kanji
#   you know.
# - The build-time data now has every JLPT word and the kanji order (from Jiten's frequency list).
# The code is v177-level.swift.
import csv, glob, json, os, pathlib, re, zipfile


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


# ---------- the build-time data ----------
KATAKANA = re.compile(r"^[゠-ヿー・]+$")
KANJI = re.compile(r"[㐀-鿿]")
LATIN = re.compile(r"[A-Za-z0-9０-９Ａ-Ｚａ-ｚ\t\n\"#]")
SPLIT = re.compile(r"[;、,／/･・（(]")


def hira(s):
    return "".join(chr(ord(c) - 0x60) if 0x30A1 <= ord(c) <= 0x30F6 else c for c in s)


def frequency_data(path):
    """Words by rank (every third up to 5 000, every eighth after) and the kanji order: by the sum of 1/rank of the
    words that have the kanji (the kanji rank of words written in kana as a rule does not count)."""
    z = zipfile.ZipFile(path)
    best = {}
    score = {}
    first = {}
    for name in sorted(n for n in z.namelist() if n.startswith("term_meta_bank_")):
        for term, kind, data in json.loads(z.read(name)):
            if kind != "freq" or not isinstance(data, dict) or "reading" not in data:
                continue
            freq = data["frequency"]
            if not isinstance(freq, dict):
                continue
            rank = int(freq["value"])
            kana = str(freq.get("displayValue", "")).endswith("㋕")
            if not kana:
                for k in set(KANJI.findall(term)):
                    score[k] = score.get(k, 0.0) + 1.0 / rank
                    first[k] = min(first.get(k, 10 ** 9), rank)
            reading = hira(data["reading"])
            if rank < 200 or rank > 40000 or len(reading) < 2 or LATIN.search(term) or LATIN.search(reading):
                continue
            if KATAKANA.match(term) or KATAKANA.match(data["reading"]):
                continue
            weight = 1 if KANJI.search(term) else 0
            old = best.get(rank)
            if old is None or weight > old[3]:
                best[rank] = (term, reading, kana, weight)
    out = []
    for i, rank in enumerate(sorted(best)):
        if (rank <= 5000 and i % 3) or (rank > 5000 and i % 8):
            continue
        term, reading, kana, _ = best[rank]
        out.append(("k" if kana else "f", rank, term, reading))
    order = sorted(score, key=lambda k: -score[k])[:3000]
    out += [("c", i + 1, k, str(first[k])) for i, k in enumerate(order)]
    return out


def jlpt_words(folder):
    """Every JLPT word (a word of several levels belongs to the easiest)."""
    levels = {}
    for n in (5, 4, 3, 2, 1):
        p = os.path.join(folder, "jlpt_n%d.csv" % n)
        if not os.path.exists(p):
            continue
        with open(p, encoding="utf-8-sig", newline="") as f:
            for row in csv.reader(f):
                if len(row) < 2 or row[0].strip().lower() == "expression":
                    continue
                word = SPLIT.split(row[0].strip())[0].strip()
                reading = hira(SPLIT.split(row[1].strip())[0].strip())
                if not word or "～" in word or "〜" in word or KATAKANA.match(word) or LATIN.search(word + reading):
                    continue
                levels[(word, reading)] = max(levels.get((word, reading), 0), n)
    return [("j", n, w, r) for (w, r), n in sorted(levels.items(), key=lambda x: (-x[1], x[0]))]


folders = [d for d in ("ours/custom-dict", os.environ.get("SATORI_DICT_DIR", "")) if d and os.path.isdir(d)]
lines = []
for folder in folders:
    zips = [p for p in sorted(glob.glob(os.path.join(folder, "*freq*.zip"))) if "webnovel" not in p.lower()]
    if zips and not any(x[0] in "fkc" for x in lines):
        lines += frequency_data(zips[0])
    if not any(x[0] == "j" for x in lines):
        lines += jlpt_words(folder)
print("level data:", sum(1 for x in lines if x[0] in "fk"), "frequent words,", sum(1 for x in lines if x[0] == "j"),
      "JLPT words,", sum(1 for x in lines if x[0] == "c"), "kanji")
data = "\n".join("%s\t%d\t%s\t%s" % x for x in lines)
assert '"""#' not in data
calibration = ('\n/// Words for the calibration and the JLPT estimate, made at build time from Jiten\'s frequency list and the\n'
               '/// JLPT lists: "f/k<TAB>rank<TAB>word<TAB>reading" (k: written in kana as a rule), '
               '"j<TAB>level<TAB>word<TAB>reading",\n/// "c<TAB>order<TAB>kanji<TAB>rank of its most frequent word".\n'
               'enum CalibrationData {\n    static let text: String = #"""\n' + data + '\n"""#\n}\n')

here = pathlib.Path(__file__).resolve().parent
hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")

marker = "\n/// Words for the calibration, made at build time from Jiten's frequency list and the JLPT lists:\n"
assert s.count(marker) == 1, "calibration data"
start = s.index(marker)
end = s.index('\n"""#\n}\n', start) + len('\n"""#\n}\n')
s = s[:start] + s[end:]

# ---------- calibration ----------
s = once(s, '''            } else {
                frequency.append((rank: number, word: parts[2], reading: parts[3], kana: parts[0] == "k"))
''', '''            } else if parts[0] == "f" || parts[0] == "k" {
                frequency.append((rank: number, word: parts[2], reading: parts[3], kana: parts[0] == "k"))
''', "calibration lines")
s = once(s, '''    /// Bands of ranks from 0.3 to 3 times the number of frequent words.
    static func bands(around vocabulary: Int) -> [Band] {
        let steps: [Double] = [0.3, 0.5, 0.7, 0.85, 1.0, 1.2, 1.45, 1.75, 2.2, 3.0]
''', '''    /// Bands of ranks from a half to six times the number of frequent words.
    static func bands(around vocabulary: Int) -> [Band] {
        let steps: [Double] = [0.5, 0.8, 1.0, 1.25, 1.6, 2.0, 2.6, 3.4, 4.5, 6.0]
''', "bands")
s = once(s, '''        for checked in [level, level - 1] where checked >= 1 && checked <= 5 {
            var taken = 0
            for item in jlpt.filter({ $0.level == checked }).shuffled() where taken < 7 {
                if let rank = HighlightData.bestRank(base: item.word, reading: item.reading, text: item.word),
                   rank <= vocabulary { continue }
                guard usable(item.word) else { continue }
''', '''        for checked in [level, level - 1] where checked >= 1 && checked <= 5 {
            // only the words rarer than the frequent ones (the level decides only these), the more frequent the
            // likelier: a word that never comes up in films and books changes no coverage
            var weighted: [(key: Double, item: (level: Int, word: String, reading: String))] = []
            for item in jlpt where item.level == checked {
                guard let rank = HighlightData.bestRank(base: item.word, reading: item.reading, text: item.word),
                      rank > vocabulary else { continue }
                weighted.append((key: pow(Double.random(in: 0.0001 ..< 1), Double(rank) / 1000), item: item))
            }
            var taken = 0
            for entry in weighted.sorted(by: { $0.key > $1.key }) where taken < 7 {
                let item = entry.item
                guard usable(item.word) else { continue }
''', "jlpt sample")
s = once(s, '''    private func levelRow(_ item: Calibration.LevelAnswer) -> some View {
        HStack {
            Text("JLPT N" + String(item.level))
''', '''    private func levelRow(_ item: Calibration.LevelAnswer) -> some View {
        HStack {
            Text("JLPT N" + String(item.level) + ", реже места " + String(vocabulary))
''', "jlpt row label")
s = once(s, '''            } header: {
                Text("Ответы")
            }
''', '''            } header: {
                Text("Ответы")
            } footer: {
                Text("Слова JLPT взяты только из тех, что встречаются реже ваших частых слов: только их засчитывает уровень JLPT. Чем чаще слово, тем вероятнее оно попадалось.")
            }
''', "answers footer")
s = once(s, '''Text("Калибровка покажет около 75 слов вокруг этих границ: частые слова чуть реже и чуть чаще вашего числа и слова JLPT вашего и следующего уровня. Ваши зрелые карточки не показываются.")''',
         '''Text("Калибровка покажет около 75 слов вокруг этих границ: частые слова от вдвое более частых до вшестеро более редких, чем ваше число, и слова JLPT вашего и следующего уровня, которые реже ваших частых. Ваши зрелые карточки не показываются.")''',
         "intro text")

# ---------- settings: the JLPT estimate ----------
s = once(s, '''                if #available(iOS 16.0, *) {
                    NavigationLink(destination: CalibrationView()) {
                        Text("Калибровка")
                    }
                }
''', '''                if #available(iOS 16.0, *) {
                    NavigationLink(destination: CalibrationView()) {
                        Text("Калибровка")
                    }
                    NavigationLink(destination: JLPTEstimateView()) {
                        Text("Уровень JLPT по словам")
                    }
                }
''', "estimate link")

s = s.rstrip("\n") + "\n" + (here / "v177-level.swift").read_text(encoding="utf-8") + calibration
hv.write_text(s, encoding="utf-8")
print("v1.77 level applied")
