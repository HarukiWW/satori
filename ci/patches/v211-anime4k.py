# v2.11 (KSPlayer): heavier kinds of Anime4K line restoration, Restore CNN M and L (MIT, (c) bloc97), next to the
# light S of 1.45. The shaders are converted by the converter of v145-ksplayer.py into more kernels of the same Metal
# library; the player settings choose the kind (ykAnime4KPreset), S when the chosen one did not convert.
# Usage: python3 v211-anime4k.py Anime4K_Restore_CNN_M.glsl Anime4K_Restore_CNN_L.glsl   (in src/, after v145)
import pathlib
import re
import sys


def once(text, old, new, label):
    assert text.count(old) == 1, "KSPlayer pattern not found exactly once: " + label
    return text.replace(old, new)


here = pathlib.Path(__file__).resolve().parent
ROOT = pathlib.Path("spm/checkouts/KSPlayer/Sources/KSPlayer")

# the converter of 1.45, the same rules for every shader
v145 = (here / "v145-ksplayer.py").read_text(encoding="utf-8")
names = {"re": re}
exec(v145[v145.index("def convert(text):"):v145.index("# ---------- Anime4K passes")], names)
convert, PRELUDE = names["convert"], names["PRELUDE"]

presets = {}
for kind, arg in zip(["M", "L"], sys.argv[1:3]):
    path = pathlib.Path(arg)
    if not path.exists():
        print("Anime4K " + kind + ": shader file missing")
        continue
    try:
        passes = convert(path.read_text(encoding="utf-8"))
    except ValueError as error:
        print("Anime4K " + kind + ": shader not converted (" + str(error) + ")")
        continue
    for item in passes:
        renamed = item["kernel"].replace("a4k_pass_", "a4k" + kind + "_pass_")
        item["source"] = item["source"].replace("kernel void " + item["kernel"] + "(", "kernel void " + renamed + "(")
        item["kernel"] = renamed
    presets[kind] = passes
    print("Anime4K " + kind + ": " + str(len(passes)) + " passes converted to Metal")

path = ROOT / "MEPlayer/YKVideoFilters.swift"
s = path.read_text(encoding="utf-8")

metal = "\n".join(item["source"] for kind in presets for item in presets[kind])
if metal:
    if "static inline float4x4 YKM4(" not in s:
        metal = PRELUDE + "\n" + metal
    assert '"""#' not in metal
    s = once(s, '\n"""#\n', "\n" + metal + '\n"""#\n', "metal source end")


def swift_list(passes):
    return ",\n".join(
        '        Pass(kernel: "%s", inputs: [%s], output: "%s")'
        % (p["kernel"], ", ".join('"%s"' % i for i in p["inputs"]), p["output"]) for p in passes)


heavier = ", ".join('"%s"' % kind for kind in ["M", "L"] if kind in presets)
s = once(s, "    public static var anime4KAvailable: Bool { !passes.isEmpty }\n",
         "    public static var anime4KAvailable: Bool { !passes.isEmpty }\n\n"
         "    static let passesM: [Pass] = [\n" + swift_list(presets.get("M", [])) + "\n    ]\n\n"
         "    static let passesL: [Pass] = [\n" + swift_list(presets.get("L", [])) + "\n    ]\n\n"
         "    /// The stronger kinds of the line restoration converted at build time (Anime4K Restore CNN M, L).\n"
         "    public static let heavierPresets: [String] = [" + heavier + "]\n\n"
         "    /// The passes of the chosen kind (ykAnime4KPreset): S, or M / L when they converted.\n"
         "    static var chosenPasses: [Pass] {\n"
         "        switch UserDefaults.standard.string(forKey: \"ykAnime4KPreset\") {\n"
         "        case \"M\" where !passesM.isEmpty:\n"
         "            return passesM\n"
         "        case \"L\" where !passesL.isEmpty:\n"
         "            return passesL\n"
         "        default:\n"
         "            return passes\n"
         "        }\n"
         "    }\n", "presets")
s = once(s, """            var named = ["MAIN": current]
            for pass in Self.passes {""", """            var named = ["MAIN": current]
            for pass in Self.chosenPasses {""", "chosen passes")
path.write_text(s, encoding="utf-8")
print("KSPlayer v2.11: Anime4K kinds " + (heavier or "none") + " added")
