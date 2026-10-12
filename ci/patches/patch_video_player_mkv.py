# Moved out of build-ios-v141-player.yml, step "Patch video player (MKV subtitles + in-app player)" (GitHub limits workflow files to 500 KB).
import pathlib, re
root = pathlib.Path("src/safari")
report = []

# ---------- 1. MainView: add Video tab ----------
p = root / "iOS (App)/MainView.swift"
s = p.read_text()
enum_line = "        case help, dictionary, settings\n"
if "case help, dictionary, settings, video" in s:
    report.append("enum Tabs: case video already present")
elif s.count(enum_line) == 1:
    s = s.replace(enum_line, "        case help, dictionary, settings, video\n")
    report.append("enum Tabs: case video added")
else:
    report.append("WARNING: enum Tabs line not found; video tab NOT added")
if "case help, dictionary, settings, video" in s:
    anchor = "                .tag(Tabs.settings)\n        }\n        .preferredColorScheme(.dark)"
    if s.count(anchor) == 1:
        replacement = (
            "                .tag(Tabs.settings)\n"
            "            VideoTabView()\n"
            "                .tabItem {\n"
            '                    Label("Видео", systemImage: "play.rectangle.fill")\n'
            "                }\n"
            "                .tag(Tabs.video)\n"
            "        }\n"
            "        .preferredColorScheme(.dark)"
        )
        s = s.replace(anchor, replacement, 1)
        report.append("Video tab inserted in TabView")
    else:
        report.append("WARNING: TabView anchor not found; video tab not inserted")
p.write_text(s)

