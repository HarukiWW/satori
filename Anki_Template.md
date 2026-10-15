## Типы заметок

Типы заметок Anki, которые хорошо работают с Satori. Они достались от Yomikiri, поэтому в Anki называются «Yomikiri…». Подходят для компьютера, iPad и iPhone, поддерживают ночной режим.

Скачайте файл и откройте его в Anki или AnkiMobile:

<a href="./extra/resources/anki/Yomikiri%20Japanese%20Note%20Types.apkg">Japanese Note Types.apkg</a>

## Japanese Word

<p align="center">
  <img src="./extra/resources/anki/yomikiri_anki_jp_word_front.png" height="320"/>
  <img src="./extra/resources/anki/yomikiri_anki_jp_word_back.png" height="320"/>
  <img src="./extra/resources/anki/yomikiri_anki_iphone_jp_word_front.jpeg" height="320"/>
  <img src="./extra/resources/anki/yomikiri_anki_iphone_jp_word_back.jpeg" height="320"/>
</p>

На лицевой стороне — японское слово: нужно вспомнить значение и чтение. На обороте показывается и предложение.

### Настройка в Satori

<p align="center">
  <img src="./extra/resources/anki/yomikiri_anki_template_jp_word.png" height="320"/>
</p>

Рекомендуемый шаблон для этого типа заметок — на скриншоте выше. Шаблон Anki настраивается в Satori: Настройки → Anki → «Настроить шаблон Anki». Кнопка слева от выбора поля открывает его параметры.

## Japanese Context

<p align="center">
  <img src="./extra/resources/anki/yomikiri_anki_jp_context_back.png" height="320"/>
  <img src="./extra/resources/anki/yomikiri_anki_iphone_jp_context_front.jpeg" height="320"/>
  <img src="./extra/resources/anki/yomikiri_anki_iphone_jp_context_back.jpeg" height="320"/>
</p>

На лицевой стороне — слово в настоящем предложении. Лучше выбирать в Satori нужное значение слова, а не добавлять все.

### Настройка в Satori

<p align="center">
  <img src="./extra/resources/anki/yomikiri_anki_template_jp_context.png" height="320"/>
</p>

Рекомендуемый шаблон для этого типа заметок — на скриншоте выше. Настраивается так же, как для Japanese Word.

## Свой тип заметок в стиле Kaishi

Вид как у колоды Kaishi 1.5k, но для майнинга из видео и чтения. На лицевой стороне — слово и предложение, в котором слово выделено синим. На обороте:

- слово с фуриганой;
- значения через точку;
- предложение с фуриганой над каждым кандзи и его перевод;
- две кнопки звука (сначала слово, потом реплика из видео);
- кадр.

Поля: `Word`, `Meaning`, `Sentence`, `SentenceMeaning`, `Audio`, `SectenceAudio`, `Image`, `Furigana`.

### Настройка в Satori

Настройки → Anki → «Настроить шаблон Anki»:

- `Word` — word;
- `Furigana` — word, «Основная форма из словаря», стиль `furigana-anki`;
- `Meaning` — meaning, «Маркированный список», «Макс. переводов» = 3;
- `Sentence` — sentence, «Стиль выбранного слова» = `bold`, «Стиль» = `furigana-anki`;
- `SentenceMeaning` — translated-sentence;
- `Audio` — audio;
- `SectenceAudio` и `Image` — «-»: звук реплики и кадр Satori кладёт туда сам.

### Лицевая сторона

```html
<div class="card">
  <div class="word">{{Word}}</div>
  <div class="sentence">{{kanji:Sentence}}</div>
</div>
```

### Оборот

Скрипт заменяет фуригану Anki обычными блоками и делит чтение по кандзи (じょう|きょう|か): встроенную фуригану AnkiMobile не даёт двигать через CSS.

