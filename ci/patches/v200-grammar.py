# v2.00: grammar decks N5–N1.
# - Decks of JLPT grammar (res/grammar/n5.json … n1.json, copied into the app when the .ipa is packed): the front shows
#   the construction and a short Japanese sentence with it, the back the meaning, the sentence, its translation and an
#   explanation; the sentence is read aloud on both sides. Reviews as in Anki (learning steps, four answers with their
#   intervals, undo) scheduled by FSRS-5.
# - The level test: about 20 questions on the meaning of the marked grammar, guesses taken out; the points answered
#   right do not come as new cards, from 85% the level is passed.
# - The grammar the user does not know makes a line less clear in the difficulty of episodes and novels (a clear line
#   has at most one unknown word or construction); the list of unknown words of an episode shows its unknown grammar.
# - The decks open from the dictionary tab.
import pathlib


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


def within(text, start, end, old, new, label):
    """Replace `old` (exactly once) between the first `start` and the next `end` after it."""
    assert text.count(start) == 1, "region start not found exactly once: " + label
    a = text.index(start)
    b = text.index(end, a + len(start))
    part = text[a:b]
    assert part.count(old) == 1, "pattern not found once in region: " + label
    return text[:a] + part.replace(old, new) + text[b:]


here = pathlib.Path(__file__).resolve().parent

hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")

# ---------- the difficulty: unknown grammar makes a line less clear ----------
s = once(s, '''    /// changes with the rules: the saved analyses are counted again
    static let algorithm = 5
''', '''    /// changes with the rules: the saved analyses are counted again
    static let algorithm = 5

    /// the saved analyses of episodes and novels: the rules and the grammar the user does not know yet
    static var textVersion: Int {
        algorithm * 10_000 + GrammarDemand.unknown().stamp
    }
''', "text version")
s = once(s, '''        var unknownCounts: [String: Int] = [:]
        var morae = 0
        for text in lines {
''', '''        var unknownCounts: [String: Int] = [:]
        var morae = 0
        // the grammar of the decks the user does not know yet
        let grammar = GrammarDemand.unknown().detectors
        var grammarCounts: [String: Int] = [:]
        for text in lines {
''', "analysis grammar")
s = once(s, '''            lineCount += 1
            if lineUnknown <= 1 {
                clearLines += 1
            }
''', '''            lineCount += 1
            var lineGrammar = 0
            let range = NSRange(text.startIndex..., in: text)
            for detector in grammar where detector.regex.firstMatch(in: text, options: [], range: range) != nil {
                lineGrammar += 1
                grammarCounts[detector.id, default: 0] += 1
            }
            if lineUnknown + lineGrammar <= 1 {
                clearLines += 1
            }
''', "clear line grammar")
s = once(s, '''                               knownShare: knownShare, clearShare: clear, words: words, lines: lineCount, unknown: list,
                               morae: morae)
''', '''                               knownShare: knownShare, clearShare: clear, words: words, lines: lineCount, unknown: list,
                               morae: morae, grammar: grammarCounts)
''', "analysis result grammar")
s = once(s, '''    /// morae a minute while a line is on screen
    var speed: Double? = nil
}
''', '''    /// morae a minute while a line is on screen
    var speed: Double? = nil
    /// unknown grammar points (id) and the lines with them
    var grammar: [String: Int] = [:]
}
''', "episode analysis grammar")
s = within(s, "    func updateCoverage() {", "    /// known share, clear share and coverage of each analysed video",
           "saved.algorithm == TextAnalysis.algorithm {", "saved.algorithm == TextAnalysis.textVersion {",
           "episode cache check")
s = within(s, "    func updateCoverage() {", "    /// known share, clear share and coverage of each analysed video",
           "algorithm: TextAnalysis.algorithm)", "algorithm: TextAnalysis.textVersion)", "episode cache save")
s = within(s, "    private func analyze(_ ncode: String) async {", "let lines = NovelAnalyzer.sentences(text.body)",
           "loaded.algorithm == TextAnalysis.algorithm {", "loaded.algorithm == TextAnalysis.textVersion {",
           "novel cache check")
s = within(s, "    private func analyze(_ ncode: String) async {", "let lines = NovelAnalyzer.sentences(text.body)",
           "algorithm: TextAnalysis.algorithm)", "algorithm: TextAnalysis.textVersion)", "novel cache save")

# ---------- the unknown grammar of an episode ----------
s = within(s, "struct UnknownWordsView: View {", "\nstruct ", '''    /// the word whose line, frame and sound are being found
    @State private var preparing: String? = nil
''', '''    /// the word whose line, frame and sound are being found
    @State private var preparing: String? = nil
    @State private var grammarPoint: GrammarPoint? = nil
''', "series list grammar state")
s = within(s, "struct UnknownWordsView: View {", "\nstruct ",
           "понятных реплик (не больше одного незнакомого слова), ",
           "понятных реплик (не больше одного незнакомого слова или конструкции), ", "series footer rule")
