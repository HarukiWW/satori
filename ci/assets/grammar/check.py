# Checks the grammar decks n5.json … n1.json: the build stops on a broken deck (the app would drop the whole level).
# Each point: a unique id, the level of its file, pattern, short (distinct in its level: the options of the test),
# explanation, two examples or more whose marks are found in order in the sentence, a detect that compiles and finds
# every example.
import json
import pathlib
import re
import sys

here = pathlib.Path(__file__).resolve().parent
keys = {"id", "level", "pattern", "short", "explanation", "formation", "detect", "examples"}
problems = []
seen = set()
total = 0
for level in [5, 4, 3, 2, 1]:
    path = here / ("n" + str(level) + ".json")
    if not path.exists():
        print("warning: no " + path.name)
        continue
    try:
        points = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as error:
        problems.append(path.name + ": " + str(error))
        continue
    shorts = {}
    for point in points:
        where = path.name + ":" + str(point.get("id"))
        for key in ("id", "pattern", "short", "explanation"):
            if not isinstance(point.get(key), str) or not point[key].strip():
                problems.append(where + ": no " + key)
        for key in ("formation", "detect"):
            if key in point and not isinstance(point[key], str):
                problems.append(where + ": " + key + " is not text")
        if set(point) - keys:
            problems.append(where + ": unknown keys " + ", ".join(sorted(set(point) - keys)))
        if point.get("id") in seen:
            problems.append(where + ": the id twice")
        seen.add(point.get("id"))
        if point.get("level") != level:
            problems.append(where + ": level " + str(point.get("level")))
        short = point.get("short", "")
        if short in shorts:
            problems.append(where + ": the short of " + shorts[short])
        shorts[short] = str(point.get("id"))
        if len(short) > 60:
            problems.append(where + ": short longer than 60")
        regex = None
        if isinstance(point.get("detect"), str):
            try:
                regex = re.compile(point["detect"])
            except re.error as error:
                problems.append(where + ": detect: " + str(error))
        examples = point.get("examples")
        if not isinstance(examples, list) or len(examples) < 2:
            problems.append(where + ": fewer than 2 examples")
            continue
        for number, example in enumerate(examples):
            spot = where + " #" + str(number + 1)
            if not isinstance(example, dict) or set(example) != {"ja", "ru", "mark"}:
                problems.append(spot + ": an example needs ja, ru and mark")
                continue
            if not all(isinstance(example[key], str) and example[key].strip() for key in ("ja", "ru", "mark")):
                problems.append(spot + ": empty ja, ru or mark")
                continue
            ja = example["ja"]
            at = 0
            for piece in example["mark"].split("|"):
                found = ja.find(piece, at) if piece else -1
                if found < 0:
                    problems.append(spot + ": mark «" + piece + "» not found in «" + ja + "»")
                    break
                at = found + len(piece)
            if regex is not None and not regex.search(ja):
                problems.append(spot + ": detect does not find «" + ja + "»")
    total += len(points)
    print(path.name + ": " + str(len(points)) + " points")

for problem in problems:
    print("problem: " + problem)
print("grammar points: " + str(total) + ", problems: " + str(len(problems)))
sys.exit(1 if problems else 0)
