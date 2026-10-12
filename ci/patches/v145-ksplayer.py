# v1.45 (KSPlayer): picture enhancement for anime and a smoother return to the video.
# 1) YKVideoFilters: deband, Anime4K line restoration (Restore CNN S, MIT, (c) bloc97) and contrast adaptive
#    sharpening on the decoded frame. The shaders are compiled on the device; when that fails the frame is drawn the
#    usual way and the error is shown in the player settings. With a filter on, plane video is drawn through Metal
#    (the system display layer cannot run shaders).
# 2) For 3 s after a seek, late video frames are dropped one by one instead of dropping everything up to the next key
#    frame (that froze the picture until the next scene change after a return from another app).
# Usage: python3 v145-ksplayer.py [Anime4K_Restore_CNN_S.glsl]   (runs in src/, after ksplayer_build_patches.py)
import pathlib, re, sys

ROOT = pathlib.Path("spm/checkouts/KSPlayer/Sources/KSPlayer")


def once(text, old, new, label):
    assert text.count(old) == 1, "KSPlayer pattern not found exactly once: " + label
    return text.replace(old, new)



def convert(text):
    passes = []
    blocks = re.split(r'(?m)^//!DESC ', text)[1:]
    for index, block in enumerate(blocks):
        header = dict()
        binds = re.findall(r'(?m)^//!BIND (\w+)\s*$', block)
        save = re.search(r'(?m)^//!SAVE (\w+)\s*$', block)
        hook = re.search(r'(?m)^//!HOOK (\w+)\s*$', block)
        if not hook or hook.group(1) != 'MAIN':
            raise ValueError(f'pass {index}: only MAIN hooks are supported')
        for key in ('WIDTH', 'HEIGHT'):
            m = re.search(rf'(?m)^//!{key} (\S+)\s*$', block)
            if m and not re.fullmatch(r'\w+\.[wh]', m.group(1)):
                raise ValueError(f'pass {index}: scaled pass ({key} {m.group(1)}) is not supported')
        if re.search(r'(?m)^//!(WHEN|OFFSET)', block):
            raise ValueError(f'pass {index}: WHEN/OFFSET are not supported')
        output = save.group(1) if save else 'MAIN'
        macros = re.findall(r'(?m)^#define (go_\d+)\(x_off, y_off\) (.+)$', block)
        body = re.search(r'vec4 hook\(\)\s*\{(.*)\}\s*$', block, re.S)
        if not body:
            raise ValueError(f'pass {index}: hook() not found')
        code = body.group(1)
        lines = []
        for name, expr in macros:
            expr = re.sub(r'(\w+)_texOff\(vec2\(x_off, y_off\)\)', r'YKT(\1, x_off, y_off)', expr)
            expr = expr.replace(', 0.0))', ', float4(0.0)))')
            if '_tex' in expr or 'vec' in expr:
                raise ValueError(f'pass {index}: unexpected macro {expr}')
            lines.append(f'    #define {name}(x_off, y_off) {expr}')
        code = code.replace('mat4(', 'YKM4(')
        code = re.sub(r'\bvec([234])\b', r'float\1', code)
        code = re.sub(r'(\w+)_tex\(\1_pos\)', r'\1.read(gid)', code)
        code = re.sub(r'return ([^;]+);', r'ykOut.write(\1, gid); return;', code)
        if re.search(r'\w_(pos|pt|size|texOff|tex)\b|HOOKED|\btexture\(|\bvec[234]\b|\bmat[234]\b', code):
            raise ValueError(f'pass {index}: unsupported construct in the body')
        args = ',\n'.join(f'    texture2d<float, access::read> {b} [[texture({i})]]' for i, b in enumerate(binds))
        kernel = f'a4k_pass_{index}'
        src = (f'kernel void {kernel}(\n{args},\n'
               f'    texture2d<float, access::write> ykOut [[texture({len(binds)})]],\n'
               f'    uint2 gid [[thread_position_in_grid]]) {{\n'
               f'    if (gid.x >= ykOut.get_width() || gid.y >= ykOut.get_height()) {{ return; }}\n'
               f'    int2 p = int2(gid);\n'
               f'    int2 lim = int2(int(ykOut.get_width()) - 1, int(ykOut.get_height()) - 1);\n'
               + '\n'.join(lines) + '\n' + code.strip('\n') + '\n'
               + '\n'.join(f'    #undef {name}' for name, _ in macros) + '\n}\n')
        passes.append({'kernel': kernel, 'inputs': binds, 'output': output, 'source': src})
    if not passes or passes[-1]['output'] != 'MAIN':
        raise ValueError('the last pass must write MAIN')
    return passes


