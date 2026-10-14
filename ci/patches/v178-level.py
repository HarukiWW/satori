# v1.78: the calibration and the JLPT estimate agree.
# - The calibration asks only frequent words (from half of the number to six times it, never a card) and keeps the
#   answers as a knowledge curve: the share of known words by frequency rank.
# - The JLPT level it suggests is counted from the same curve, the same way as the "Уровень JLPT по словам" page:
#   cards are known, every other JLPT word counts with the share the curve gives for its frequency, a level is reached
#   at 75% of its words and the easier ones. "Применить" keeps the curve, and the page uses it from then on.
# - Before: the page used a hard boundary (only words up to the number, none after it) and the calibration asked 7
#   JLPT words per level, so the two said different things.
# The code is v178-level.swift (it replaces the calibration and the estimate of 1.76-1.77).
import pathlib

here = pathlib.Path(__file__).resolve().parent
hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")
start = '/// The calibration of "Мой уровень японского": words around the present boundaries'
end = "\n/// Words for the calibration and the JLPT estimate, made at build time"
assert s.count(start) == 1 and s.count(end) == 1, "calibration code"
a = s.index(start)
b = s.index(end)
s = s[:a] + (here / "v178-level.swift").read_text(encoding="utf-8") + s[b:]
hv.write_text(s, encoding="utf-8")
print("v1.78 level applied")