# ---------- 2. HelpView: append video player implementation ----------
p = root / "iOS (App)/HelpView.swift"
s = p.read_text()
VIDEO_CODE = r'''
// MARK: - Video player (in-app, MKV subtitles, word lookup)
import WebKit

/// Serves local media files (video/subtitles) to the web player at ykmedia://files/<name>.
final class YomikiriMediaSchemeHandler: NSObject, WKURLSchemeHandler {
    static func videosDirectory() -> URL? {
        guard let base = try? getSharedDirectory() else { return nil }
        let dir = base.appendingPathComponent("Videos", isDirectory: true)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir
    }
    static func mediaType(_ path: String) -> String {
        switch path.lowercased().split(separator: ".").last.map(String.init) ?? "" {
        case "mp4", "m4v": return "video/mp4"
        case "mov": return "video/quicktime"
        case "mkv": return "video/x-matroska"
        case "webm": return "video/webm"
        case "srt": return "text/srt; charset=utf-8"
        case "vtt": return "text/vtt; charset=utf-8"
        case "ass", "ssa": return "text/plain; charset=utf-8"
        default: return "application/octet-stream"
        }
    }
    func webView(_ webView: WKWebView, start task: WKURLSchemeTask) {
        guard let comps = URLComponents(url: task.request.url!, resolvingAgainstBaseURL: false),
              comps.host == "files",
              let dir = YomikiriMediaSchemeHandler.videosDirectory()
        else {
            task.didFailWithError(NSError(domain: "yomikiri.media", code: 1))
            return
        }
        let name = comps.percentEncodedPath.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
            .removingPercentEncoding ?? ""
        let file = dir.appendingPathComponent(name)
        guard name != "", FileManager.default.fileExists(atPath: file.path),
              let attrs = try? FileManager.default.attributesOfItem(atPath: file.path),
              let length = attrs[.size] as? UInt64
        else {
            task.didFailWithError(NSError(domain: "yomikiri.media", code: 2))
            return
        }
        var status = 200
        var lower: UInt64 = 0
        var upper = length > 0 ? length - 1 : 0
        if let range = task.request.allHTTPHeaderFields?["Range"],
           let eq = range.range(of: "="), range[..<eq.lowerBound].contains("bytes"),
           let dash = range.range(of: "-", range: eq.upperBound..<range.endIndex)
        {
            let lo = range[eq.upperBound..<dash.lowerBound].trimmingCharacters(in: .whitespaces)
            let hi = range[dash.upperBound...].trimmingCharacters(in: .whitespaces)
            if let loV = UInt64(lo), loV < length {
                lower = loV
                if let hiV = UInt64(hi), hiV >= loV, hiV < length { upper = hiV }
                status = 206
            }
        }
        guard let handle = try? FileHandle(forReadingFrom: file) else {
            task.didFailWithError(NSError(domain: "yomikiri.media", code: 3))
            return
        }
        defer { try? handle.close() }
        try? handle.seek(toOffset: lower)
        let size = Int(upper - lower + 1)
        let data = (try? handle.read(upToCount: size)) ?? Data()
        var headers: [String: String] = [
            "Content-Type": YomikiriMediaSchemeHandler.mediaType(name),
            "Accept-Ranges": "bytes",
            "Access-Control-Allow-Origin": "*",
        ]
        if status == 206 {
            headers["Content-Range"] = "bytes \(lower)-\(upper)/\(length)"
            headers["Content-Length"] = String(data.count)
        } else {
            headers["Content-Length"] = String(length)
        }
        let response = HTTPURLResponse(
            url: task.request.url!, statusCode: status, httpVersion: "HTTP/1.1", headerFields: headers)
        task.didReceive(response!)
        task.didReceive(data)
        task.didFinish()
    }
    func webView(_ webView: WKWebView, stop task: WKURLSchemeTask) {}
}

enum YomikiriVideoLibrary {
    static func fileNames() -> [String] {
        guard let dir = YomikiriMediaSchemeHandler.videosDirectory() else { return [] }
        let items = (try? FileManager.default.contentsOfDirectory(
            at: dir, includingPropertiesForKeys: [.fileSizeKey])) ?? []
        return items.map { $0.lastPathComponent }.sorted()
    }
}

struct VideoTabView: View {
    var body: some View {
        PlayerWebView()
            .ignoresSafeArea(edges: .bottom)
    }
}

struct PlayerWebView: UIViewRepresentable {
    func makeCoordinator() -> Coordinator { Coordinator() }

    func makeUIView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        config.setURLSchemeHandler(YomikiriMediaSchemeHandler(), forURLScheme: "ykmedia")
        let controller = WKUserContentController()
        controller.add(context.coordinator, name: "player")
        config.userContentController = controller
        config.allowsInlineMediaPlayback = true
        config.mediaTypesRequiringUserActionForPlayback = []
        let wv = WKWebView(frame: .zero, configuration: config)
        context.coordinator.webView = wv
        wv.isOpaque = false
        wv.backgroundColor = .black
        wv.scrollView.backgroundColor = .black
        wv.loadHTMLString(PlayerHTML.makePage(), baseURL: URL(string: "https://yomikiri.local/"))
        return wv
    }
    func updateUIView(_ wv: WKWebView, context: Context) {}

    final class Coordinator: NSObject, WKScriptMessageHandler {
        weak var webView: WKWebView?
        func userContentController(
            _ userContentController: WKUserContentController,
            didReceive message: WKScriptMessage
        ) {
            guard message.name == "player", let text = message.body as? String else { return }
            if text == "__refresh__" {
                webView?.loadHTMLString(PlayerHTML.makePage(), baseURL: URL(string: "https://yomikiri.local/"))
                return
            }
            UIPasteboard.general.string = text
        }
    }
}

enum PlayerHTML {
    static func makePage() -> String {
        let files = YomikiriVideoLibrary.fileNames()
        let filesJSON = (try? String(
            data: JSONSerialization.data(withJSONObject: files), encoding: .utf8)) ?? "[]"
        return rawPage.replacingOccurrences(of: "__FILES__", with: filesJSON)
    }

    private static let rawPage = #"""
<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
<title>Видео</title>
<style>
:root { color-scheme: dark; }
* { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
body { margin: 0; background: #000; color: #e8e8e8;
       font: 16px -apple-system, sans-serif; }
header { display: flex; align-items: center; gap: 8px; padding: 10px 12px;
         background: #111; border-bottom: 1px solid #2a2a2c; }
header select, header button {
  background: #2c2c2e; color: #e8e8e8; border: 1px solid #3a3a3c;
  border-radius: 10px; padding: 8px 10px; font-size: 15px; }
#stage { position: relative; background: #000; }
video { width: 100%; max-height: 60vh; background: #000; }
#subOverlay { position: absolute; left: 6%; right: 6%; bottom: 8%;
  text-align: center; font-size: 20px; line-height: 1.35;
  text-shadow: 0 0 4px #000, 0 2px 4px #000; pointer-events: auto; }
#subOverlay span.w { cursor: pointer; }
#subOverlay span.w:active { color: #ff9f0a; }
#bar { display: flex; gap: 8px; padding: 10px 12px; background: #111;
       border-top: 1px solid #2a2a2c; flex-wrap: wrap; }
#bar button { flex: 1 1 auto; background: #2c2c2e; color: #e8e8e8;
  border: 1px solid #3a3a3c; border-radius: 10px; padding: 10px; font-size: 15px; }
#status { padding: 10px 12px; color: #a0a0a5; font-size: 13px; white-space: pre-wrap; }
#files { padding: 12px; }
.file { padding: 12px; border-radius: 12px; background: #1c1c1e;
        margin-bottom: 8px; display: flex; justify-content: space-between; gap: 8px; }
.file .name { word-break: break-all; }
.file .kind { color: #8e8e93; font-size: 13px; white-space: nowrap; }
.hint { padding: 12px; color: #a0a0a5; font-size: 14px; line-height: 1.5; }
</style></head><body>
<header>
  <button id="back">← Файлы</button>
  <select id="trackSel" style="flex:1"></select>
  <button id="refresh">⟳</button>
  <button id="speed">1.0×</button>
</header>
<div id="stage">
  <video id="vid" playsinline controls></video>
  <div id="subOverlay"></div>
</div>
<div id="bar">
  <button id="prevSub">−5с</button>
  <button id="nextSub">+5с</button>
  <button id="copyCmd">ffmpeg-команда</button>
</div>
<div id="status"></div>
<div id="files"></div>
<script>
var FILES = __FILES__;
var $ = function (id) { return document.getElementById(id); };
var enc = function (s) { return encodeURIComponent(s).replace(/%20/g, "+"); };
function mediaUrl(name) { return "ykmedia://files/" + enc(name); }
function status(t) { $("status").textContent = t; }
function post(text) {
  try { window.webkit.messageHandlers.player.postMessage(text); } catch (e) {}
}
function parseSRT(text) {
  var cues = [];
  var ts = /(\d+):(\d+):(\d+)[,.](\d+)/;
  function toSec(m) { return +m[1]*3600 + +m[2]*60 + +m[3] + +m[4]/1000; }
  var blocks = text.replace(/\r/g, "").split(/\n\n+/);
  for (var bi = 0; bi < blocks.length; bi++) {
    var lines = blocks[bi].split("\n");
    var i = -1;
    for (var li = 0; li < lines.length; li++) { if (lines[li].indexOf("-->") >= 0) { i = li; break; } }
    if (i < 0) continue;
    var mm = lines[i].match(ts);
    var rest = lines[i].split("-->")[1];
    var m2 = rest ? rest.match(ts) : null;
    if (!mm || !m2) continue;
    cues.push({ a: toSec(mm), b: toSec(m2), text: lines.slice(i + 1).join("\n").replace(/<[^>]+>/g, "") });
  }
  return cues;
}
function parseASS(text) {
  var cues = [];
  var ts = /(\d+):(\d{2}):(\d{2})[.,](\d{2})/;
  function toSec(m) { return +m[1]*3600 + +m[2]*60 + +m[3] + +m[4]/100; }
  var lines = text.split("\n");
  for (var i = 0; i < lines.length; i++) {
    var line = lines[i];
    if (line.indexOf("Dialogue:") !== 0) continue;
    var parts = line.split(",");
    if (parts.length < 10) continue;
    var a = parts[1].match(ts), b = parts[2].match(ts);
    if (!a || !b) continue;
    var t = parts.slice(9).join(",")
      .replace(/\{[^}]*\}/g, "").replace(/\\N/g, "\n").replace(/\\h/g, " ");
    cues.push({ a: toSec(a), b: toSec(b), text: t });
  }
  return cues;
}
function parseSubs(name, text) {
  var ext = name.split(".").pop().toLowerCase();
  if (ext === "ass" || ext === "ssa") return parseASS(text);
  if (ext === "vtt") return parseSRT(text.replace(/^WEBVTT[^\n]*\n/, "").replace(/\./g, ","));
  return parseSRT(text);
}
function readBytes(name, start, size) {
  return fetch(mediaUrl(name), { headers: { Range: "bytes=" + start + "-" + (start + size - 1) } })
    .then(function (r) { return r.arrayBuffer(); })
    .then(function (buf) { return new Uint8Array(buf); });
}
function fileSize(name) {
  return fetch(mediaUrl(name), { method: "HEAD" }).then(function (r) {
    var cr = r.headers.get("Content-Range") || r.headers.get("Content-Length") || "0";
    return parseInt(cr.split("/").pop(), 10) || 0;
  });
}
function extractMkvSubs(name, onProgress) {
  return fileSize(name).then(function (total) {
    status("Чтение MKV: 0%");
    var tracks = {};
    var subNums = {};
    var cues = [];
    var WIN = 4 * 1024 * 1024;
    function readId(buf, o) {
      if (o >= buf.length) return null;
      var b0 = buf[o];
      if (!b0) return null;
      var sizeLen = 8 - (31 - Math.clz32(b0));
      if (o + sizeLen > buf.length) return null;
      var v = b0;
      for (var i = 1; i < sizeLen; i++) v = v * 256 + buf[o + i];
      return { id: v >>> 0, len: sizeLen };
    }
    function readSize(buf, o) {
      if (o >= buf.length) return null;
      var b0 = buf[o];
      if (!b0) return null;
      var sizeLen = 8 - (31 - Math.clz32(b0));
      if (o + sizeLen > buf.length) return null;
      var v = b0 & ((1 << (8 - sizeLen)) - 1);
      for (var i = 1; i < sizeLen; i++) v = v * 256 + buf[o + i];
      return { v: v, len: sizeLen };
    }
    var ID_TRACKS = 0x1654AE6B, ID_TRACKENTRY = 0xAE, ID_TRACKNUMBER = 0xD7,
        ID_TRACKTYPE = 0x83, ID_TRACKLANG = 0x22B59C, ID_CLUSTER = 0x1F43B675,
        ID_SIMPLEBLOCK = 0xA3, ID_BLOCKGROUP = 0xA0, ID_BLOCK = 0xA1, ID_TIMECODE = 0xE7;
    return readBytes(name, 0, Math.min(WIN, total)).then(function (head) {
      var tw = head;
      var find = function (from, id) {
        var q = from;
        while (q < tw.length - 8) {
          if (tw[q] === ((id >>> 24) & 255) && tw[q+1] === ((id >>> 16) & 255)
              && tw[q+2] === ((id >>> 8) & 255) && tw[q+3] === (id & 255)) return q;
          q++;
        }
        return -1;
      };
      var t0 = find(0, ID_TRACKS);
      if (t0 >= 0) {
        var q = t0 + 4;
        var tsz = readSize(tw, q); q += tsz.len;
        var tend = q + tsz.v;
        while (q < tend && q < tw.length - 4) {
          var eid = readId(tw, q); if (!eid) break; q += eid.len;
          var esz = readSize(tw, q); if (!esz) break; q += esz.len;
          if (eid.id === ID_TRACKENTRY) {
            var num = 0, type = 0, lang = "";
            var r = q, entryEnd = q + esz.v;
            while (r < entryEnd && r < tw.length - 4) {
              var fid = readId(tw, r); if (!fid) break; r += fid.len;
              var fsz = readSize(tw, r); if (!fsz) break; r += fsz.len;
              if (fid.id === ID_TRACKNUMBER && fsz.v <= 4) {
                for (var i2 = 0; i2 < fsz.v; i2++) num = num * 256 + tw[r + i2];
              } else if (fid.id === ID_TRACKTYPE && fsz.v === 1) {
                type = tw[r];
              } else if (fid.id === ID_TRACKLANG) {
                lang = new TextDecoder().decode(tw.slice(r, r + fsz.v));
              }
              r += fsz.v;
            }
            if (type === 0x11 && num) { tracks[num] = lang || "und"; subNums[num] = true; }
          }
          q += esz.v;
        }
      }
      if (!Object.keys(subNums).length) throw new Error("в MKV нет текстовых субтитров");
      var pos = 0;
      function step() {
        if (pos >= total) return Promise.resolve();
        if (onProgress) onProgress(pos / total);
        return readBytes(name, pos, Math.min(WIN, total - pos)).then(function (win) {
          var o = 0;
          while (o < win.length - 4) {
            var id = readId(win, o);
            if (!id) { o += 4; continue; }
            var sz = readSize(win, o + id.len);
            if (!sz) { o += id.len + 1; continue; }
            var headLen = id.len + sz.len;
            if (id.id === ID_CLUSTER) {
              var p = o + headLen;
              var clusterEnd = o + headLen + sz.v;
              var baseTime = 0;
              while (p < clusterEnd && p < win.length - 4) {
                var eid = readId(win, p); if (!eid) break;
                var esz = readSize(win, p + eid.len); if (!esz) break;
                var eHead = eid.len + esz.len;
                if (eid.id === ID_TIMECODE) {
                  var v = 0;
                  for (var i3 = 0; i3 < esz.v && i3 < 8; i3++) v = v * 256 + win[p + eid.len + esz.len + i3];
                  baseTime = v;
                } else if (eid.id === ID_SIMPLEBLOCK || eid.id === ID_BLOCKGROUP || eid.id === ID_BLOCK) {
                  var bo = p + eHead;
                  var tn = readSize(win, bo);
                  if (tn) {
                    var q2 = bo + tn.len;
                    var trackNum = tn.v;
                    if (subNums[trackNum]) {
                      var relTime = (win[q2] << 8) | win[q2 + 1];
                      var dataOff = q2 + 3;
                      var dataLen = esz.v - (dataOff - bo);
                      if (dataLen > 0 && dataOff + dataLen <= win.length) {
                        var text = new TextDecoder().decode(win.slice(dataOff, dataOff + dataLen));
                        var t = (baseTime + relTime) / 1000;
                        cues.push({ a: t, b: t + 5, text: text, track: trackNum });
                      }
                    }
                  }
                }
                p += eHead + esz.v;
              }
              o = clusterEnd;
            } else {
              o += headLen + sz.v;
            }
          }
          pos += win.length;
          return step();
        });
      }
      return step().then(function () {
        cues.sort(function (a, b) { return a.a - b.a; });
        for (var i = 0; i < cues.length - 1; i++) {
          if (cues[i].track === cues[i + 1].track && cues[i + 1].a > cues[i].a) {
            cues[i].b = Math.min(cues[i + 1].a, cues[i].a + 12);
          }
        }
        return { tracks: tracks, cues: cues };
      });
    });
  });
}
var cues = [];
var vid = $("vid"), overlay = $("subOverlay");
function listFiles() {
  var box = $("files");
  box.innerHTML = "";
  $("stage").style.display = "none";
  $("bar").style.display = "none";
  $("trackSel").innerHTML = "";
  cues = [];
  if (!FILES.length) {
    box.innerHTML = '<div class="hint">Нет файлов. Добавьте видео или субтитры через приложение «Файлы»: удерживайте файл → «Поделиться» → Yomikiri.<br><br>MKV поддерживается в части субтитров: видео из MKV сам iOS не воспроизводит (это ограничение системы). Сделайте ремукс в MP4 (кнопка «ffmpeg-команда») и импортируйте оба файла с одинаковым именем — субтитры подключатся автоматически.</div>';
    return;
  }
  for (var i = 0; i < FILES.length; i++) {
    (function (name) {
      var ext = name.split(".").pop().toLowerCase();
      var isSub = ["srt", "vtt", "ass", "ssa"].indexOf(ext) >= 0;
      var isVid = ["mp4", "m4v", "mov"].indexOf(ext) >= 0;
      var isMkv = ext === "mkv";
      var div = document.createElement("div");
      div.className = "file";
      div.innerHTML = '<div class="name">' + name + '</div><div class="kind">'
        + (isVid ? "видео" : isSub ? "субтитры" : isMkv ? "MKV" : "файл") + "</div>";
      div.onclick = function () { openItem(name); };
      box.appendChild(div);
    })(FILES[i]);
  }
}
function renderTrackSelect(opts) {
  var sel = $("trackSel");
  sel.innerHTML = "";
  for (var i = 0; i < opts.length; i++) {
    var op = document.createElement("option");
    op.value = i;
    op.textContent = opts[i].name + " (" + opts[i].cues.length + ")";
    sel.appendChild(op);
  }
  if (opts.length) cues = opts[0].cues;
  sel.onchange = function () { cues = opts[+sel.value].cues; };
}
function openItem(name) {
  var ext = name.split(".").pop().toLowerCase();
  status("");
  if (["mp4", "m4v", "mov"].indexOf(ext) >= 0) {
    vid.src = mediaUrl(name);
    $("stage").style.display = "";
    $("bar").style.display = "";
    $("files").innerHTML = "";
    autoSubsFor(name);
  } else if (["srt", "vtt", "ass", "ssa"].indexOf(ext) >= 0) {
    fetch(mediaUrl(name)).then(function (r) { return r.text(); }).then(function (text) {
      cues = parseSubs(name, text);
      renderTrackSelect([{ name: name, cues: cues }]);
      status("Субтитры загружены: " + cues.length + " строк");
    });
  } else if (ext === "mkv") {
    status("Чтение субтитров из MKV…");
    extractMkvSubs(name, function (p) { status("Чтение MKV: " + Math.round(p * 100) + "%"); })
      .then(function (res) {
        var byTrack = {};
        for (var i = 0; i < res.cues.length; i++) {
          var c = res.cues[i];
          if (!byTrack[c.track]) byTrack[c.track] = [];
          byTrack[c.track].push(c);
        }
        var opts = [];
        for (var n in byTrack) {
          opts.push({ name: "Дорожка " + n + " (" + (res.tracks[n] || "?") + ")", cues: byTrack[n] });
        }
        renderTrackSelect(opts);
        status("Извлечено дорожек: " + opts.length + ", строк: " + res.cues.length +
          "\nВидео из MKV сам iOS не играет — нужен ремукс в MP4 (кнопка «ffmpeg-команда»). Если рядом лежит такой же .mp4, субтитры подключатся к нему.");
        var mp4 = name.replace(/\.mkv$/i, ".mp4");
        fetch(mediaUrl(mp4), { method: "HEAD" }).then(function (r) {
          if (r.ok) { vid.src = mediaUrl(mp4); $("stage").style.display = ""; $("bar").style.display = ""; }
        }).catch(function () {});
      })
      .catch(function (e) { status("MKV: " + e.message); });
  }
}
function autoSubsFor(video) {
  var base = video.replace(/\.[^.]+$/, "");
  var exts = ["srt", "vtt", "ass"];
  for (var i = 0; i < exts.length; i++) {
    (function (ext) {
      fetch(mediaUrl(base + "." + ext), { method: "HEAD" }).then(function (r) {
        if (r.ok) {
          fetch(mediaUrl(base + "." + ext)).then(function (r2) { return r2.text(); }).then(function (text) {
            cues = parseSubs(base + "." + ext, text);
            renderTrackSelect([{ name: base + "." + ext, cues: cues }]);
          });
        }
      }).catch(function () {});
    })(exts[i]);
  }
}
var seg = ("Segmenter" in Intl) ? new Intl.Segmenter("ja", { granularity: "word" }) : null;
function showCue(t) {
  var c = null;
  for (var i = 0; i < cues.length; i++) {
    if (t >= cues[i].a && t <= cues[i].b) { c = cues[i]; break; }
  }
  overlay.innerHTML = "";
  if (!c) return;
  var lines = c.text.split("\n");
  for (var li = 0; li < lines.length; li++) {
    var div = document.createElement("div");
    var line = lines[li];
    if (seg && /[\u3040-\u30ff\u4e00-\u9fff]/.test(line)) {
      var parts = seg.segment(line);
      for (const s of parts) {
        var sp = document.createElement("span");
        sp.textContent = s.segment;
        if (s.isWordLike && /[\u3040-\u30ff\u4e00-\u9fff]/.test(s.segment)) {
          (function (word) {
            sp.className = "w";
            sp.onclick = function () { lookupWord(word); };
          })(s.segment);
        }
        div.appendChild(sp);
      }
    } else {
      div.textContent = line;
    }
    overlay.appendChild(div);
  }
}
function lookupWord(w) {
  post(w);
  status("Слово «" + w + "» скопировано — вставьте его в поиск на вкладке «Словарь».");
}
vid.addEventListener("timeupdate", function () { showCue(vid.currentTime); });
$("back").onclick = listFiles;
$("prevSub").onclick = function () { vid.currentTime = Math.max(0, vid.currentTime - 5); };
$("nextSub").onclick = function () { vid.currentTime += 5; };
var speeds = [1, 1.25, 1.5, 0.75], spIdx = 0;
$("speed").onclick = function () {
  spIdx = (spIdx + 1) % speeds.length;
  vid.playbackRate = speeds[spIdx];
  $("speed").textContent = speeds[spIdx] + "×";
};
$("refresh").onclick = function () { post("__refresh__"); };
$("copyCmd").onclick = function () {
  post("ffmpeg -i input.mkv -map 0:v -map 0:a -c copy -movflags +faststart output.mp4");
  status("Команда скопирована. Вставьте её в терминал на компьютере (нужен установленный ffmpeg).");
};
listFiles();
</script></body></html>
"""#
}
'''
s = s.rstrip("\n") + "\n" + VIDEO_CODE
p.write_text(s)
report.append("HelpView: video player code appended")
print("\n".join(report))
