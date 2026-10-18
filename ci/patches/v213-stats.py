# v2.13 (the app): the statistics, the player, the captions of YouTube.
# - «Статистика»: Чтение · Грамматика · Просмотр · Прогресс. «Прогресс» (as the page the user sent): the words of
#   the mature cards day by day (from the review log of Anki, kept when a backup is read) and the hours with the
#   language (reading, watching, grammar), each with what the pace of the last month gives in the next 60 days and
#   the days to the next JLPT level by the words.
# - «Дней подряд» counts a day of reading or watching from 10 minutes of it (a minute, or one mined word, counted).
# - Anime4K: «Авто» picks the kind by itself (v213-anime4k.py): down when a frame takes over 30 ms, up when the next
#   one would fit.
# - The player starts its picture again when it stopped while the sound goes on (2 s without a new frame while
#   playing): a seek to the same place resets the decoder, as VLC and nPlayer do. The frames come from v213-anime4k.py.
# - YouTube's automatic captions: the player rolled two lines and cut a line when the next one began, so a phrase
#   could vanish while it was spoken. The words with their times are put together into phrases (a pause, a full
#   stop or a long phrase starts the next), each stays until the next one or a moment after its last word.
import pathlib


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


here = pathlib.Path(__file__).resolve().parent
hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")

# --- statistics: the order of the modes, «Прогресс»
s = once(s, '''                    Text("Чтение").tag(0)
                    Text("Просмотр").tag(1)
                    Text("Грамматика").tag(2)
''', '''                    Text("Чтение").tag(0)
                    Text("Грамматика").tag(2)
                    Text("Просмотр").tag(1)
                    Text("Прогресс").tag(3)
''', "stats modes")
s = once(s, '''                if mode != 2 {
                    Picker("Период", selection: $period) {''', '''                if mode < 2 {
                    Picker("Период", selection: $period) {''', "stats period picker")
s = once(s, '''                if mode == 2 {
                    if #available(iOS 16.0, *) {
                        GrammarStatsView()
                    }
                } else {
''', '''                if mode == 2 {
                    if #available(iOS 16.0, *) {
                        GrammarStatsView()
                    }
                } else if mode == 3 {
                    if #available(iOS 16.0, *) {
                        ProgressStatsView(model: model)
                    }
                } else {
''', "stats progress branch")

# --- streaks from 10 minutes a day
s = once(s, '''    /// Days in a row with at least a minute of watching.
    func watchStreak() -> Int {
        func isActive(_ key: String) -> Bool {
            (watch[key]?.time ?? 0) >= 60
        }''', '''    /// Days in a row with at least 10 minutes of watching.
    func watchStreak() -> Int {
        func isActive(_ key: String) -> Bool {
            (watch[key]?.time ?? 0) >= 600
        }''', "watch streak")
s = once(s, '''            return day.read >= 50 || !day.mined.isEmpty
''', '''            // 10 minutes of reading: a minute, or one word added, made a day before
            return day.time >= 600
''', "read streak")

# --- Anime4K: «Авто»
s = once(s, '''                                      Text("S — лёгкая").tag("S")
''', '''                                      Text("Авто").tag("auto")
                                      Text("S — лёгкая").tag("S")
''', "anime4k auto")

# --- the player: a picture that stopped is started again
s = once(s, '''    @State private var lastResync: CFTimeInterval = 0
''', '''    @State private var lastResync: CFTimeInterval = 0
    /// since when the video plays without a pause, a seek or a swipe (the watch of the frames starts there)
    @State private var steadySince: CFTimeInterval = 0
    @State private var lastRecovery: CFTimeInterval = 0
''', "watch state")
s = once(s, '''        updateNowPlaying()
        detectSkipSegments()
        checkEnd()
        saveCoverFrame()
    }
''', '''        updateNowPlaying()
        detectSkipSegments()
        checkEnd()
        saveCoverFrame()
        watchFrames()
    }

    /// The picture stopped while the sound goes on: 2 s without a new frame while playing. A seek to the same place
    /// resets the decoder (VLC and nPlayer do the same); at most every 6 s.
    private func watchFrames() {
        let now = CACurrentMediaTime()
        guard let layer = coordinator.playerLayer, layer.player is KSMEPlayer, layer.player.isPlaying,
              scrubTo == nil, swipeStart == nil, duration > 0 else {
            steadySince = now
            return
        }
        let last = YKFrameWatch.lastFrame
        guard last > 0, now - max(last, steadySince) > 2, now - lastRecovery > 6 else { return }
        lastRecovery = now
        steadySince = now
        CrashTrail.mark("плеер: кадр стоял 2 с, перезапуск вывода")
        layer.seek(time: layer.player.currentPlaybackTime, autoPlay: true) { _ in }
    }
''', "watch frames")

