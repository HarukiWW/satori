# v1.79: the settings take a new accent color at once (the menus kept the old one until a restart: the settings are
# drawn again when the color changes), and shorter explanations everywhere.
import pathlib


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")

# ---------- the accent color in the settings ----------
s = once(s, '''        .onAppear {
            config.reload()
            imported = ImportedWords.counts()
        }
''', '''        // the menus take the new accent color only when they are made again
        .id(accent)
        .onAppear {
            config.reload()
            imported = ImportedWords.counts()
        }
''', "accent redraw")

# ---------- shorter explanations ----------
s = once(s, '''    private var levelFooter: String {
        let rules: String = "Для покрытия и сложности знакомыми считаются зрелые карточки Anki (интервал от 21 дня, "
            + "из импорта колоды), слова JLPT до этого уровня и столько самых частых слов (Jiten). 0 — по уровню: "
            + "N5 ≈ 800, N4 ≈ 1500, N3 ≈ 3700, N2 ≈ 6000, N1 ≈ 10 000. Калибровка уточняет оба числа по вашим ответам. "
            + "Подсветка на это не влияет."
        if imported.all > 0 && !imported.scheduled {
            return rules + " Колода импортирована до 1.76: пока считаются все её карточки — импортируйте её заново."
        }
        return rules
    }
''', '''    private var levelFooter: String {
        let rules: String = "Знакомые слова для покрытия и сложности: зрелые карточки Anki, JLPT до этого уровня и столько "
            + "самых частых слов. 0 — по уровню (от 800 для N5 до 10 000 для N1)."
        if imported.all > 0 && !imported.scheduled {
            return rules + " Колода импортирована до 1.76 — импортируйте её заново."
        }
        return rules
    }
''', "level footer")
s = once(s, '''        var text: String = "Очередь майнинга: кнопка ⊕ в видео и в чтении кладёт заметку в очередь, а не открывает "
            + "AnkiMobile. Очередь — кнопка вверху вкладок «Видео» и «Чтение»."
        if imported.all > 0 {
            text += " Импортировано слов: " + String(imported.all)
            if imported.scheduled {
                text += ", из них зрелых: " + String(imported.mature)
            }
            text += ". Импорт можно повторять: новые зрелые карточки добавятся."
        }
''', '''        var text: String = "Очередь майнинга: ⊕ кладёт заметку в очередь вместо AnkiMobile."
        if imported.all > 0 {
            text += " Импортировано слов: " + String(imported.all)
            if imported.scheduled {
                text += ", зрелых: " + String(imported.mature)
            }
            text += "."
        }
''', "anki footer")
s = once(s, 'Text("Выделяет слова, которых ещё нет в Anki: от первого места до второго (1 — самое частое слово). В Safari после изменения обновите страницу.")',
         'Text("Выделяет слова, которых нет в Anki, с места «от» до «до» (1 — самое частое). В Safari обновите страницу.")',
         "highlight footer")
s = once(s, '''        let rules: String = "easy: от 90% знакомых слов и 65% понятных реплик; normal: от 80% и 40%; иначе hard. "
            + "Понятная реплика — не больше одного незнакомого слова. "
        let speed: String = "Быстрая речь (больше 320 мор/мин) понижает оценку, медленная — повышает: каждые 50 мор/мин — "
            + "как 4% знакомых слов и 10% понятных реплик. "
        let settings: String = "Знакомыми считаются зрелые карточки Anki, JLPT до N" + String(level) + " и "
            + String(VideoLibraryStore.vocabulary(level: level)) + " частых слов."
        return rules + speed + settings
''', '''        let rules: String = "easy — от 90% знакомых слов и 65% понятных реплик (не больше одного незнакомого слова), "
            + "normal — от 80% и 40%. Быстрая речь понижает оценку, медленная — повышает. "
        let settings: String = "Знакомые: зрелые карточки, JLPT до N" + String(level) + " и "
            + String(VideoLibraryStore.vocabulary(level: level)) + " частых слов."
        return rules + settings
''', "episode footer")
s = once(s, 'Text("Очередь пуста. Включите «Очередь майнинга» (Настройки → Anki или меню плеера) и добавляйте слова кнопкой ⊕ в словаре.")',
         'Text("Очередь пуста. Включите «Очередь майнинга» в Настройках → Anki или в меню плеера.")', "queue empty")
s = once(s, 'Text("Нажмите на слово, чтобы открыть словарь; ⊕ кладёт его в очередь майнинга.")',
         'Text("Слово открывает словарь, ⊕ — в очередь майнинга.")', "episode words footer")