PRELUDE = '''#define YKT(tex, dx, dy) tex.read(uint2(clamp(p + int2(int(dx), int(dy)), int2(0), lim)))
static inline float4x4 YKM4(float a0, float a1, float a2, float a3, float a4, float a5, float a6, float a7,
                            float a8, float a9, float a10, float a11, float a12, float a13, float a14, float a15) {
    return float4x4(float4(a0, a1, a2, a3), float4(a4, a5, a6, a7), float4(a8, a9, a10, a11), float4(a12, a13, a14, a15));
}
'''


# ---------- Anime4K passes from the downloaded shader (optional) ----------
glsl_path = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else None
passes, license_lines = [], []
if glsl_path and glsl_path.exists():
    text = glsl_path.read_text(encoding="utf-8")
    try:
        passes = convert(text)
        license_lines = [l for l in text.split("\n")[:30] if l.startswith("//") and not l.startswith("//!")]
        print(f"Anime4K: {len(passes)} passes converted to Metal")
    except ValueError as error:
        print(f"Anime4K: shader not converted ({error}); line restoration will be unavailable")
        passes = []
else:
    print("Anime4K: shader file missing; line restoration will be unavailable")

METAL = r"""#include <metal_stdlib>
using namespace metal;

struct YKVOut {
    float4 pos [[position]];
    float2 uv;
};

vertex YKVOut ykFullscreen(uint vid [[vertex_id]]) {
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    YKVOut o;
    o.pos = float4(p * 2.0 - 1.0, 0.0, 1.0);
    o.uv = float2(p.x, 1.0 - p.y);
    return o;
}

fragment float4 ykPresent(YKVOut in [[stage_in]], texture2d<float> t [[texture(0)]]) {
    constexpr sampler s(coord::normalized, filter::nearest, address::clamp_to_edge);
    return float4(t.sample(s, in.uv).rgb, 1.0);
}

kernel void ykDeband(texture2d<float, access::read> src [[texture(0)]],
                     texture2d<float, access::write> dst [[texture(1)]],
                     constant float &strength [[buffer(0)]],
                     uint2 gid [[thread_position_in_grid]]) {
    if (gid.x >= dst.get_width() || gid.y >= dst.get_height()) { return; }
    int2 p = int2(gid);
    int2 lim = int2(int(dst.get_width()) - 1, int(dst.get_height()) - 1);
    float4 c = src.read(gid);
    float h = fract(sin(dot(float2(gid), float2(12.9898, 78.233))) * 43758.5453);
    float angle = h * 6.2831853;
    float radius = 3.0 + h * 13.0;
    int2 o1 = int2(round(float2(cos(angle), sin(angle)) * radius));
    int2 o2 = int2(-o1.y, o1.x);
    float3 a = src.read(uint2(clamp(p + o1, int2(0), lim))).rgb;
    float3 b = src.read(uint2(clamp(p - o1, int2(0), lim))).rgb;
    float3 d = src.read(uint2(clamp(p + o2, int2(0), lim))).rgb;
    float3 e = src.read(uint2(clamp(p - o2, int2(0), lim))).rgb;
    float3 avg = (a + b + d + e) * 0.25;
    float threshold = (1.5 + 2.5 * strength) / 255.0;
    float3 diff = max(max(abs(a - c.rgb), abs(b - c.rgb)), max(abs(d - c.rgb), abs(e - c.rgb)));
    bool flatArea = all(diff < float3(threshold));
    float grain = (fract(h * 91.3458) - 0.5) / 255.0;
    float3 outc = flatArea ? (avg + grain) : c.rgb;
    dst.write(float4(outc, 1.0), gid);
}

kernel void ykSharpen(texture2d<float, access::read> src [[texture(0)]],
                      texture2d<float, access::write> dst [[texture(1)]],
                      constant float &sharpness [[buffer(0)]],
                      uint2 gid [[thread_position_in_grid]]) {
    if (gid.x >= dst.get_width() || gid.y >= dst.get_height()) { return; }
    int2 p = int2(gid);
    int2 lim = int2(int(dst.get_width()) - 1, int(dst.get_height()) - 1);
    #define YKS(dx, dy) src.read(uint2(clamp(p + int2(dx, dy), int2(0), lim))).rgb
    float3 a = YKS(-1, -1); float3 b = YKS(0, -1); float3 c = YKS(1, -1);
    float3 d = YKS(-1, 0);  float3 e = YKS(0, 0);  float3 f = YKS(1, 0);
    float3 g = YKS(-1, 1);  float3 h = YKS(0, 1);  float3 i = YKS(1, 1);
    #undef YKS
    float3 mn = min(min(min(d, e), min(f, b)), h);
    mn += min(mn, min(min(a, c), min(g, i)));
    float3 mx = max(max(max(d, e), max(f, b)), h);
    mx += max(mx, max(max(a, c), max(g, i)));
    float3 amp = sqrt(saturate(min(mn, 2.0 - mx) / max(mx, float3(0.00001))));
    float peak = -1.0 / mix(8.0, 5.0, saturate(sharpness));
    float3 w = amp * peak;
    float3 outc = saturate((b * w + d * w + f * w + h * w + e) / (1.0 + 4.0 * w));
    dst.write(float4(outc, 1.0), gid);
}

""" + (PRELUDE + "\n" + "\n".join(p["source"] for p in passes) if passes else "")

