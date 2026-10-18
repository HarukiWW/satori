# The sentences of the grammar decks read aloud in advance (v2.15): one MP3 per sentence in audio/, named by the
# first 16 hex digits of the SHA-256 of its text, so the app finds it without a list. The voice is Microsoft's
# neural Nanami (the voices of Edge's «Read aloud», through the edge-tts package), a little slower for learners.
# Only the missing files are made, and files no sentence uses any more are removed. Run it after editing a deck:
#   python -m venv env && env/bin/pip install edge-tts && env/bin/python ci/assets/grammar/voice.py
import asyncio
import hashlib
import json
import pathlib

import edge_tts

VOICE = "ja-JP-NanamiNeural"
RATE = "-8%"
here = pathlib.Path(__file__).resolve().parent
out = here / "audio"


def name(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16] + ".mp3"


async def make(text, path, gate):
    async with gate:
        for attempt in range(4):
            try:
                await edge_tts.Communicate(text, VOICE, rate=RATE).save(str(path) + ".part")
                pathlib.Path(str(path) + ".part").replace(path)
                return True
            except Exception as error:
                print("retry", attempt + 1, text, error)
                await asyncio.sleep(2 + attempt * 3)
        return False


async def main():
    out.mkdir(exist_ok=True)
    sentences = {}
    for level in [5, 4, 3, 2, 1]:
        for point in json.loads((here / ("n%d.json" % level)).read_text(encoding="utf-8")):
            for example in point["examples"]:
                sentences[name(example["ja"])] = example["ja"]
    for old in out.glob("*.mp3"):
        if old.name not in sentences:
            old.unlink()
    missing = [(text, out / file) for file, text in sentences.items() if not (out / file).exists()]
    print("sentences:", len(sentences), "to make:", len(missing))
    gate = asyncio.Semaphore(4)
    done = await asyncio.gather(*(make(text, path, gate) for text, path in missing))
    failed = [text for (text, _), ok in zip(missing, done) if not ok]
    print("made:", len(missing) - len(failed), "failed:", len(failed))
    for text in failed:
        print("  ", text)


asyncio.run(main())
