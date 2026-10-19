# v2.19: the package of the queue works on the first try, adding is quick, the translator retries.
# - «Добавить все» right after an update went one by one: the note types come from the backup, and its reading (tens
#   of seconds for a big collection) had not ended yet. Now the queue waits for that reading, or starts it itself.
#   When the package still cannot be made, Satori says why and offers «Отправить по одной» instead of doing it quietly.
# - The sounds of the package are fetched together (one by one, 30 words of JapanesePod101 took half a minute).
# - Adding a word: the note waits at most 4 seconds for the translation and the check of the word audio; what is not
#   there yet is done by the mining queue in the background (v2.17). The translator gives up on a request after
#   5 seconds, asks the page translator twice, and says «Переводчик Google не ответил» instead of WebKit's «The string
#   did not match the expected pattern» (the old endpoint answered with an error page, not JSON).
import pathlib


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")

# --- why the package was not made
s = once(s, '''        /// a sound or a picture of a note did not download
        case offline(String)
    }''', '''        /// a sound or a picture of a note did not download
        case offline(String)
        /// what the user must know (no backup, a note type the backup does not have)
        case reason(String)
    }''', "reason case")
s = once(s, '''        guard let models = models() else { throw Failure.unknown }
        var notes: [Note] = []''', '''        guard let models = models() else {
            throw Failure.reason("Нет типов заметок из бэкапа AnkiMobile: пакет берёт их оттуда. Выберите папку бэкапов "
                + "в Настройках → Anki.")
        }
        var notes: [Note] = []''', "no models")
s = once(s, '''            guard let notetype = models.notetypes.first(where: { $0.name == param("type") }), notetype.kind == 0 else {
                throw Failure.unknown
            }
            var values: [String: String] = [:]
            for field in MiningReady.fields(of: entry.url) {
                let packed = try await MiningQueue.packed(field.value, of: entry)
                values[field.name] = packed.value
                if let made = packed.file {
                    files.append(made)
                }
            }''', '''            let type = param("type")
            guard let notetype = models.notetypes.first(where: { $0.name == type }) else {
                throw Failure.reason("В бэкапе AnkiMobile нет типа заметок «" + type + "». Сделайте свежий бэкап в "
                    + "AnkiMobile: Satori прочитает его сам.")
            }
            guard notetype.kind == 0 else {
                throw Failure.reason("Тип «" + type + "» с пропусками (cloze): такие заметки уходят только по одной.")
            }
            let values = filled[entry.id]?.values ?? [:]
            files += filled[entry.id]?.files ?? []''', "note type reasons")
s = once(s, '''        var files: [(name: String, data: Data)] = []
        for entry in entries {
            let items = URLComponents(string: entry.url)?.percentEncodedQueryItems ?? []''', '''        var files: [(name: String, data: Data)] = []
        // the files of all the notes are fetched together: one by one, 30 words of JapanesePod101 took half a minute
        let filled = try await withThrowingTaskGroup(of: Filled.self) { group -> [UUID: Filled] in
            for entry in entries {
                group.addTask {
                    var one = Filled(id: entry.id)
                    for field in MiningReady.fields(of: entry.url) {
                        let packed = try await MiningQueue.packed(field.value, of: entry)
                        one.values[field.name] = packed.value
                        if let made = packed.file {
                            one.files.append(made)
                        }
                    }
                    return one
                }
            }
            var all: [UUID: Filled] = [:]
            for try await one in group {
                all[one.id] = one
            }
            return all
        }
        for entry in entries {
            let items = URLComponents(string: entry.url)?.percentEncodedQueryItems ?? []''', "files together")
s = once(s, '''        guard !notes.isEmpty else { throw Failure.unknown }''', '''        guard !notes.isEmpty else {
            throw Failure.reason("У этих заметок нет карточек: лицевая сторона их типа осталась бы пустой.")
        }''', "no cards")
s = once(s, '''    /// One note of the package.
    struct Note {''', '''    /// The fields of a note with its sounds and pictures made files.
    struct Filled: Sendable {
        let id: UUID
        var values: [String: String] = [:]
        var files: [(name: String, data: Data)] = []
    }

    /// One note of the package.
    struct Note {''', "filled type")