pass_list = ",\n".join(
    '        Pass(kernel: "%s", inputs: [%s], output: "%s")' % (p["kernel"], ", ".join('"%s"' % i for i in p["inputs"]), p["output"])
    for p in passes)
assert '"""#' not in METAL

SWIFT = """//
//  YKVideoFilters.swift
//  Yomikiri: picture enhancement for anime on the decoded frame.
""" + "\n".join("//  " + l.lstrip("/ ").rstrip() for l in license_lines) + """
//
import Foundation
import Metal
import QuartzCore

public final class YKVideoFilters {
    public static let shared = YKVideoFilters()
    /// A short text for the settings screen.
    public static var status = "выключено"

    struct Pass {
        let kernel: String
        let inputs: [String]
        let output: String
    }

    static let passes: [Pass] = [
""" + pass_list + """
    ]

    public static var anime4KAvailable: Bool { !passes.isEmpty }

    /// Any filter switched on in the player settings.
    public static var isEnabled: Bool {
        let d = UserDefaults.standard
        return d.bool(forKey: "ykDeband") || (d.bool(forKey: "ykAnime4K") && anime4KAvailable) || d.double(forKey: "ykSharpen") > 0.001
    }

    static let source = #\"\"\"
""" + METAL + """
\"\"\"#

    private let device = MetalRender.device
    private var library: MTLLibrary?
    private var compiling = false
    private var failure: String?
    private var compute = [String: MTLComputePipelineState]()
    private var presentStates = [UInt: MTLRenderPipelineState]()
    private var textures = [String: MTLTexture]()
    private var frames = 0
    private var gpuMs = 0.0

    /// True when the filters can draw this frame. The first call starts compiling the shaders in the background.
    var isReady: Bool {
        guard Self.isEnabled, failure == nil else { return false }
        if library != nil { return true }
        if !compiling {
            compiling = true
            Self.status = "подготовка шейдеров…"
            device.makeLibrary(source: Self.source, options: nil) { [weak self] library, error in
                DispatchQueue.main.async {
                    guard let self else { return }
                    self.compiling = false
                    if let library {
                        self.library = library
                        Self.status = "готово"
                    } else {
                        let text = error?.localizedDescription ?? "неизвестная ошибка"
                        self.failure = text
                        Self.status = "ошибка шейдеров: " + String(text.prefix(300))
                    }
                }
            }
        }
        return false
    }

    func texture(_ name: String, width: Int, height: Int, pixelFormat: MTLPixelFormat, render: Bool) -> MTLTexture? {
        if let existing = textures[name], existing.width == width, existing.height == height,
           existing.pixelFormat == pixelFormat {
            return existing
        }
        let descriptor = MTLTextureDescriptor.texture2DDescriptor(pixelFormat: pixelFormat, width: width, height: height,
                                                                  mipmapped: false)
        descriptor.usage = render ? [.renderTarget, .shaderRead] : [.shaderRead, .shaderWrite]
        descriptor.storageMode = .private
        let created = device.makeTexture(descriptor: descriptor)
        textures[name] = created
        return created
    }

    private func pipeline(_ name: String) -> MTLComputePipelineState? {
        if let state = compute[name] { return state }
        guard let library, let function = library.makeFunction(name: name) else {
            failure = "нет функции " + name
            Self.status = "ошибка шейдеров: нет функции " + name
            return nil
        }
        do {
            let state = try device.makeComputePipelineState(function: function)
            compute[name] = state
            return state
        } catch {
            failure = error.localizedDescription
            Self.status = "ошибка шейдера " + name + ": " + String(error.localizedDescription.prefix(300))
            return nil
        }
    }

    private func run(_ name: String, _ inputs: [MTLTexture], _ output: MTLTexture, _ commandBuffer: MTLCommandBuffer,
                     value: Float?) -> Bool {
        guard let state = pipeline(name), let encoder = commandBuffer.makeComputeCommandEncoder() else { return false }
        encoder.setComputePipelineState(state)
        for (index, input) in inputs.enumerated() {
            encoder.setTexture(input, index: index)
        }
        encoder.setTexture(output, index: inputs.count)
        if var number = value {
            encoder.setBytes(&number, length: MemoryLayout<Float>.size, index: 0)
        }
        encoder.dispatchThreads(MTLSize(width: output.width, height: output.height, depth: 1),
                                threadsPerThreadgroup: MTLSize(width: 16, height: 16, depth: 1))
        encoder.endEncoding()
        return true
    }

    /// The filters switched on, in order: deband, Anime4K, sharpening. nil when something could not be encoded.
    func encode(commandBuffer: MTLCommandBuffer, source: MTLTexture) -> MTLTexture? {
        let d = UserDefaults.standard
        let width = source.width
        let height = source.height
        var current = source
        if d.bool(forKey: "ykDeband") {
            guard let out = texture("deband", width: width, height: height, pixelFormat: .rgba16Float, render: false),
                  run("ykDeband", [current], out, commandBuffer, value: 0.5) else { return nil }
            current = out
        }
        if d.bool(forKey: "ykAnime4K"), !Self.passes.isEmpty {
            var named = ["MAIN": current]
            for pass in Self.passes {
                let inputs = pass.inputs.compactMap { named[$0] }
                guard inputs.count == pass.inputs.count,
                      let out = texture("a4k." + pass.output, width: width, height: height, pixelFormat: .rgba16Float,
                                        render: false),
                      run(pass.kernel, inputs, out, commandBuffer, value: nil) else { return nil }
                named[pass.output] = out
            }
            guard let main = named["MAIN"] else { return nil }
            current = main
        }
        let sharpen = d.double(forKey: "ykSharpen")
        if sharpen > 0.001 {
            guard let out = texture("sharpen", width: width, height: height, pixelFormat: .rgba16Float, render: false),
                  run("ykSharpen", [current], out, commandBuffer, value: Float(sharpen)) else { return nil }
            current = out
        }
        return current
    }

    /// The filtered picture onto the screen (the drawable has the size of the video).
    func present(_ texture: MTLTexture, to drawable: CAMetalDrawable, commandBuffer: MTLCommandBuffer) -> Bool {
        let format = drawable.texture.pixelFormat
        if presentStates[format.rawValue] == nil {
            guard let library, let vertex = library.makeFunction(name: "ykFullscreen"),
                  let fragment = library.makeFunction(name: "ykPresent") else { return false }
            let descriptor = MTLRenderPipelineDescriptor()
            descriptor.vertexFunction = vertex
            descriptor.fragmentFunction = fragment
            descriptor.colorAttachments[0].pixelFormat = format
            presentStates[format.rawValue] = try? device.makeRenderPipelineState(descriptor: descriptor)
        }
        guard let state = presentStates[format.rawValue] else { return false }
        let pass = MTLRenderPassDescriptor()
        pass.colorAttachments[0].texture = drawable.texture
        pass.colorAttachments[0].loadAction = .dontCare
        pass.colorAttachments[0].storeAction = .store
        guard let encoder = commandBuffer.makeRenderCommandEncoder(descriptor: pass) else { return false }
        encoder.setRenderPipelineState(state)
        encoder.setFragmentTexture(texture, index: 0)
        encoder.drawPrimitives(type: .triangle, vertexStart: 0, vertexCount: 3)
        encoder.endEncoding()
        return true
    }

    /// GPU time of the frame, shown in the settings (average of 30 frames).
    func finished(_ commandBuffer: MTLCommandBuffer, width: Int, height: Int) {
        gpuMs += max(0, commandBuffer.gpuEndTime - commandBuffer.gpuStartTime) * 1000
        frames += 1
        if frames >= 30 {
            Self.status = String(format: "работает: %.1f мс на кадр, %d×%d", gpuMs / Double(frames), width, height)
            frames = 0
            gpuMs = 0
        }
    }
}
"""
(ROOT / "MEPlayer/YKVideoFilters.swift").write_text(SWIFT, encoding="utf-8")

