# v1.76: the analysis counts only mature cards, the speech speed and a calibration of the level.
# - An imported deck keeps the words of its mature cards (an interval of 21 days or more) apart: the coverage and
#   the difficulty count only these (all imported words stay "in Anki": not highlighted, marked). Words added from
#   Satori count once a later import finds them mature. Until a deck is imported again, the old way.
# - Settings → Anki: "delete the imported words".
# - Speech speed: morae a minute while the subtitles are on screen (Jiten's speed in the catalog); faster than the
#   usual 320 makes the grade harder, slower easier.
# - "Калибровка" in "Мой уровень японского": about 75 words around the present boundaries (frequent words that
#   only the number of frequent words decides, JLPT words of the level and the next one); the number moves to where
#   about half of the words are known, the level moves when its words are not known or the next level's are.
#   The words are made at build time from Jiten's frequency list and the JLPT lists of the release.
# The code is v176-analysis.swift.
import csv, glob, json, os, pathlib, re, zipfile


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


def between(text, start, end, new, label):
    assert text.count(start) == 1, "start not found exactly once: " + label
    a = text.index(start)
    b = text.index(end, a)
    return text[:a] + new + text[b:]


# ---------- the calibration words ----------
KATAKANA = re.compile(r"^[゠-ヿー・]+$")
KANJI = re.compile(r"[㐀-鿿]")
LATIN = re.compile(r"[A-Za-z0-9０-９Ａ-Ｚａ-ｚ\t\n\"#]")
SPLIT = re.compile(r"[;、,／/･・（(]")


def hira(s):
    return "".join(chr(ord(c) - 0x60) if 0x30A1 <= ord(c) <= 0x30F6 else c for c in s)


def frequency_words(path):
    """One word per rank (200 … 40 000): every third up to 5 000, every eighth after."""
    z = zipfile.ZipFile(path)
    best = {}
    for name in sorted(n for n in z.namelist() if n.startswith("term_meta_bank_")):
        for term, kind, data in json.loads(z.read(name)):
            if kind != "freq" or not isinstance(data, dict) or "reading" not in data:
                continue
            freq = data["frequency"]
            if not isinstance(freq, dict):
                continue
            rank = int(freq["value"])
            reading = hira(data["reading"])
            if rank < 200 or rank > 40000 or len(reading) < 2 or LATIN.search(term) or LATIN.search(reading):
                continue
            if KATAKANA.match(term) or KATAKANA.match(data["reading"]):
                continue
            kana = str(freq.get("displayValue", "")).endswith("㋕")
            score = 1 if KANJI.search(term) else 0
            old = best.get(rank)
            if old is None or score > old[3]:
                best[rank] = (term, reading, kana, score)
    out = []
    for i, rank in enumerate(sorted(best)):
        if (rank <= 5000 and i % 3) or (rank > 5000 and i % 8):
            continue
        term, reading, kana, _ = best[rank]
        out.append(("k" if kana else "f", rank, term, reading))
    return out


