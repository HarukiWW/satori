# v1.79: no calibration and no JLPT estimate (a few answers per band cannot tell how many words one knows). The
# statistics show the main kanji instead: how many of the 2000 most frequent kanji your cards have, and lighter,
# how many new ones a week usually add (the words added in the last four weeks). The build-time data keeps only the
# kanji order (from Jiten's frequency list). The code is v179-kanji.swift.
import glob, json, os, pathlib, re, zipfile


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


KANJI = re.compile(r"[㐀-鿿]")


def kanji_order(path):
    """Kanji by the sum of 1/rank of the words that have them (words written in kana as a rule do not count)."""
    z = zipfile.ZipFile(path)
    score = {}
    for name in sorted(n for n in z.namelist() if n.startswith("term_meta_bank_")):
        for term, kind, data in json.loads(z.read(name)):
            if kind != "freq" or not isinstance(data, dict) or "reading" not in data:
                continue
            freq = data["frequency"]
            if not isinstance(freq, dict) or str(freq.get("displayValue", "")).endswith("㋕"):
                continue
            rank = int(freq["value"])
            for k in set(KANJI.findall(term)):
                score[k] = score.get(k, 0.0) + 1.0 / rank
    return sorted(score, key=lambda k: -score[k])[:3000]


folders = [d for d in ("ours/custom-dict", os.environ.get("SATORI_DICT_DIR", "")) if d and os.path.isdir(d)]
order = []
for folder in folders:
    zips = [p for p in sorted(glob.glob(os.path.join(folder, "*freq*.zip"))) if "webnovel" not in p.lower()]
    if zips and not order:
        order = kanji_order(zips[0])
print("kanji order:", len(order))
data = "\n".join("c\t%d\t%s" % (i + 1, k) for i, k in enumerate(order))
kanji_data = ('\n/// The kanji from the most frequent, made at build time from Jiten\'s frequency list: "c<TAB>order<TAB>kanji".\n'
              'enum KanjiData {\n    static let text: String = #"""\n' + data + '\n"""#\n}\n')

here = pathlib.Path(__file__).resolve().parent
hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")

# ---------- the calibration and the JLPT estimate go, the kanji stay ----------
start = "/// What the calibration found: the share of the words (not in the cards) that are known, by frequency rank."
marker = "\n/// Words for the calibration and the JLPT estimate, made at build time"
assert s.count(start) == 1 and s.count(marker) == 1, "level code"
a = s.index(start)
b = s.index(marker)
end = s.index('\n"""#\n}\n', b) + len('\n"""#\n}\n')
s = s[:a] + (here / "v179-kanji.swift").read_text(encoding="utf-8") + s[end:]
s = s.rstrip("\n") + "\n" + kanji_data

s = once(s, '''                if #available(iOS 16.0, *) {
                    NavigationLink(destination: CalibrationView()) {
                        Text("Калибровка")
                    }
                    NavigationLink(destination: JLPTEstimateView()) {
                        Text("Уровень JLPT по словам")
                    }
                }
''', "", "settings links")

# ---------- the statistics: the main kanji under the chart ----------
s = once(s, '''                VStack(alignment: .leading, spacing: 10) {
                    Text(mode == 0 ? "Прочитано слов за 7 дней" : "Время просмотра за 7 дней")
''', '''                if #available(iOS 16.0, *) {
                    KanjiProgressCard()
                }

                VStack(alignment: .leading, spacing: 10) {
                    Text(mode == 0 ? "Прочитано слов за 7 дней" : "Время просмотра за 7 дней")
''', "kanji card")
hv.write_text(s, encoding="utf-8")
print("v1.79 kanji applied")