# ---------- MetalRender: filtered drawing ----------
rp = ROOT / "Metal/MetalRender.swift"
s = rp.read_text(encoding="utf-8")
s = once(s, """    func draw(pixelBuffer: PixelBufferProtocol, display: DisplayEnum = .plane, drawable: CAMetalDrawable) {
        let inputTextures = pixelBuffer.textures()
""", """    func draw(pixelBuffer: PixelBufferProtocol, display: DisplayEnum = .plane, drawable: CAMetalDrawable) {
        if display == .plane, YKVideoFilters.shared.isReady,
           drawFiltered(pixelBuffer: pixelBuffer, display: display, drawable: drawable) {
            return
        }
        let inputTextures = pixelBuffer.textures()
""", "draw head")
s = once(s, """    private func setFragmentBuffer(pixelBuffer: PixelBufferProtocol, encoder: MTLRenderCommandEncoder) {
""", """    /// The frame is converted to RGB in a texture of the drawable size, filtered, then drawn on the screen.
    @MainActor
    private func drawFiltered(pixelBuffer: PixelBufferProtocol, display: DisplayEnum, drawable: CAMetalDrawable) -> Bool {
        let filters = YKVideoFilters.shared
        let target = drawable.texture
        let inputTextures = pixelBuffer.textures()
        guard !inputTextures.isEmpty,
              let source = filters.texture("source", width: target.width, height: target.height,
                                           pixelFormat: target.pixelFormat, render: true),
              let commandBuffer = commandQueue?.makeCommandBuffer() else { return false }
        let pass = MTLRenderPassDescriptor()
        pass.colorAttachments[0].texture = source
        pass.colorAttachments[0].loadAction = .clear
        pass.colorAttachments[0].clearColor = MTLClearColor(red: 0, green: 0, blue: 0, alpha: 1)
        pass.colorAttachments[0].storeAction = .store
        guard let encoder = commandBuffer.makeRenderCommandEncoder(descriptor: pass) else { return false }
        let state = display.pipeline(planeCount: pixelBuffer.planeCount, bitDepth: pixelBuffer.bitDepth)
        encoder.setRenderPipelineState(state)
        encoder.setFragmentSamplerState(samplerState, index: 0)
        for (index, texture) in inputTextures.enumerated() {
            encoder.setFragmentTexture(texture, index: index)
        }
        setFragmentBuffer(pixelBuffer: pixelBuffer, encoder: encoder)
        display.set(encoder: encoder)
        encoder.endEncoding()
        guard let result = filters.encode(commandBuffer: commandBuffer, source: source),
              filters.present(result, to: drawable, commandBuffer: commandBuffer) else { return false }
        commandBuffer.present(drawable)
        commandBuffer.commit()
        commandBuffer.waitUntilCompleted()
        filters.finished(commandBuffer, width: target.width, height: target.height)
        return true
    }

    private func setFragmentBuffer(pixelBuffer: PixelBufferProtocol, encoder: MTLRenderCommandEncoder) {
""", "drawFiltered")
rp.write_text(s, encoding="utf-8")