s = once(s, '''                    loaded = try await URLSession.shared.data(from: url)''',
         '''                    loaded = try await URLSession.shared.data(for: URLRequest(url: url, timeoutInterval: 15))''',
         "download timeout")

# --- the queue: wait for the backup, say why
s = once(s, '''    /// why the package was not made
    @Published var packFailure = ""
''', '''    /// why the package was not made
    @Published var packFailure = ""
    /// the notes that can still go one by one after it
    @Published var packLeft: [Entry] = []
    /// what the package waits for now
    @Published var packStep = ""
''', "package step")
s = once(s, '''    func sendTogether() {
        guard sending.count > 1, MiningBatch.known, !packing else {
            sendNext()
            return
        }
        let batch = sending
        sending = []
        packing = true
        Task { @MainActor in
            do {
                let made = try await MiningBatch.build(batch)
                packing = false
                MiningBatch.share(made.package) { completed in
                    if completed {
                        self.packed = made.ids
                    }
                }
            } catch MiningBatch.Failure.offline(let host) {
                packing = false
                packFailure = "Не скачался звук с " + host + ". Проверьте интернет и попробуйте ещё раз."
            } catch {
                // a note type the backup does not know: one by one, as before 2.18
                packing = false
                sending = batch
                sendNext()
            }
        }
    }''', '''    func sendTogether() {
        guard sending.count > 1, !packing else {
            sendNext()
            return
        }
        let batch = sending
        sending = []
        packing = true
        Task { @MainActor in
            // the note types come from the backup: its reading (tens of seconds) is waited for, or started now
            let backups = AnkiBackupSync.shared
            if !MiningBatch.known, backups.connected {
                self.packStep = "Читаю бэкап AnkiMobile…"
                if !backups.importing {
                    backups.check(force: true)
                }
                var waited = 0
                while backups.importing, waited < 240 {
                    try? await Task.sleep(nanoseconds: 500_000_000)
                    waited += 1
                }
            }
            self.packStep = "Собираю пакет…"
            var why = ""
            do {
                let made = try await MiningBatch.build(batch)
                self.packing = false
                MiningBatch.share(made.package) { completed in
                    if completed {
                        self.packed = made.ids
                    }
                }
                return
            } catch MiningBatch.Failure.offline(let host) {
                why = "Не скачался звук с " + host + ". Проверьте интернет и попробуйте ещё раз."
            } catch MiningBatch.Failure.reason(let text) {
                why = text
            } catch {
                why = "Пакет не записался: " + String(describing: error)
            }
            self.packing = false
            self.packLeft = batch
            self.packFailure = why
        }
    }

    /// After a package that could not be made: the notes go one by one, as before 2.18.
    func sendOneByOne() {
        sending = packLeft
        packLeft = []
        sendNext()
    }''', "send together")

# --- the queue screen
s = once(s, '''        if queue.packing {
            return "Собираю пакет…"
        }''', '''        if queue.packing {
            return queue.packStep.isEmpty ? "Собираю пакет…" : queue.packStep
        }''', "step title")
s = once(s, '''            Button("OK", role: .cancel) {}
        } message: {
            Text(queue.packFailure)
        }''', '''            if !queue.packLeft.isEmpty {
                Button("Отправить по одной") {
                    queue.sendOneByOne()
                }
            }
            Button("Отмена", role: .cancel) {
                queue.packLeft = []
            }
        } message: {
            Text(queue.packFailure)
        }''', "one by one button")
hv.write_text(s, encoding="utf-8")

# --- the web: the translator and the note do not wait long
tr = pathlib.Path("src/main/src/platform/common/translate.ts")
t = tr.read_text(encoding="utf-8")
t = once(t, '''/**
 * Google's page translator (the one of Chrome)''', '''/** A request that gives up after `ms`, its body read inside that time: a hanging answer must not hold the
 * dictionary or the note. */
async function fetchWithin(url: string, init: RequestInit, ms: number): Promise<{ status: number; text: string }> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), ms);
  try {
    const response = await fetch(url, { ...init, signal: controller.signal });
    return { status: response.status, text: await response.text() };
  } finally {
    clearTimeout(timer);
  }
}

/**
 * Google's page translator (the one of Chrome)''', "fetch within")