```html
<div class="card">
  <div class="word">{{furigana:Furigana}}</div>
  <div class="meaning">{{Meaning}}</div>
  <div class="sentence">{{furigana:Sentence}}</div>
  {{#SentenceMeaning}}<div class="translation">{{SentenceMeaning}}</div>{{/SentenceMeaning}}
  <div class="audio">{{Audio}}{{SectenceAudio}}</div>
  {{#Image}}<div class="image">{{Image}}</div>{{/Image}}
</div>
<script>
(function () {
  var SMALL = "ゃゅょぁぃぅぇぉゎャュョァィゥェォヮ";
  var KANJI = /^[㐀-鿿豈-﫿々〆ヶ]$/;

  // чтение по кандзи: じょう|きょう|か; null, если не делится
  function split(reading, count) {
    var parts = [];
    Array.from(reading).forEach(function (c) {
      var last = parts.length - 1;
      if (last >= 0 && (SMALL.indexOf(c) >= 0 || "んンっッーうウいイ".indexOf(c) >= 0)) parts[last] += c;
      else parts.push(c);
    });
    for (var i = parts.length - 1; i > 0 && parts.length > count; i--) {
      if ("くきつちクキツチ".indexOf(parts[i]) >= 0) {
        parts[i - 1] += parts[i];
        parts.splice(i, 1);
      }
    }
    while (parts.length > count) {
      var best = parts.length - 2;
      for (var j = parts.length - 2; j >= 0; j--) {
        if (parts[j].length + parts[j + 1].length < parts[best].length + parts[best + 1].length) best = j;
      }
      parts.splice(best, 2, parts[best] + parts[best + 1]);
    }
    return parts.length === count ? parts : null;
  }

  function box(base, reading) {
    var b = document.createElement("span");
    b.className = "fg";
    b.textContent = base;
    var r = document.createElement("span");
    r.className = "fg-r";
    r.textContent = reading;
    b.appendChild(r);
    return b;
  }

  document.querySelectorAll(".card ruby").forEach(function (ruby) {
    var rt = ruby.querySelector("rt");
    if (!rt) return;
    var reading = rt.textContent.trim();
    ruby.querySelectorAll("rt, rp").forEach(function (part) { part.remove(); });
    var base = ruby.textContent;
    var chars = Array.from(base);
    var parts = chars.length > 1 && chars.every(function (c) { return KANJI.test(c); })
      ? split(reading, chars.length) : null;
    var frag = document.createDocumentFragment();
    if (parts) {
      chars.forEach(function (c, k) { frag.appendChild(box(c, parts[k])); });
    } else {
      frag.appendChild(box(base, reading));
    }
    ruby.replaceWith(frag);
  });

  // длинное чтение раздвигает свой кандзи, чтобы не наезжать на соседнее
  document.querySelectorAll(".card .fg").forEach(function (b) {
    var need = b.querySelector(".fg-r").getBoundingClientRect().width;
    if (need > b.getBoundingClientRect().width) b.style.minWidth = need + "px";
  });
})();
</script>
```

### Таблица стилей

```css
.card {
  font-family: -apple-system, "Hiragino Sans", "Noto Sans JP", sans-serif;
  text-align: center;
  color: #ffffff;
  background-color: #000000;
  padding: 16px 12px;
}
.word { font-size: 44px; font-weight: 400; line-height: 1.3; padding-top: 0.35em; }
.meaning { font-size: 22px; margin: 6px 0 14px; }
.meaning ol, .meaning ul { list-style: none; padding: 0; margin: 0; }
.meaning li::before { content: "• "; }
.meaning li:has(.yomi-glosses)::before { content: none; }
.meaning .yomi-example { display: none !important; }
.sentence { font-size: 21px; line-height: 2.1; }
.sentence b { color: #5b8fd9; }
.translation { font-size: 22px; margin-top: 2px; }
.audio { margin: 14px 0 6px; }
.replay-button svg { width: 44px; height: 44px; margin: 0 6px; }
.image img { display: block; max-width: 100%; max-height: 40vh; height: auto; margin: 8px auto 0; border-radius: 8px; }

/* фуригана из скрипта: bottom — расстояние до кандзи, меньше — ближе */
.fg { position: relative; display: inline-block; line-height: 1; text-align: center; }
.fg-r {
  position: absolute;
  left: 50%;
  bottom: 95%;
  transform: translateX(-50%);
  white-space: nowrap;
  line-height: 1;
}
.word .fg-r { font-size: 0.4em; }
.sentence .fg-r { font-size: 0.5em; }
```

После правки шаблона закройте и заново откройте редактор: повторный предпросмотр в AnkiMobile показывает ошибку JavaScript, хотя шаблон работает.