# ---------- KSOptions: Metal output with filters, no drop up to the key frame right after a seek ----------
op = ROOT / "AVPlayer/KSOptions.swift"
s = op.read_text(encoding="utf-8")
s = once(s, "    open func isUseDisplayLayer() -> Bool {\n        display == .plane\n    }\n",
         "    open func isUseDisplayLayer() -> Bool {\n        // the system display layer cannot run shaders: with a picture filter on, the frame goes through Metal\n"
         "        display == .plane && !YKVideoFilters.isEnabled\n    }\n", "display layer")
s = once(s, "    static var isAccurateSeek = false\n",
         "    static var isAccurateSeek = false\n"
         "    /// Until this time (3 s after a seek) late video frames are dropped one by one, not up to the next key frame.\n"
         "    public static var ykSeekGraceUntil: CFTimeInterval = 0\n", "grace var")
for kind in ("dropGOPPacket", "seek", "flush"):
    s = once(s, f"                        return (diff, .{kind})\n",
             f"                        return (diff, CACurrentMediaTime() < KSOptions.ykSeekGraceUntil ? .dropNextFrame : .{kind})\n",
             "grace " + kind)
op.write_text(s, encoding="utf-8")

mp = ROOT / "MEPlayer/MEPlayerItem.swift"
s = mp.read_text(encoding="utf-8")
s = once(s, "    public func seek(time: TimeInterval, completion: @escaping ((Bool) -> Void)) {\n        if state == .reading || state == .paused {\n",
         "    public func seek(time: TimeInterval, completion: @escaping ((Bool) -> Void)) {\n"
         "        KSOptions.ykSeekGraceUntil = CACurrentMediaTime() + 3\n"
         "        if state == .reading || state == .paused {\n", "seek grace")
mp.write_text(s, encoding="utf-8")
print("KSPlayer v1.45: picture filters and seek grace applied")
