# v2.12 (KSPlayer): Anime4K Restore CNN M and L that compile. Replaces v211-anime4k.py in the build.
# - 2.11 broke all the filters: the M and L shaders also define macros without arguments (g_0, g_1 …: one texel of
#   a texture), the converter of 1.45 took only go_0(x_off, y_off), so the Metal library did not compile, S with it.
#   Every #define of a pass is converted now, with the same rules as the code of the pass.
# - Each kind is compiled here with the Metal compiler of Xcode before it goes into the app: a kind that does not
#   compile is left out (with the error in the log), so the filters of the app always compile.
# Usage: python3 v212-anime4k.py Anime4K_Restore_CNN_M.glsl Anime4K_Restore_CNN_L.glsl   (in src/, after v145)
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile


def once(text, old, new, label):
    assert text.count(old) == 1, "KSPlayer pattern not found exactly once: " + label
    return text.replace(old, new)


here = pathlib.Path(__file__).resolve().parent
ROOT = pathlib.Path("spm/checkouts/KSPlayer/Sources/KSPlayer")
v145 = (here / "v145-ksplayer.py").read_text(encoding="utf-8")
PRELUDE = v145[v145.index("PRELUDE = '''") + len("PRELUDE = '''"):v145.index("'''", v145.index("PRELUDE = '''") + 13)]


def translate(code, where):
    """GLSL of a pass (its body or a #define) into Metal: textures read at the thread's texel or at an offset."""
    code = re.sub(r'(\w+)_texOff\(vec2\(([^,()]+), ([^()]+)\)\)', r'YKT(\1, \2, \3)', code)
    code = re.sub(r'(\w+)_tex\(\1_pos\)', r'\1.read(gid)', code)
    # max(x, 0.0) of GLSL takes a vector and a number; Metal wants two vectors
    code = code.replace(', 0.0))', ', float4(0.0)))')
    code = code.replace('mat4(', 'YKM4(')
    code = re.sub(r'\bvec([234])\b', r'float\1', code)
    if re.search(r'\w_(pos|pt|size|texOff|tex)\b|HOOKED|\btexture\(|\bvec[234]\b|\bmat[234]\b', code):
        raise ValueError(where + ': unsupported construct')
    return code


def convert(text, kind):
    passes = []
    blocks = re.split(r'(?m)^//!DESC ', text)[1:]
    for index, block in enumerate(blocks):
        where = kind + " pass " + str(index)
        binds = re.findall(r'(?m)^//!BIND (\w+)\s*$', block)
        save = re.search(r'(?m)^//!SAVE (\w+)\s*$', block)
        hook = re.search(r'(?m)^//!HOOK (\w+)\s*$', block)
        if not hook or hook.group(1) != 'MAIN':
            raise ValueError(where + ': only MAIN hooks are supported')
        for key in ('WIDTH', 'HEIGHT'):
            m = re.search(rf'(?m)^//!{key} (\S+)\s*$', block)
            if m and not re.fullmatch(r'\w+\.[wh]', m.group(1)):
                raise ValueError(where + ': scaled pass')
        if re.search(r'(?m)^//!(WHEN|OFFSET)', block):
            raise ValueError(where + ': WHEN/OFFSET')
        body = re.search(r'vec4 hook\(\)\s*\{(.*)\}\s*$', block, re.S)
        if not body:
            raise ValueError(where + ': hook() not found')
        defines = re.findall(r'(?m)^#define (\w+(?:\([^)]*\))?) (.+)$', block)
        lines = ['    #define ' + head + ' ' + translate(expr, where) for head, expr in defines]
        code = translate(body.group(1), where)
        code = re.sub(r'return ([^;]+);', r'ykOut.write(\1, gid); return;', code)
        args = ',\n'.join(f'    texture2d<float, access::read> {b} [[texture({i})]]' for i, b in enumerate(binds))
        kernel = f'a4k{kind}_pass_{index}'
        source = (f'kernel void {kernel}(\n{args},\n'
                  f'    texture2d<float, access::write> ykOut [[texture({len(binds)})]],\n'
                  f'    uint2 gid [[thread_position_in_grid]]) {{\n'
                  f'    if (gid.x >= ykOut.get_width() || gid.y >= ykOut.get_height()) {{ return; }}\n'
                  f'    int2 p = int2(gid);\n'
                  f'    int2 lim = int2(int(ykOut.get_width()) - 1, int(ykOut.get_height()) - 1);\n'
                  + '\n'.join(lines) + '\n' + code.strip('\n') + '\n'
                  + '\n'.join('    #undef ' + head.split('(')[0] for head, _ in defines) + '\n}\n')
        passes.append({'kernel': kernel, 'inputs': binds, 'output': save.group(1) if save else 'MAIN',
                       'source': source})
    if not passes or passes[-1]['output'] != 'MAIN':
        raise ValueError(kind + ': the last pass must write MAIN')
    return passes


def metal_compiler():
    """Xcode's Metal compiler is there (newer Xcodes download it as a component)."""
    if not shutil.which("xcrun"):
        return False
    probe = subprocess.run(["xcrun", "-sdk", "iphoneos", "metal", "--version"], capture_output=True, text=True)
    if probe.returncode != 0:
        print("Anime4K: no Metal compiler here, the kinds are not checked (" + probe.stderr.strip()[:300] + ")")
        return False
    return True


CHECK = metal_compiler()


def compiles(source, label):
    """The Metal compiler of Xcode on the source; True without one."""
    if not CHECK:
        return True
    with tempfile.TemporaryDirectory() as folder:
        metal = pathlib.Path(folder) / "check.metal"
        metal.write_text(source, encoding="utf-8")
        done = subprocess.run(["xcrun", "-sdk", "iphoneos", "metal", "-c", str(metal), "-o", str(metal) + ".air"],
                              capture_output=True, text=True)
    if done.returncode != 0:
        print("Anime4K " + label + ": Metal does not compile it, left out:\n" + done.stderr[-3000:])
        return False
    return True


path = ROOT / "MEPlayer/YKVideoFilters.swift"
s = path.read_text(encoding="utf-8")
start = s.index('static let source = #"""\n') + len('static let source = #"""\n')
end = s.index('\n"""#\n', start)
metal = s[start:end]
if not compiles(metal, "S"):
    print("Anime4K: the filters of 1.45 do not compile")
prelude = "" if "static inline float4x4 YKM4(" in metal else PRELUDE + "\n"

presets = {}
for kind, arg in zip(["M", "L"], sys.argv[1:3]):
    file = pathlib.Path(arg)
    if not file.exists():
        print("Anime4K " + kind + ": shader file missing")
        continue
    try:
        passes = convert(file.read_text(encoding="utf-8"), kind)
    except ValueError as error:
        print("Anime4K " + kind + ": shader not converted (" + str(error) + ")")
        continue
    candidate = metal + "\n" + prelude + "\n".join(item["source"] for item in passes)
    if not compiles(candidate, kind):
        continue
    metal = candidate
    prelude = ""
    presets[kind] = passes
    print("Anime4K " + kind + ": " + str(len(passes)) + " passes converted and compiled")

assert '"""#' not in metal
s = s[:start] + metal + s[end:]


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
print("KSPlayer v2.12: Anime4K kinds " + (heavier or "none") + " added")
