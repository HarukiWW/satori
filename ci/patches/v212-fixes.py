# v2.12: fixes.
# - Anime4K: see v212-anime4k.py (it replaces v211-anime4k.py in the build): 2.11 broke all the picture filters.
# - The voice: iOS gives apps no Siri voices, only the voices of Устной контент (Кёко, Отоя, O-ren and their
#   «улучшенный», the Eloquence ones). «Как в настройках iOS» now also asks iOS for the settings of its assistive
#   speech (prefersAssistiveTechnologySettings), and the Eloquence voices are marked in the list.
import pathlib


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


gl = pathlib.Path("src/safari/Shared (iOS)/Globals.swift")
g = gl.read_text(encoding="utf-8")
g = once(g, '''    if ssVoice == nil {
        ssVoice = AVSpeechSynthesisVoice(language: "ja-JP")
    }
''', '''    if ssVoice == nil {
        ssVoice = AVSpeechSynthesisVoice(language: "ja-JP")
        // no voice chosen: the voice of the speech settings of iOS, when it lets an app use it
        utterance.prefersAssistiveTechnologySettings = true
    }
''', "assistive voice")
gl.write_text(g, encoding="utf-8")

hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")
s = once(s, '''    static func label(_ voice: TTSVoice) -> String {
        if voice.quality >= 300 {''', '''    static func label(_ voice: TTSVoice) -> String {
        if voice.id.lowercased().contains("eloquence") {
            return voice.name + " · Eloquence"
        }
        if voice.quality >= 300 {''', "eloquence label")
hv.write_text(s, encoding="utf-8")
print("v2.12 fixes applied")