t = once(t, '''  const response = await fetch(PAGE_TRANSLATE_URL, {''', '''  const response = await fetchWithin(PAGE_TRANSLATE_URL, {''', "page timeout")
t = once(t, '''  const body = (await response.json()) as string[][];''', '''  const body = JSON.parse(response.text) as string[][];''', "page body")
t = once(t, '''    body: JSON.stringify([[[html], "ja", targetLang], "te_lib"]),
  });''', '''    body: JSON.stringify([[[html], "ja", targetLang], "te_lib"]),
  }, 5000);''', "page timeout end")
t = once(t, '''  const targetLang = "ru";
  try {
    const translated = await pageTranslation(text, targetLang);
    if (translated !== "") {
      const result = { translated };
      translationCache[text] = result;
      return result;
    }
  } catch (err) {
    // the old endpoint below answers when the page translator does not
    console.warn(err);
  }
  const encodedText = encodeURIComponent(text);

  const url = `https://translate.googleapis.com/translate_a/single?client=gtx&sl=ja&tl=${targetLang}&dt=t&dt=bd&dj=1&q=${encodedText}`;
  const response = await fetch(url);
  const respBody = await response.json(); // eslint-disable-line

  if (response.status !== 200) {
    console.error(respBody);
    throw respBody;
  } else {''', '''  const targetLang = "ru";
  // Google answers a burst with an error now and then: the page translator is asked again after a moment
  for (const pause of [0, 700]) {
    if (pause > 0) await new Promise((resolve) => setTimeout(resolve, pause));
    try {
      const translated = await pageTranslation(text, targetLang);
      if (translated !== "") {
        const result = { translated };
        translationCache[text] = result;
        return result;
      }
    } catch (err) {
      // the old endpoint below answers when the page translator does not
      console.warn(err);
    }
  }
  const encodedText = encodeURIComponent(text);

  const url = `https://translate.googleapis.com/translate_a/single?client=gtx&sl=ja&tl=${targetLang}&dt=t&dt=bd&dj=1&q=${encodedText}`;
  let respBody: unknown;
  try {
    const response = await fetchWithin(url, {}, 5000);
    // an error page is HTML, not JSON (WebKit then says «The string did not match the expected pattern»)
    if (response.status !== 200) throw new Error("gtx: " + response.status);
    respBody = JSON.parse(response.text);
  } catch (err) {
    console.error(err);
    throw new Error("Переводчик Google не ответил, попробуйте ещё раз");
  }
  {''', "retry and plain error")
tr.write_text(t, encoding="utf-8")

ab = pathlib.Path("src/main/src/lib/anki/ankiBuilder.ts")
a = ab.read_text(encoding="utf-8")
a = once(a, '''addBuilder("translated-sentence", (_opts, data) => {
  const translatePromise = Platform.translate(data.sentence);''', '''addBuilder("translated-sentence", (_opts, data) => {
  // the note waits 4 seconds at most: the mining queue of the app translates later what is missing
  const translatePromise = Promise.race([
    Platform.translate(data.sentence),
    new Promise<never>((_resolve, reject) => setTimeout(() => reject(new Error("перевод не успел")), 4000)),
  ]);''', "translation wait")
a = once(a, '''  try {
    const resp = await fetch(JPOD101_URL + query);
    if (!resp.ok) return "";
    const buf = await resp.arrayBuffer();''', '''  // the check gives up after 4 seconds: the mining queue of the app checks the link later (MiningReady.unchecked)
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 4000);
  try {
    const resp = await fetch(JPOD101_URL + query, { signal: controller.signal });
    if (!resp.ok) return "";
    const buf = await resp.arrayBuffer();''', "jpod timeout")
a = once(a, '''    // the app's mining queue checks it again (MiningReady.unchecked)
    return JPOD101_URL + query + "&unchecked=1&fakePath=audio.mp3";
  }''', '''    // the app's mining queue checks it again (MiningReady.unchecked)
    return JPOD101_URL + query + "&unchecked=1&fakePath=audio.mp3";
  } finally {
    clearTimeout(timer);
  }''', "jpod timer")
ab.write_text(a, encoding="utf-8")
print("v2.19 fixes applied")
