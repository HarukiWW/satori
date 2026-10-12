# v1.47 (settings): native settings screen in the iOS 26 style (inset grouped form, like statistics and video).
# Appearance, highlighting, JLPT and Anki options are native and write the same shared config the Safari extension
# reads. The Anki template editor keeps its page; the Anki deck import (needs the web zstd/SQLite reader) and
# "about" open as pages inside the settings.
import json, pathlib, re

src = pathlib.Path("src")


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


# the frequency dictionaries and the config version, as the web settings know them (generated earlier in the build)
lst = (src / "main/src/lib/freqDictList.ts").read_text(encoding="utf-8")
dicts = json.loads(re.search(r"=\s*(\[.*\])\s*;", lst, re.S).group(1))
config_ts = (src / "main/src/lib/config.ts").read_text(encoding="utf-8")
version = int(re.search(r"export const CONFIG_VERSION = (\d+)", config_ts).group(1))


def swift_str(value):
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


dict_items = ",\n".join("        (id: %s, label: %s)" % (swift_str(d["id"]), swift_str(d["label"])) for d in dicts)
print(f"settings: {len(dicts)} frequency dictionaries, config version {version}")

SWIFT = '''

// MARK: - Native settings (iOS 26 look)

/// The shared config (the same JSON the Safari extension and the web pages read).
@MainActor
final class NativeConfig: ObservableObject {
    static let version = ''' + str(version) + '''
    static let freqDicts: [(id: String, label: String)] = [
''' + dict_items + '''
    ]

    @Published private(set) var values: [String: Any] = [:]

    init() {
        reload()
    }

    func reload() {
        guard let json = try? Storage.config.get(), let data = json.data(using: .utf8),
              let object = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] else {
            values = [:]
            return
        }
        values = object
    }

    func set(_ key: String, _ value: Any) {
        reload()
        var updated = values
        updated[key] = value
        if updated["config_version"] == nil {
            updated["config_version"] = NativeConfig.version
        }
        guard let data = try? JSONSerialization.data(withJSONObject: updated),
              let json = String(data: data, encoding: .utf8) else { return }
        do {
            try Storage.config.set(json)
            values = updated
            triggerConfigUpdateHook(messageHandler: nil, configJSON: json)
        } catch {}
    }

    func bool(_ key: String, _ fallback: Bool) -> Binding<Bool> {
        Binding(get: { (self.values[key] as? Bool) ?? fallback }, set: { self.set(key, $0) })
    }

    func int(_ key: String, _ fallback: Int) -> Binding<Int> {
        Binding(get: { (self.values[key] as? NSNumber)?.intValue ?? fallback }, set: { self.set(key, $0) })
    }

    func string(_ key: String, _ fallback: String) -> Binding<String> {
        Binding(get: { (self.values[key] as? String) ?? fallback }, set: { self.set(key, $0) })
    }

    /// The old settings stored "main" / "wn": they mean the general and the web novel dictionary.
    var dictionary: Binding<String> {
        Binding(get: {
            let value = (self.values["highlight.dict"] as? String) ?? "main"
            let list = NativeConfig.freqDicts
            if list.contains(where: { $0.id == value }) { return value }
            let web = list.first { $0.label.range(of: "WN", options: .caseInsensitive) != nil
                || $0.label.range(of: "webnovel", options: .caseInsensitive) != nil }
            let general = list.first { $0.label.range(of: "WN", options: .caseInsensitive) == nil }
            return ((value == "wn" ? web : general) ?? list.first)?.id ?? value
        }, set: { self.set("highlight.dict", $0) })
    }
}

struct NativeSettingsView: View {
    let onAnkiTemplate: () -> Void
    @StateObject private var config = NativeConfig()

    private static let colors: [(String, String)] = [
        ("#ff9f0a", "Оранжевый"), ("#ffd60a", "Жёлтый"), ("#30d158", "Зелёный"), ("#64d2ff", "Голубой"),
        ("#bf5af2", "Фиолетовый"), ("#ff375f", "Красный"), ("#ffffff", "Белый"),
    ]

    private func webPage(_ only: String, _ title: String) -> some View {
        YomikiriWebView(url: OptionsView.URL_OPTIONS.withPathComponents([URLQueryItem(name: "only", value: only)]) ?? OptionsView.URL_OPTIONS)
            .ignoresSafeArea(.keyboard)
            .navigationTitle(title)
            .navigationBarTitleDisplayMode(.inline)
    }

    private func numberRow(_ title: String, _ key: String, _ fallback: Int) -> some View {
        HStack {
            Text(title)
            Spacer()
            TextField(title, value: config.int(key, fallback), format: .number)
                .keyboardType(.numberPad)
                .multilineTextAlignment(.trailing)
                .foregroundColor(.secondary)
                .frame(width: 120)
        }
    }

    var body: some View {
        Form {
            Section {
                HStack {
                    Text("Японский шрифт")
                    Spacer()
                    TextField("по умолчанию", text: config.string("general.font", ""))
                        .multilineTextAlignment(.trailing)
                        .foregroundColor(.secondary)
                }
                Stepper(value: config.int("general.font_size", 11), in: 9 ... 24) {
                    HStack {
                        Text("Размер шрифта")
                        Spacer()
                        Text(String(config.int("general.font_size", 11).wrappedValue)).foregroundColor(.secondary)
                    }
                }
                Stepper(value: config.int("general.tooltip_max_height", 300), in: 120 ... 1200, step: 20) {
                    HStack {
                        Text("Высота подсказки")
                        Spacer()
                        Text(String(config.int("general.tooltip_max_height", 300).wrappedValue)).foregroundColor(.secondary)
                    }
                }
            } header: {
                Text("Внешний вид")
            }

            Section {
                Toggle("Подсвечивать слова", isOn: config.bool("highlight.enabled", false))
            } header: {
                Text("Подсветка слов")
            } footer: {
                Text("Выделяет слова, которых ещё нет в Anki. После изменения обновите страницу.")
            }

            Section {
                Toggle("Подсвечивать по частотности", isOn: config.bool("highlight.freq", true))
                if !NativeConfig.freqDicts.isEmpty {
                    Picker("Словарь частот", selection: config.dictionary) {
                        ForEach(NativeConfig.freqDicts, id: \\.id) { item in
                            Text(item.label).tag(item.id)
                        }
                    }
                }
                numberRow("От места", "highlight.min", 3000)
                numberRow("До места", "highlight.max", 8000)
                Picker("Цвет подсветки", selection: config.string("highlight.color", "#ff9f0a")) {
                    ForEach(NativeSettingsView.colors, id: \\.0) { item in
                        Text(item.1).tag(item.0)
                    }
                }
            } header: {
                Text("Подсветка по частотности")
            } footer: {
                Text("1 — самое частое слово. Слова чаще первого места и реже второго не выделяются.")
            }

            Section {
                Toggle("N5 🟢", isOn: config.bool("highlight.jlpt.n5", false))
                Toggle("N4 🔵", isOn: config.bool("highlight.jlpt.n4", false))
                Toggle("N3 🟡", isOn: config.bool("highlight.jlpt.n3", false))
                Toggle("N2 🟠", isOn: config.bool("highlight.jlpt.n2", false))
                Toggle("N1 🔴", isOn: config.bool("highlight.jlpt.n1", false))
            } header: {
                Text("Подсветка по уровню JLPT")
            }

            Section {
                Toggle("Использовать Anki", isOn: config.bool("anki.enabled", false))
                Toggle("Возвращаться в Safari после добавления заметки", isOn: config.bool("anki.ios_auto_redirect", true))
                Button("Настроить шаблон Anki") {
                    onAnkiTemplate()
                }
                NavigationLink(destination: webPage("ankiImport", "Импорт колоды Anki")) {
                    Text("Импорт колоды Anki")
                }
            } header: {
                Text("Anki")
            }

            Section {
                NavigationLink(destination: webPage("about", "О программе")) {
                    Text("О программе и лицензии")
                }
            }
        }
        .onAppear {
            config.reload()
        }
    }
}
'''