# --- YouTube: the automatic captions in phrases
s = once(s, '''      function parse(text) {
        var cues = [];
        try {
          var j = JSON.parse(text);
          (j.events || []).forEach(function (e) {''', '''      // automatic captions: the words with their times, put together into phrases that stay until they are spoken
      function phrases(j) {
        var words = [];
        (j.events || []).forEach(function (e) {
          (e.segs || []).forEach(function (g) {
            var s = (g.utf8 || '').replace(/\\n/g, '').trim();
            if (s) words.push({ t: ((e.tStartMs || 0) + (g.tOffsetMs || 0)) / 1000, s: s });
          });
        });
        words.sort(function (a, b) { return a.t - b.t; });
        var list = [], cur = null;
        words.forEach(function (w) {
          if (cur && w.t === cur.last && w.s === cur.tail) return;
          if (!cur || w.t - cur.last > 0.9 || cur.text.length >= 28 || w.t - cur.start > 7 || /[。？！?!]$/.test(cur.text)) {
            if (cur) list.push(cur);
            cur = { start: w.t, last: w.t, text: '', tail: '' };
          }
          cur.text += w.s;
          cur.last = w.t;
          cur.tail = w.s;
        });
        if (cur) list.push(cur);
        return list.map(function (c, i) {
          var next = i + 1 < list.length ? list[i + 1].start : c.last + 3;
          var end = next - c.last <= 2 ? next : c.last + 1.5;
          return [Math.max(0, c.start - 0.15), end, c.text];
        });
      }
      function parse(text) {
        var cues = [];
        try {
          var j = JSON.parse(text);
          if ((j.events || []).some(function (e) { return (e.segs || []).some(function (g) { return g.tOffsetMs !== undefined; }); })) {
            return phrases(j);
          }
          (j.events || []).forEach(function (e) {''', "youtube phrases")

s = s.rstrip("\n") + "\n" + (here / "v213-stats.swift").read_text(encoding="utf-8")
hv.write_text(s, encoding="utf-8")

# --- the history of the mature words from the review log of a backup
ai = pathlib.Path("src/main/src/lib/ankiImport.ts")
a = ai.read_text(encoding="utf-8")
a = once(a, '''export async function readAnkiDeck(buf: ArrayBuffer): Promise<{ words: string[]; mature: string[] }> {''',
         '''export async function readAnkiDeck(
  buf: ArrayBuffer,
): Promise<{ words: string[]; mature: string[]; history: [string, number][] }> {''', "deck type")
a = once(a, '''      "select n.mid, n.flds, max(case when c.type = 2 and c.ivl >= 21 then 1 else 0 end) " +
        "from notes n left join cards c on c.nid = n.id group by n.id",
    );''', '''      "select n.mid, n.flds, max(case when c.type = 2 and c.ivl >= 21 then 1 else 0 end), n.id " +
        "from notes n left join cards c on c.nid = n.id group by n.id",
    );
    const wordOfNote = new Map<number, string>();''', "deck select")
a = once(a, '''      words.add(word);
      if (Number(row[2]) === 1) mature.add(word);
    }
    return { words: Array.from(words), mature: Array.from(mature) };''', '''      words.add(word);
      wordOfNote.set(Number(row[3]), word);
      if (Number(row[2]) === 1) mature.add(word);
    }
    return { words: Array.from(words), mature: Array.from(mature), history: matureHistory(db, wordOfNote) };''',
         "deck return")
a = once(a, '''/** Words of all notes, and the words of notes with a mature card (a review interval of 21 days or more). */''',
         '''/** Per day of the review log, the words with a mature card at its end (only the days where the number changes). */
function matureHistory(db: any, wordOfNote: Map<number, string>): [string, number][] {
  const history: [string, number][] = [];
  try {
    const noteOfCard = new Map<number, number>();
    const cards = db.exec("select id, nid from cards");
    for (const row of cards[0] ? cards[0].values : []) {
      if (wordOfNote.has(Number(row[1]))) noteOfCard.set(Number(row[0]), Number(row[1]));
    }
    const interval = new Map<number, number>();
    const matureCards = new Map<number, number>();
    const matureNotes = new Map<string, number>();
    const pad = (n: number) => (n < 10 ? "0" : "") + n;
    let count = 0;
    let day = "";
    const reviews = db.exec("select id, cid, ivl from revlog order by id");
    for (const row of reviews[0] ? reviews[0].values : []) {
      const card = Number(row[1]);
      const note = noteOfCard.get(card);
      if (note === undefined) continue;
      const date = new Date(Number(row[0]));
      const key = date.getFullYear() + "-" + pad(date.getMonth() + 1) + "-" + pad(date.getDate());
      if (key !== day) {
        if (day !== "" && (history.length === 0 || history[history.length - 1][1] !== count)) history.push([day, count]);
        day = key;
      }
      const was = (interval.get(card) ?? 0) >= 21;
      const now = Number(row[2]) >= 21;
      interval.set(card, Number(row[2]));
      if (was === now) continue;
      const word = wordOfNote.get(note) ?? "";
      const onNote = (matureCards.get(note) ?? 0) + (now ? 1 : -1);
      matureCards.set(note, onNote);
      // a note became mature or stopped being so: so did its word, unless another note of the word is
      if ((now && onNote === 1) || (!now && onNote === 0)) {
        const onWord = (matureNotes.get(word) ?? 0) + (now ? 1 : -1);
        matureNotes.set(word, onWord);
        if (now && onWord === 1) count++;
        if (!now && onWord === 0) count--;
      }
    }
    if (day !== "") history.push([day, count]);
  } catch (e) {
    // a collection without a review log: no history
  }
  return history;
}

/** Words of all notes, and the words of notes with a mature card (a review interval of 21 days or more). */''',
         "history function")
a = once(a, '''export async function importDeck(
  deck: { words: string[]; mature: string[] },
  replaceMature = false,
): Promise<{ added: number }> {''', '''export async function importDeck(
  deck: { words: string[]; mature: string[]; history?: [string, number][] },
  replaceMature = false,
): Promise<{ added: number }> {''', "import type")
a = once(a, '''  data.matureUpdated = new Date().toISOString();
''', '''  data.matureUpdated = new Date().toISOString();
  // a whole collection: its review log gives the words of «Статистика → Прогресс» day by day
  if (replaceMature && Array.isArray(deck.history) && deck.history.length > 0) data.matureHistory = deck.history;
''', "import history")
ai.write_text(a, encoding="utf-8")
print("v2.13 statistics, player and captions applied")