def jlpt_words(folder):
    """About 200 words of every level (a word of several levels belongs to the easiest)."""
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
    out = []
    for n in (5, 4, 3, 2, 1):
        words = sorted(k for k, v in levels.items() if v == n)
        step = max(1, len(words) // 200)
        out += [("j", n, w, r) for i, (w, r) in enumerate(words) if i % step == 0]
    return out


folders = [d for d in ("ours/custom-dict", os.environ.get("SATORI_DICT_DIR", "")) if d and os.path.isdir(d)]
lines = []
for folder in folders:
    zips = [p for p in sorted(glob.glob(os.path.join(folder, "*freq*.zip"))) if "webnovel" not in p.lower()]
    if zips and not any(x[0] in "fk" for x in lines):
        lines += frequency_words(zips[0])
    if not any(x[0] == "j" for x in lines):
        lines += jlpt_words(folder)
print("calibration words:", sum(1 for x in lines if x[0] != "j"), "frequent,", sum(1 for x in lines if x[0] == "j"), "JLPT")
data = "\n".join("%s\t%d\t%s\t%s" % x for x in lines)
assert '"""#' not in data
calibration = ('\n/// Words for the calibration, made at build time from Jiten\'s frequency list and the JLPT lists:\n'
               '/// "f/k<TAB>rank<TAB>word<TAB>reading" (k: written in kana as a rule), "j<TAB>level<TAB>word<TAB>reading".\n'
               'enum CalibrationData {\n    static let text: String = #"""\n' + data + '\n"""#\n}\n')

here = pathlib.Path(__file__).resolve().parent
hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")

# ---------- the known words of the analysis: mature cards ----------
s = once(s, '''        for w in (root["known"] as? [String]) ?? [] { words.insert(w) }
        return words
    }
''', '''        for w in (root["known"] as? [String]) ?? [] { words.insert(w) }
        return words
    }

    /// The cards the analysis counts as known: the mature ones of the imported decks (an interval of 21 days or more).
    /// Before a deck is imported with its schedule (1.76), every card as before; without any import, none.
    static func analysisWords() -> Set<String> {
        guard let json = (try? Storage.stats.get())?.data(using: .utf8),
              let root = (try? JSONSerialization.jsonObject(with: json)) as? [String: Any] else { return [] }
        if let mature = root["mature"] as? [String] {
            return Set(mature)
        }
        return root["known"] != nil ? minedWords() : []
    }
''', "analysis words")
assert s.count("HighlightData.minedWords()") == 5, "mined words uses"
s = s.replace("HighlightData.minedWords()", "HighlightData.analysisWords()")
s = once(s, '''        if !known.isEmpty {
            root["known"] = known
        }
''', '''        if !known.isEmpty {
            root["known"] = known
        }
        if let mature = ImportedWords.mature() {
            root["mature"] = mature
        }
''', "reset keeps mature")

# ---------- speech speed ----------
s = once(s, "    static let algorithm = 3\n", "    static let algorithm = 4\n", "algorithm 4")
s = once(s, '''struct EpisodeAnalysis {
    let coverage: Int
    let difficulty: Int?
''', '''struct EpisodeAnalysis {
    let coverage: Int
    var difficulty: Int?
''', "difficulty var")
s = once(s, '''    let lines: Int
    let unknown: [UnknownWord]
}
''', '''    let lines: Int
    let unknown: [UnknownWord]
    /// morae of all the lines (the speech speed)
    var morae: Int = 0
    /// morae a minute while a line is on screen
    var speed: Double? = nil
}
''', "episode speed fields")
s = once(s, '''        var unknownCounts: [String: Int] = [:]
        for text in lines {
            guard !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { continue }
            let tokens = autoreleasepool { NativeLookup.tokenize(text, charAt: 0).tokens }
''', '''        var unknownCounts: [String: Int] = [:]
        var morae = 0
        for text in lines {
            guard !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { continue }
            let tokens = autoreleasepool { NativeLookup.tokenize(text, charAt: 0).tokens }
            for token in tokens {
                morae += TextAnalysis.morae(token.reading)
            }
''', "count morae")
s = once(s, "knownShare: knownShare, clearShare: clear, words: words, lines: lineCount, unknown: list)",
         "knownShare: knownShare, clearShare: clear, words: words, lines: lineCount, unknown: list,\n"
         "                               morae: morae)", "episode morae")
s = once(s, "enum TextAnalysis {\n", '''enum TextAnalysis {
    private static let smallKana: Set<UInt32> = [0x3041, 0x3043, 0x3045, 0x3047, 0x3049, 0x3083, 0x3085, 0x3087, 0x308E,
                                                 0x30A1, 0x30A3, 0x30A5, 0x30A7, 0x30A9, 0x30E3, 0x30E5, 0x30E7, 0x30EE]

    /// Morae of a reading: the kana without the small ゃゅょぁぃぅぇぉゎ (っ and ー count).
    static func morae(_ reading: String) -> Int {
        var count = 0
        for scalar in reading.unicodeScalars {
            let value = scalar.value
            let kana = (0x3041 ... 0x3096).contains(value) || (0x30A1 ... 0x30FA).contains(value) || value == 0x30FC
            if kana && !smallKana.contains(value) {
                count += 1
            }
        }
        return count
    }

''', "morae func")
s = once(s, '''    nonisolated static func analyze(of file: URL, index: KnownWordsIndex, level: Int, vocabulary: Int) -> EpisodeAnalysis? {
        TextAnalysis.analyze(lines: EmbeddedSubtitles.cues(fromFile: file).map { $0.text }, index: index, level: level,
                             vocabulary: vocabulary)
    }
''', '''    nonisolated static func analyze(of file: URL, index: KnownWordsIndex, level: Int, vocabulary: Int) -> EpisodeAnalysis? {
        let cues = EmbeddedSubtitles.cues(fromFile: file)
        guard var result = TextAnalysis.analyze(lines: cues.map { $0.text }, index: index, level: level,
                                                vocabulary: vocabulary) else { return nil }
        // the speech speed: morae a minute while a line is on screen; it moves the grade
        let seconds = VideoLibraryStore.speechSeconds(cues)
        if seconds >= 60, result.morae > 0 {
            let speed = Double(result.morae) / (seconds / 60)
            result.speed = speed
            if result.difficulty != nil {
                result.difficulty = VideoLibraryStore.classify(known: result.knownShare, clear: result.clearShare,
                                                               speed: speed)
            }
        }
        return result
    }
''', "video speed")
s = once(s, '''                        row("Реплик", String(result.lines))
''', '''                        row("Реплик", String(result.lines))
                        if let speed = result.speed {
                            row("Скорость речи", SpeechSpeed.text(speed))
                        }
''', "episode speed row")
s = once(s, '''                        Text("easy: от 90% знакомых слов и 65% понятных реплик; normal: от 80% и 40%; иначе hard. Понятная реплика — не больше одного незнакомого слова. Уровень: N" + String(VideoLibraryStore.userLevel) + ", частых слов: " + String(VideoLibraryStore.vocabulary(level: VideoLibraryStore.userLevel)) + ".")
''', '''                        Text(footerText())
''', "episode footer")
s = once(s, '''    private func row(_ title: String, _ value: String) -> some View {
        HStack {
            Text(title)
            Spacer()
            Text(value).foregroundColor(.secondary)
        }
    }

    var body: some View {
        NavigationView {
            List {
                if loading {''', '''    private func row(_ title: String, _ value: String) -> some View {
        HStack {
            Text(title)
            Spacer()
            Text(value).foregroundColor(.secondary)
        }
    }

    /// The rules of the grade, in steps (one long expression is slow for the type checker).
    private func footerText() -> String {
        let level = VideoLibraryStore.userLevel
        let rules: String = "easy: от 90% знакомых слов и 65% понятных реплик; normal: от 80% и 40%; иначе hard. "
            + "Понятная реплика — не больше одного незнакомого слова. "
        let speed: String = "Быстрая речь (больше 320 мор/мин) понижает оценку, медленная — повышает: каждые 50 мор/мин — "
            + "как 4% знакомых слов и 10% понятных реплик. "
        let settings: String = "Знакомыми считаются зрелые карточки Anki, JLPT до N" + String(level) + " и "
            + String(VideoLibraryStore.vocabulary(level: level)) + " частых слов."
        return rules + speed + settings
    }

    var body: some View {
        NavigationView {
            List {
                if loading {''', "episode footer func")

# ---------- the catalog grade with Jiten's speech speed ----------
s = once(s, "                        CoverageBadge(known: coverage.known, difficulty: coverage.difficulty)\n",
         "                        CoverageBadge(known: coverage.known,\n"
         "                                      difficulty: CatalogStore.grade(known: coverage.known, speed: deck.speechSpeed))\n",
         "catalog row grade")
s = once(s, '''                        Text(CatalogStore.difficultyName(coverage.difficulty))
                            .font(.callout.bold())
                            .foregroundColor(coverage.difficulty == 2 ? .white : .black)
                            .padding(.horizontal, 8)
                            .padding(.vertical, 2)
                            .background(CatalogStore.difficultyColor(coverage.difficulty).opacity(0.85))
''', '''                        Text(CatalogStore.difficultyName(grade(coverage)))
                            .font(.callout.bold())
                            .foregroundColor(grade(coverage) == 2 ? .white : .black)
                            .padding(.horizontal, 8)
                            .padding(.vertical, 2)
                            .background(CatalogStore.difficultyColor(grade(coverage)).opacity(0.85))
''', "catalog detail grade")
s = once(s, '''    private func load() async {
        guard detail == nil else { return }
''', '''    /// The grade by the known words and Jiten's speech speed.
    private func grade(_ coverage: CatalogCoverage) -> Int {
        CatalogStore.grade(known: coverage.known, speed: shown.speechSpeed)
    }

    private func load() async {
        guard detail == nil else { return }
''', "catalog detail grade func")
s = once(s, "Text(\"Знакомыми считаются ваши карточки, слова JLPT до вашего уровня и частые слова (Настройки → «Мой уровень японского»). Доля учитывает, как часто слово встречается. Оценка: easy от 90%, normal от 80%.\")",
         "Text(\"Знакомыми считаются ваши зрелые карточки Anki, слова JLPT до вашего уровня и частые слова (Настройки → «Мой уровень японского»). Доля учитывает, как часто слово встречается. Оценка: easy от 90%, normal от 80%; быстрая речь понижает её, медленная — повышает.\")",
         "catalog detail footer")

# ---------- settings: calibration, imported words ----------
s = once(s, '''    @AppStorage("ykMiningQueue") private var miningQueue = false
''', '''    @AppStorage("ykMiningQueue") private var miningQueue = false
    /// words imported from Anki decks: all, mature, imported with the schedule
    @State private var imported: (all: Int, mature: Int, scheduled: Bool) = (0, 0, false)
    @State private var confirmForget = false

    private var levelFooter: String {
        let rules: String = "Для покрытия и сложности знакомыми считаются зрелые карточки Anki (интервал от 21 дня, "
            + "из импорта колоды), слова JLPT до этого уровня и столько самых частых слов (Jiten). 0 — по уровню: "
            + "N5 ≈ 800, N4 ≈ 1500, N3 ≈ 3700, N2 ≈ 6000, N1 ≈ 10 000. Калибровка уточняет оба числа по вашим ответам. "
            + "Подсветка на это не влияет."
        if imported.all > 0 && !imported.scheduled {
            return rules + " Колода импортирована до 1.76: пока считаются все её карточки — импортируйте её заново."
        }
        return rules
    }

    private var ankiFooter: String {
        var text: String = "Очередь майнинга: кнопка ⊕ в видео и в чтении кладёт заметку в очередь, а не открывает "
            + "AnkiMobile. Очередь — кнопка вверху вкладок «Видео» и «Чтение»."
        if imported.all > 0 {
            text += " Импортировано слов: " + String(imported.all)
            if imported.scheduled {
                text += ", из них зрелых: " + String(imported.mature)
            }
            text += ". Импорт можно повторять: новые зрелые карточки добавятся."
        }
        return text
    }
''', "settings state")
s = once(s, '''                        .frame(width: 100)
                }
            } header: {
                Text("Мой уровень японского")
            } footer: {
                Text("Для покрытия и сложности серий знакомыми считаются ваши карточки, слова JLPT до этого уровня и столько самых частых слов (Jiten). 0 — по уровню: N5 ≈ 800, N4 ≈ 1500, N3 ≈ 3700, N2 ≈ 6000, N1 ≈ 10 000. Подсветка на это не влияет.")
            }
''', '''                        .frame(width: 100)
                }
                if #available(iOS 16.0, *) {
                    NavigationLink(destination: CalibrationView()) {
                        Text("Калибровка")
                    }
                }
            } header: {
                Text("Мой уровень японского")
            } footer: {
                Text(levelFooter)
            }
''', "level section")
s = once(s, '''                NavigationLink(destination: webPage("ankiImport", "Импорт колоды Anki")) {
                    Text("Импорт колоды Anki")
                }
            } header: {
                Text("Anki")
            } footer: {
                Text("Очередь майнинга: кнопка ⊕ в видео и в чтении кладёт заметку в очередь, а не открывает AnkiMobile. Очередь — кнопка вверху вкладок «Видео» и «Чтение».")
            }
''', '''                NavigationLink(destination: webPage("ankiImport", "Импорт колоды Anki")) {
                    Text("Импорт колоды Anki")
                }
                if imported.all > 0 {
                    Button("Удалить импортированные слова", role: .destructive) {
                        confirmForget = true
                    }
                }
            } header: {
                Text("Anki")
            } footer: {
                Text(ankiFooter)
            }
''', "anki section")
s = once(s, '''        .onAppear {
            config.reload()
        }
''', '''        .onAppear {
            config.reload()
            imported = ImportedWords.counts()
        }
        .alert("Удалить импортированные слова?", isPresented: $confirmForget) {
            Button("Удалить", role: .destructive) {
                ImportedWords.forget()
                imported = ImportedWords.counts()
            }
            Button("Отмена", role: .cancel) {}
        } message: {
            Text("Слова из колод Anki (" + String(imported.all) + ") перестанут считаться известными и снова будут подсвечиваться. Статистика и слова, добавленные из Satori, останутся. Колоду можно импортировать заново.")
        }
''', "forget alert")

s = s.rstrip("\n") + "\n" + (here / "v176-analysis.swift").read_text(encoding="utf-8") + calibration
hv.write_text(s, encoding="utf-8")

# ---------- the import of a deck: mature cards apart ----------
web = pathlib.Path("src/main/src")
lib = web / "lib/ankiImport.ts"
t = lib.read_text(encoding="utf-8")
t = t.rstrip("\n") + '''

/** Words of all notes, and the words of notes with a mature card (a review interval of 21 days or more). */
export async function readAnkiDeck(buf: ArrayBuffer): Promise<{ words: string[]; mature: string[] }> {
  const bytes = collectionBytes(new Uint8Array(buf));
  // @ts-ignore pure JavaScript build, no wasm file to copy
  const SQL = await initSqlJs();
  const db = new SQL.Database(bytes);
  try {
    const names = fieldNames(db);
    const words = new Set<string>();
    const mature = new Set<string>();
    const rows = db.exec(
      "select n.mid, n.flds, max(case when c.type = 2 and c.ivl >= 21 then 1 else 0 end) " +
        "from notes n left join cards c on c.nid = n.id group by n.id",
    );
    for (const row of rows[0] ? rows[0].values : []) {
      const values = String(row[1]).split("\\x1f");
      const word = wordFromFields(names[String(row[0])] ?? [], values);
      if (!word) continue;
      words.add(word);
      if (Number(row[2]) === 1) mature.add(word);
    }
    return { words: Array.from(words), mature: Array.from(mature) };
  } finally {
    db.close();
  }
}

/** All words go to the known list (not highlighted), the mature ones also to the mature list (the analysis). */
export async function importDeck(deck: { words: string[]; mature: string[] }): Promise<{ added: number }> {
  const raw = (await Platform.messageWebview("loadStats", null)) as any;
  const data: any = raw && raw.days !== undefined ? raw : { days: {} };
  const known = new Set<string>(Array.isArray(data.known) ? data.known : []);
  let added = 0;
  for (const w of deck.words) {
    if (!known.has(w)) {
      known.add(w);
      added++;
    }
  }
  const mature = new Set<string>(Array.isArray(data.mature) ? data.mature : []);
  for (const w of deck.mature) mature.add(w);
  data.known = Array.from(known);
  data.mature = Array.from(mature);
  data.matureUpdated = new Date().toISOString();
  await Platform.messageWebview("saveStats", data);
  return { added };
}
'''
lib.write_text(t, encoding="utf-8")

page = web / "components/options/groups/GroupAnkiImport.svelte"
t = page.read_text(encoding="utf-8")
t = once(t, 'import { readAnkiWords, importKnownWords } from "lib/ankiImport";',
         'import { readAnkiDeck, importDeck } from "lib/ankiImport";', "import page imports")
t = once(t, '''      const words = await readAnkiWords(await file.arrayBuffer());
      const added = await importKnownWords(words);
      status = `Слов в колоде: ${words.length}, добавлено новых: ${added}. Они больше не подсвечиваются.`;
''', '''      const deck = await readAnkiDeck(await file.arrayBuffer());
      const result = await importDeck(deck);
      status =
        `Слов в колоде: ${deck.words.length}, новых: ${result.added}, зрелых (интервал от 21 дня): ${deck.mature.length}. ` +
        "Все слова колоды больше не подсвечиваются; в покрытии и сложности учитываются только зрелые.";
      if (deck.words.length > 0 && deck.mature.length === 0) {
        status +=
          " Зрелых карточек нет: похоже, колода экспортирована без расписания. Экспортируйте .colpkg " +
          "или .apkg с включённым Include scheduling information.";
      }
''', "import page status")
t = once(t, '''  <div class="title">Импорт колоды Anki</div>
''', '''  <div class="title">Импорт колоды Anki</div>
  <div class="note">
    Экспортируйте колоду из AnkiMobile (.colpkg или .apkg с расписанием) и выберите файл. Все её слова перестанут
    подсвечиваться, а в покрытии и сложности будут учитываться слова зрелых карточек (интервал от 21 дня). Импорт можно
    повторять: новые зрелые карточки добавятся.
  </div>
''', "import page note")
t = once(t, '''  .status {
''', '''  .note {
    margin-bottom: 8px;
    font-size: 0.85rem;
    color: var(--text-faint);
  }
  .status {
''', "import page note style")
page.write_text(t, encoding="utf-8")

stats = web / "extension/stats.ts"
t = stats.read_text(encoding="utf-8")
t = once(t, "      if (old.known !== undefined) fresh.known = old.known;\n",
         "      if (old.known !== undefined) fresh.known = old.known;\n"
         "      if ((old as any).mature !== undefined) (fresh as any).mature = (old as any).mature;\n", "extension reset")
stats.write_text(t, encoding="utf-8")
print("v1.76 analysis applied")