hv = src / "safari/iOS (App)/HelpView.swift"
hv.write_text(hv.read_text(encoding="utf-8").rstrip("\n") + "\n" + SWIFT, encoding="utf-8")

ov = src / "safari/iOS (App)/OptionsView.swift"
s = ov.read_text(encoding="utf-8")
s, n = re.subn(r"YomikiriWebView\(url: OptionsView\.URL_OPTIONS\)\s*\n\s*\.handleExtraMessage\(self\.messageHandler\(\)\)\s*\n\s*\.ignoresSafeArea\(\.keyboard\)",
               "NativeSettingsView(onAnkiTemplate: { _ = requestAnkiInfo() })", s)
assert n == 1, "options web view not found exactly once"
ov.write_text(s, encoding="utf-8")

# the web settings page can show one group: options.html?only=ankiImport / about
mc = src / "main/src/components/options/MainColumn.svelte"
s = mc.read_text(encoding="utf-8")
s = once(s, "</script>\n", '  const only = new URLSearchParams(window.location.search).get("only");\n</script>\n', "script end")
s = once(s, "<div>\n", '<div>\n  {#if only === "ankiImport"}\n    <GroupAnkiImport />\n  {:else if only === "about"}\n    <GroupAbout />\n  {:else}\n', "div start")
s = once(s, "</div>", "  {/if}\n</div>", "div end")
mc.write_text(s, encoding="utf-8")
print("v1.47 native settings applied")
