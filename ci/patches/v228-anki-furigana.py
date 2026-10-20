# v2.28: the furigana of numbers in the Anki fields. UniDic reads a number digit by digit (12号 -> 1[いち] 2[に] 号[ごう]),
# so a number keeps no furigana; and digits are part of a ruby base, so kana before a number is matched against the
# reading instead of being swallowed by it (たった１人[たったひとり] -> たった １人[ひとり], １つ -> １[ひと]つ).
import pathlib


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


p = pathlib.Path("src/main/src/lib/japanese.ts")
t = p.read_text(encoding="utf-8")
t = once(t, r'''const RE_KANJI_SEGMENT_SPLIT = new RegExp(
  `(${RE_KANJI.source}*)(${RE_NOKANJI.source}*)`,
  "g",
);
''', r'''// Satori: digits and 々〆ヶ belong to a ruby base like kanji, so the kana around a number is matched against the reading
const RE_RUBY_BASE = /[㐀-䶿一-鿿豈-﫿々〆ヶ0-9０-９]/u;
const RE_NO_RUBY_BASE = /[^㐀-䶿一-鿿豈-﫿々〆ヶ0-9０-９]/u;
const RE_DIGITS = /^[0-9０-９]+$/u;
const RE_KANJI_SEGMENT_SPLIT = new RegExp(
  `(${RE_RUBY_BASE.source}*)(${RE_NO_RUBY_BASE.source}*)`,
  "g",
);
''', "segment split")
t = once(t, '''      return [{ base: text }];
    }

    const [kanjiSegs, noKanjiSegs] = splitKanjiSegments(text);
''', '''      return [{ base: text }];
    }
    // Satori: UniDic reads a number digit by digit (12 -> 1[いち] 2[に]), so a number keeps no furigana
    if (RE_DIGITS.test(text)) {
      return [{ base: text }];
    }

    const [kanjiSegs, noKanjiSegs] = splitKanjiSegments(text);
''', "digits only")
t = once(t, '''    return rubyString;
  }

  export function fromToken''', '''    // Satori: a part read as itself (digits written in the reading: w1) is plain text, joined with its neighbours
    const merged: RubyString = [];
    for (const unit of rubyString) {
      const plain = unit.ruby === undefined || toHiragana(unit.ruby) === toHiragana(unit.base);
      const last = merged[merged.length - 1];
      if (plain && last !== undefined && last.ruby === undefined) {
        last.base += unit.base;
      } else {
        merged.push(plain ? { base: unit.base } : unit);
      }
    }
    return merged;
  }

  export function fromToken''', "merge plain parts")
p.write_text(t, encoding="utf-8")
print("v2.28 anki furigana applied")