s = within(s, "struct UnknownWordsView: View {", "\nstruct ", '''                    } footer: {
                        Text("Слово открывает словарь на самой понятной реплике серии; ⊕ кладёт в очередь заметку с её звуком и кадром. Свайп вправо — «Знаю», влево — «Игнор».")
                    }
''', '''                    } footer: {
                        Text("Слово открывает словарь на самой понятной реплике серии; ⊕ кладёт в очередь заметку с её звуком и кадром. Свайп вправо — «Знаю», влево — «Игнор».")
                    }
                    let grammar = GrammarDemand.list(result.grammar)
                    if !grammar.isEmpty {
                        Section {
                            ForEach(grammar) { item in
                                Button {
                                    grammarPoint = item.point
                                } label: {
                                    HStack {
                                        VStack(alignment: .leading, spacing: 2) {
                                            Text(item.point.pattern)
                                                .foregroundColor(.primary)
                                            Text("N" + String(item.point.level) + " · " + item.point.short)
                                                .font(.caption)
                                                .foregroundColor(.secondary)
                                        }
                                        Spacer()
                                        Text("×" + String(item.count))
                                            .foregroundColor(.secondary)
                                    }
                                }
                            }
                        } header: {
                            Text("Незнакомая грамматика: " + String(grammar.count))
                        } footer: {
                            Text("Конструкции из колод «Грамматика» (вкладка «Словарь»), которых вы ещё не знаете. Реплика с ними понятна, только если в ней нет незнакомых слов.")
                        }
                    }
''', "series list grammar section")
s = within(s, "struct UnknownWordsView: View {", "\nstruct ", '''            .sheet(item: $lineLookup) { item in
                WordLookupSheet(text: item.text, charAt: item.charAt)
            }
''', '''            .sheet(item: $lineLookup) { item in
                WordLookupSheet(text: item.text, charAt: item.charAt)
            }
            .sheet(item: $grammarPoint) { point in
                NavigationStack {
                    GrammarPointView(point: point)
                }
            }
''', "series list grammar sheet")

s = s.rstrip("\n") + "\n" + (here / "v200-grammar.swift").read_text(encoding="utf-8")
hv.write_text(s, encoding="utf-8")

# ---------- the dictionary tab opens the decks ----------
dv = pathlib.Path("src/safari/iOS (App)/DictionaryView.swift")
t = dv.read_text(encoding="utf-8")
t = once(t, '''    var body: some View {
        YomikiriWebView(url: DictionaryView.URL_DICTIONARY)
            .onLoadFail { error in
''', '''    /// the grammar decks open over the dictionary
    @ObservedObject private var grammar = GrammarPresenter.shared

    var body: some View {
        YomikiriWebView(url: DictionaryView.URL_DICTIONARY)
            .handleExtraMessage { key, _ in
                guard key == "openGrammar" else { return nil }
                await MainActor.run {
                    if #available(iOS 16.0, *) {
                        GrammarPresenter.shared.open = true
                    }
                }
                return .some(nil)
            }
            .onLoadFail { error in
''', "dictionary grammar message")
t = once(t, '''            .ignoresSafeArea(.keyboard)
    }
''', '''            .ignoresSafeArea(.keyboard)
            .fullScreenCover(isPresented: $grammar.open) {
                if #available(iOS 16.0, *) {
                    GrammarHome()
                }
            }
    }
''', "dictionary grammar cover")
dv.write_text(t, encoding="utf-8")

page = pathlib.Path("src/main/src/iosapp/DictionaryView.svelte")
t = page.read_text(encoding="utf-8")
t = once(t, '''  const config = Config.using();
''', '''  const config = Config.using();
  // the grammar decks are native screens of the app
  const app = Platform as unknown as {
    messageWebview(key: string, request: unknown): Promise<unknown>;
  };

  async function openGrammar() {
    await app.messageWebview("openGrammar", null);
  }
''', "page grammar call")
t = once(t, '''      <div class="placeholder-container">
      </div>
''', '''      <div class="placeholder-container">
        {#if context === "app"}
          <button class="grammar-entry" on:click={openGrammar}>
            <span class="grammar-title">文法 · Грамматика</span>
            <span class="grammar-sub">Колоды N5–N1, повторение по FSRS</span>
          </button>
        {/if}
      </div>
''', "page grammar button")
t = once(t, '''  .placeholder-container {
    flex: 1 1 auto;
    background-color: transparent;
    display: flex;
    align-items: center;
  }
''', '''  .placeholder-container {
    flex: 1 1 auto;
    background-color: transparent;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .grammar-entry {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    padding: 18px 28px;
    border-radius: 18px;
    border: 1px solid rgba(255, 255, 255, 0.14);
    background: rgba(255, 255, 255, 0.07);
    -webkit-backdrop-filter: blur(14px);
    backdrop-filter: blur(14px);
    color: var(--text);
    font: inherit;
  }

  .grammar-title {
    font-size: 20px;
    font-weight: 600;
  }

  .grammar-sub {
    font-size: 13px;
    color: var(--text-light);
  }
''', "page grammar style")
page.write_text(t, encoding="utf-8")
print("v2.00 grammar applied")