s = once(s, 'Text("«Моё покрытие» ставит выше тайтлы, которые вы поймёте лучше всего (среди уже посчитанных).")',
         'Text("«Моё покрытие» — выше то, что вы поймёте лучше (из уже посчитанных).")', "filter footer")
s = once(s, '''                Text("Все незнакомые слова, самые частые сверху. Нажмите на слово, чтобы открыть словарь; ⊕ кладёт его "
                     + "в очередь майнинга.")''', '''                Text("Самые частые сверху. Слово открывает словарь, ⊕ — в очередь майнинга.")''', "title words footer")
s = once(s, 'Text("Ищет на syosetu.com (小説家になろう). Можно вставить ссылку вида ncode.syosetu.com/n1234ab/ или код n1234ab.")',
         'Text("Поиск по syosetu.com, ссылка ncode.syosetu.com/n1234ab/ или код n1234ab.")', "novel add footer")
s = once(s, 'Text("Главы скачиваются по одной, примерно раз в секунду, и потом читаются без интернета.")',
         'Text("Скачанные главы читаются без интернета.")', "downloads footer")
s = once(s, 'Text("Считается по скачанным главам так же, как у серий: знакомые слова и понятные предложения. Том сворачивается нажатием на него, ↓ скачивает его главы; свайп по главе → «Слова».")',
         'Text("По скачанным главам, как у серий. Нажмите на том, чтобы свернуть; свайп по главе — «Слова».")', "novel footer")
s = once(s, 'Text("Знакомыми считаются ваши зрелые карточки Anki, слова JLPT до вашего уровня и частые слова (Настройки → «Мой уровень японского»). Доля учитывает, как часто слово встречается. Оценка: easy от 90%, normal от 80%; быстрая речь понижает её, медленная — повышает.")',
         'Text("Знакомые: зрелые карточки, JLPT до вашего уровня и частые слова. easy — от 90%, normal — от 80%, с поправкой на скорость речи.")',
         "catalog detail footer")
s = once(s, 'Text("Берутся японские субтитры самого YouTube: сначала сделанные людьми, иначе автоматические. Кнопка ⊕ в словаре добавляет слово в Anki или в очередь майнинга, в карточку идёт снимок плеера или обложка видео.")',
         'Text("Японские субтитры YouTube: ручные, а если их нет — автоматические.")', "youtube footer")
s = once(s, 'Text("Кнопка ⊕ в словаре кладёт заметку в очередь, а не открывает AnkiMobile. Тот же переключатель — в Настройках → Anki. Очередь — кнопка вверху вкладки «Видео».")',
         'Text("⊕ кладёт заметку в очередь вместо AnkiMobile.")', "player queue footer")
hv.write_text(s, encoding="utf-8")

# ---------- the deck import page ----------
page = pathlib.Path("src/main/src/components/options/groups/GroupAnkiImport.svelte")
t = page.read_text(encoding="utf-8")
t = once(t, '''  <div class="note">
    Экспортируйте колоду из AnkiMobile (.colpkg или .apkg с расписанием) и в меню «Поделиться» выберите Satori —
    импорт начнётся сам. Или выберите файл здесь. Все слова колоды перестанут подсвечиваться, а в покрытии и сложности
    будут учитываться слова зрелых карточек (интервал от 21 дня). Импорт можно повторять: новые зрелые карточки
    добавятся.
  </div>
''', '''  <div class="note">
    В AnkiMobile экспортируйте колоду (.colpkg или .apkg с расписанием) и в «Поделиться» выберите Satori. В покрытии
    учитываются зрелые карточки (интервал от 21 дня).
  </div>
''', "import note")
t = once(t, '''    status =
      `Слов в колоде: ${deck.words.length}, новых: ${result.added}, зрелых (интервал от 21 дня): ${deck.mature.length}. ` +
      "Все слова колоды больше не подсвечиваются; в покрытии и сложности учитываются только зрелые.";
    if (deck.words.length > 0 && deck.mature.length === 0) {
      status +=
        " Зрелых карточек нет: похоже, колода экспортирована без расписания. Экспортируйте .colpkg " +
        "или .apkg с включённым Include scheduling information.";
    }
''', '''    status = `Слов: ${deck.words.length}, новых: ${result.added}, зрелых: ${deck.mature.length}.`;
    if (deck.words.length > 0 && deck.mature.length === 0) {
      status += " Зрелых нет — экспортируйте с Include scheduling information.";
    }
''', "import status")
page.write_text(t, encoding="utf-8")
print("v1.79 ui applied")
