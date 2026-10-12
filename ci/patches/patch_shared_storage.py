# Moved out of build-ios-v141-player.yml, step "Patch shared storage (sync fix, keychain channel, on-device diagnostics)" (GitHub limits workflow files to 500 KB).
import pathlib, re

root = pathlib.Path("src/safari")
tok = root / "YomikiriTokenizer/YomikiriTokenizer"


def replace_once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


# ---------- 1. Utils.swift: find every App Group this process can really use ----------
p = tok / "Utils.swift"
s = p.read_text()
s = replace_once(s, "import Foundation\n", "import Foundation\nimport Security\n", "utils import")
start = s.index("/// Returns URL path to directory that all Yomikiri apps share\n/// App Groups that may")
end = s.index("/// Returns shared caches directory.")
NEW_UTILS = r'''// MARK: - Shared storage between the app and the extensions

/// Groups from the provisioning profile of the personal certificate come first,
/// then the groups from the embedded profile of this process, then the original group.
private let knownAppGroupIds: [String] = (1 ... 5).map { "group.e9b3f7cfcd7710ea.\($0)" }

private func embeddedProfileEntitlements() -> [String: Any]? {
    guard let path = Bundle.main.path(forResource: "embedded", ofType: "mobileprovision"),
          let data = FileManager.default.contents(atPath: path),
          let text = String(data: data, encoding: .isoLatin1),
          let start = text.range(of: "<?xml"),
          let end = text.range(of: "</plist>"),
          start.lowerBound < end.upperBound,
          let xml = String(text[start.lowerBound ..< end.upperBound]).data(using: .utf8),
          let plist = (try? PropertyListSerialization.propertyList(from: xml, options: [], format: nil)) as? [String: Any]
    else {
        return nil
    }
    return plist["Entitlements"] as? [String: Any]
}

private func candidateAppGroupIds() -> [String] {
    var ids: [String] = []
    for id in knownAppGroupIds where !ids.contains(id) {
        ids.append(id)
    }
    if let entitlements = embeddedProfileEntitlements(),
       let groups = entitlements["com.apple.security.application-groups"] as? [String]
    {
        for id in groups.sorted() where !ids.contains(id) {
            ids.append(id)
        }
    }
    if !ids.contains(APP_GROUP_ID) {
        ids.append(APP_GROUP_ID)
    }
    return ids
}

/// "app", "ext" (Safari extension) or "action" (share sheet)
private func sharedProcessTag() -> String {
    let url = Bundle.main.bundleURL
    if url.pathExtension != "appex" {
        return "app"
    }
    return url.lastPathComponent.lowercased().contains("action") ? "action" : "ext"
}

/// App Groups that this process can really use. A group counts only if a file can be written into its folder.
let accessibleAppGroups: [(id: String, url: URL)] = {
    var result: [(id: String, url: URL)] = []
    let fm = FileManager.default
    for id in candidateAppGroupIds() {
        guard let url = fm.containerURL(forSecurityApplicationGroupIdentifier: id) else {
            continue
        }
        let probe = url.appendingPathComponent(".yomikiri-probe-" + sharedProcessTag())
        if fm.createFile(atPath: probe.path, contents: Data([49])) {
            result.append((id: id, url: url))
        }
    }
    return result
}()

/// The first App Group that this process can access, if there is one.
let resolvedAppGroup: (id: String, url: URL)? = accessibleAppGroups.first

/// Returns URL path to directory that all Yomikiri apps share
public func getSharedDirectory() throws -> URL {
    if let group = resolvedAppGroup {
        return group.url
    }
    // Fallback for builds without App Group access: the private folder of this process
    let fm = FileManager.default
    guard let dir = fm.urls(for: .applicationSupportDirectory, in: .userDomainMask).first else {
        throw YomikiriTokenizerError.CouldNotAccessDirectory
    }
    if !fm.fileExists(atPath: dir.path) {
        try fm.createDirectory(at: dir, withIntermediateDirectories: true)
    }
    return dir
}

// MARK: Keychain (second channel, works when App Groups are not available)

private let keychainService = "yomikiri.shared"

private func keychainQuery(_ key: String, group: String?) -> [String: Any] {
    var query: [String: Any] = [
        kSecClass as String: kSecClassGenericPassword,
        kSecAttrService as String: keychainService,
        kSecAttrAccount as String: key,
    ]
    if let group = group {
        query[kSecAttrAccessGroup as String] = group
    }
    return query
}

/// Access group that the system chooses for this process by default (its name starts with the team id).
private func keychainDefaultGroup() -> String? {
    let key = "diag.probe"
    var query = keychainQuery(key, group: nil)
    query[kSecReturnAttributes as String] = true
    query[kSecMatchLimit as String] = kSecMatchLimitOne
    var result: CFTypeRef?
    var status = SecItemCopyMatching(query as CFDictionary, &result)
    if status == errSecItemNotFound {
        var add = keychainQuery(key, group: nil)
        add[kSecValueData as String] = Data([49])
        add[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlock
        add[kSecReturnAttributes as String] = true
        status = SecItemAdd(add as CFDictionary, &result)
    }
    guard status == errSecSuccess, let attributes = result as? [String: Any] else {
        return nil
    }
    return attributes[kSecAttrAccessGroup as String] as? String
}

private let keychainDefaultGroupName: String? = keychainDefaultGroup()

/// nil means "default group of this process".
private let keychainGroups: [String?] = {
    var list: [String?] = [nil]
    if let def = keychainDefaultGroupName, let dot = def.firstIndex(of: ".") {
        let shared = String(def[def.startIndex ..< dot]) + ".yomikiri.shared"
        if shared != def {
            list.append(shared)
        }
    }
    return list
}()

private func keychainWrite(_ key: String, _ value: String, ts: Double, group: String?) -> OSStatus {
    guard let data = (String(ts) + "\n" + value).data(using: .utf8) else {
        return errSecParam
    }
    let base = keychainQuery(key, group: group)
    var status = SecItemUpdate(base as CFDictionary, [kSecValueData as String: data] as CFDictionary)
    if status == errSecItemNotFound {
        var add = base
        add[kSecValueData as String] = data
        add[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlock
        status = SecItemAdd(add as CFDictionary, nil)
    }
    return status
}

private func keychainRead(_ key: String, group: String?) -> (value: String, ts: Double)? {
    var query = keychainQuery(key, group: group)
    query[kSecReturnData as String] = true
    query[kSecMatchLimit as String] = kSecMatchLimitOne
    var result: CFTypeRef?
    let status = SecItemCopyMatching(query as CFDictionary, &result)
    guard status == errSecSuccess,
          let data = result as? Data,
          let text = String(data: data, encoding: .utf8),
          let newline = text.firstIndex(of: "\n")
    else {
        return nil
    }
    let ts = Double(String(text[text.startIndex ..< newline])) ?? 0
    return (value: String(text[text.index(after: newline)...]), ts: ts)
}

private func keychainDelete(_ key: String, group: String?) {
    _ = SecItemDelete(keychainQuery(key, group: group) as CFDictionary)
}

// MARK: Key-value storage: written everywhere, the newest value wins

struct SharedValue {
    var value: String
    var ts: Double
    var source: String
}

/// All copies of the value that this process can see.
func sharedStoreCopies(_ key: String) -> [SharedValue] {
    var found: [SharedValue] = []
    for group in accessibleAppGroups {
        guard let defaults = UserDefaults(suiteName: group.id), let object = defaults.object(forKey: key) else {
            continue
        }
        var text: String?
        if let string = object as? String {
            text = string
        } else if let number = object as? NSNumber {
            text = number.stringValue
        }
        if let text = text {
            found.append(SharedValue(value: text, ts: defaults.double(forKey: key + "#ts"), source: group.id))
        }
    }
    for group in keychainGroups {
        if let item = keychainRead(key, group: group) {
            found.append(SharedValue(value: item.value, ts: item.ts, source: "keychain " + (group ?? "default")))
        }
    }
    // private copy of this process: the last resort when nothing is shared
    let own = UserDefaults.standard
    if let text = own.string(forKey: "yomikiri." + key) {
        found.append(SharedValue(value: text, ts: own.double(forKey: "yomikiri." + key + "#ts"), source: "private"))
    }
    return found
}

func sharedStoreRead(_ key: String) -> String? {
    var best: SharedValue?
    for item in sharedStoreCopies(key) {
        if let current = best {
            if item.ts > current.ts {
                best = item
            }
        } else {
            best = item
        }
    }
    return best?.value
}

func sharedStoreWrite(_ key: String, _ value: String?) {
    let ts = Date().timeIntervalSince1970
    for group in accessibleAppGroups {
        guard let defaults = UserDefaults(suiteName: group.id) else {
            continue
        }
        if let value = value {
            defaults.set(value, forKey: key)
            defaults.set(ts, forKey: key + "#ts")
        } else {
            defaults.removeObject(forKey: key)
            defaults.removeObject(forKey: key + "#ts")
        }
        defaults.synchronize()
    }
    for group in keychainGroups {
        if let value = value {
            _ = keychainWrite(key, value, ts: ts, group: group)
        } else {
            keychainDelete(key, group: group)
        }
    }
    let own = UserDefaults.standard
    if let value = value {
        own.set(value, forKey: "yomikiri." + key)
        own.set(ts, forKey: "yomikiri." + key + "#ts")
    } else {
        own.removeObject(forKey: "yomikiri." + key)
        own.removeObject(forKey: "yomikiri." + key + "#ts")
    }
}

// MARK: Diagnostics

private let heartbeatLock = NSLock()
private var lastHeartbeat: Double = 0

/// Tells the other processes that this one is alive and can write to the shared storage.
public func sharedStorageHeartbeat() {
    let now = Date().timeIntervalSince1970
    heartbeatLock.lock()
    let skip = now - lastHeartbeat < 3
    if !skip {
        lastHeartbeat = now
    }
    heartbeatLock.unlock()
    if skip {
        return
    }
    sharedStoreWrite("diag.hb." + sharedProcessTag(), String(now))
}

/// Human-readable state of the shared storage, shown in the app and in the extension popup.
public func sharedStorageReport() -> String {
    sharedStorageHeartbeat()
    let now = Date().timeIntervalSince1970
    var lines: [String] = []
    lines.append("процесс: " + sharedProcessTag() + " (" + Bundle.main.bundleURL.lastPathComponent + ")")
    lines.append("bundle id: " + (Bundle.main.bundleIdentifier ?? "?"))
    if let entitlements = embeddedProfileEntitlements() {
        lines.append("профиль в процессе: есть")
        if let id = entitlements["application-identifier"] as? String {
            lines.append("  application-identifier: " + id)
        }
        if let groups = entitlements["com.apple.security.application-groups"] as? [String] {
            lines.append("  группы в профиле: " + String(groups.count))
        }
    } else {
        lines.append("профиль в процессе: НЕТ")
    }
    if accessibleAppGroups.isEmpty {
        lines.append("App Group доступны: НЕТ")
    } else {
        lines.append("App Group доступны (" + String(accessibleAppGroups.count) + "): "
            + accessibleAppGroups.map { $0.id.replacingOccurrences(of: "group.e9b3f7cfcd7710ea.", with: "…") }.joined(separator: " "))
    }
    lines.append("папка файлов: " + (resolvedAppGroup?.id ?? "личная (не общая)"))
    lines.append("keychain, группа по умолчанию: " + (keychainDefaultGroupName ?? "НЕДОСТУПЕН"))
    for group in keychainGroups {
        let status = keychainWrite("diag.selftest", String(now), ts: now, group: group)
        let back = keychainRead("diag.selftest", group: group) != nil
        lines.append("  keychain " + (group ?? "(по умолчанию)") + ": запись " + String(status) + ", чтение " + (back ? "ок" : "нет"))
    }
    lines.append("— последние сигналы процессов —")
    for tag in ["app", "ext", "action"] {
        let copies = sharedStoreCopies("diag.hb." + tag).filter { $0.source != "private" }
        var newest: Double = 0
        for copy in copies {
            newest = max(newest, Double(copy.value) ?? 0)
        }
        if copies.isEmpty {
            lines.append(tag + ": не виден")
        } else {
            lines.append(tag + ": " + String(Int(now - newest)) + " с назад, каналов: " + String(copies.count))
        }
    }
    lines.append("— данные —")
    for key in ["config", "stats.v1"] {
        let copies = sharedStoreCopies(key)
        if copies.isEmpty {
            lines.append(key + ": пусто")
        }
        for copy in copies {
            let age = copy.ts > 0 ? String(Int(now - copy.ts)) + " с" : "без метки"
            let source = copy.source.replacingOccurrences(of: "group.e9b3f7cfcd7710ea.", with: "…")
            lines.append(key + " [" + source + "]: " + String(copy.value.count) + " зн., " + age)
        }
    }
    return lines.joined(separator: "\n")
}

'''
s = s[:start] + NEW_UTILS + s[end:]
p.write_text(s)

# ---------- 2. Storage.swift: use the shared storage above ----------
(tok / "Storage.swift").write_text(r'''/// Files and configurations shared between Yomikiri app and extensions.

import Foundation

/// Wrapper for shared storage between app and extensions
/// Each value saved in Storage has its own getter and setter
public enum Storage {
    public static let config = StoragePropertyWithDefault<String>(key: "config", other: "{}")
    public static let jmdictEtag = StorageProperty<String>(key: "dict.jmdict.etag")
    public static let jmnedictEtag = StorageProperty<String>(key: "dict.jmnedict.etag")
    public static let dictSchemaVer = StorageProperty<Int>(key: "dict.schema_ver")
    /// Reading and mining statistics (JSON), shared between the extension and the app
    public static let stats = StoragePropertyWithDefault<String>(key: "stats.v1", other: "null")
}

private func storageDecode<T>(_ raw: String?) -> T? {
    guard let raw = raw else {
        return nil
    }
    if T.self == String.self {
        return raw as? T
    }
    if T.self == Int.self {
        return Int(raw) as? T
    }
    return nil
}

private func storageEncode<T>(_ value: T?) -> String? {
    guard let value = value else {
        return nil
    }
    return String(describing: value)
}

public struct StorageProperty<T> {
    let key: String

    public func get() throws -> T? {
        return storageDecode(sharedStoreRead(key))
    }

    public func set(_ value: T?) throws {
        sharedStoreWrite(key, storageEncode(value))
    }
}

public struct StoragePropertyWithDefault<T> {
    let key: String
    let other: T

    public func get() throws -> T {
        let value: T? = storageDecode(sharedStoreRead(key))
        return value ?? other
    }

    public func set(_ value: T?) throws {
        sharedStoreWrite(key, storageEncode(value))
    }
}
''')

# ---------- 3. extension handler: "diag" message and heartbeat ----------
p = root / "iOS (Extension)/IOSWebExtensionHandler.swift"
s = p.read_text()
s = replace_once(s, "        let completionHandler = context.completeRequest\n",
                 "        let completionHandler = context.completeRequest\n        sharedStorageHeartbeat()\n", "heartbeat")
s = replace_once(s, '                case "loadStats":\n',
                 '                case "diag":\n                    jsonResponse = try jsonSerialize(obj: sharedStorageReport())\n                case "loadStats":\n', "diag case")
p.write_text(s)

# ---------- 4. app: diagnostics block on the statistics screen ----------
p = root / "iOS (App)/HelpView.swift"
s = p.read_text()
s = replace_once(s, "    @State private var confirmReset = false\n",
                 "    @State private var confirmReset = false\n    @State private var diag = \"\"\n", "diag state")
s = replace_once(s, '''                .buttonStyle(.bordered)
            }
            .padding(16)''', '''                .buttonStyle(.bordered)

                Button {
                    diag = sharedStorageReport()
                } label: {
                    Text("Диагностика синхронизации")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.bordered)

                if !diag.isEmpty {
                    Text(diag)
                        .font(.system(size: 11, design: .monospaced))
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .textSelection(.enabled)
                        .padding(10)
                        .background(Color(.secondarySystemBackground))
                        .cornerRadius(10)
                    Button {
                        UIPasteboard.general.string = diag
                    } label: {
                        Text("Скопировать")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.bordered)
                }
            }
            .padding(16)''', "diag block")
s = replace_once(s, "        .onAppear {\n            model.reload()\n",
                 "        .onAppear {\n            sharedStorageHeartbeat()\n            model.reload()\n", "heartbeat onAppear")
p.write_text(s)

# ---------- 5. extension popup: same diagnostics ----------
ext = pathlib.Path("src/main/src/extension")
p = ext.parent / "platform/ios/index.ts"
s = p.read_text()
s = replace_once(s, "  saveStats: [unknown, null];\n", "  saveStats: [unknown, null];\n  diag: [null, string];\n", "diag message map")
p.write_text(s)

p = ext / "popup/StatsView.svelte"
s = p.read_text()
s = replace_once(s, '  import { onMount, onDestroy } from "svelte";\n',
                 '  import { onMount, onDestroy } from "svelte";\n  import { ExtensionPlatform as Platform } from "@platform";\n', "popup import")
s = replace_once(s, "  let confirmTimer: number | undefined;\n", '''  let confirmTimer: number | undefined;
  let diag = "";
  let diagBusy = false;

  async function showDiag(): Promise<void> {
    diagBusy = true;
    try {
      // eslint-disable-next-line
      diag = String(await (Platform as any).requestToApp("diag", null));
    } catch (e) {
      diag = "Ошибка: " + String(e);
    }
    diagBusy = false;
  }
''', "popup diag script")
s = replace_once(s, '  <button class="reset" class:confirm={confirmReset} on:click={onReset}>', '''  <button class="diag-button" on:click={() => void showDiag()}>
    {diagBusy ? "..." : "Диагностика синхронизации"}
  </button>
  {#if diag !== ""}
    <pre class="diag">{diag}</pre>
  {/if}

  <button class="reset" class:confirm={confirmReset} on:click={onReset}>''', "popup diag markup")
s = replace_once(s, "  .reset.confirm {", '''  .diag-button {
    display: block;
    width: 100%;
    margin-top: 1em;
    padding: 0.7em 1em;
    text-align: center;
    border: 1px solid var(--border);
    border-radius: 0.5em;
    font-size: 0.9em;
  }

  .diag {
    margin-top: 0.6em;
    padding: 0.6em;
    font-size: 0.7em;
    white-space: pre-wrap;
    word-break: break-all;
    user-select: text;
    -webkit-user-select: text;
    border: 1px solid var(--border);
    border-radius: 0.5em;
  }

  .reset.confirm {''', "popup diag css")
p.write_text(s)
# ---------- 6. share sheet: the link arrives as a JSON string (with quotes), decode it; stronger opening ----------
p = root / "Yomikiri Action/ActionViewController.swift"
s = p.read_text()
s = replace_once(s, """                    guard let urlString = request as? String else {
                        throw "'openLink' url is not string"
                    }
""", """                    guard let rawString = request as? String else {
                        throw "'openLink' url is not string"
                    }
                    // the web part sends the link as a JSON string: "\\"anki://...\\""
                    let urlString: String = (try? jsonDeserialize(json: rawString)) ?? rawString
""", "action decode json")
m = re.search(r"    func openURL\(_ url: URL\) \{.*?\n    \}\n", s, re.S)
assert m, "action openURL not found"
NEW_OPEN = r"""    func openURL(_ url: URL) {
        if let ctx = self.extensionContext {
            ctx.open(url, completionHandler: nil)
        }
        // A share extension cannot open another app by itself: ask an object that can (responder chain, then UIApplication).
        let selector = NSSelectorFromString("openURL:options:completionHandler:")
        typealias OpenFunction = @convention(c) (AnyObject, Selector, URL, [UIApplication.OpenExternalURLOptionsKey: Any], ((Bool) -> Void)?) -> Void
        var targets: [NSObject] = []
        var responder: UIResponder? = self
        while let current = responder {
            // UIScene has a method with the same name but other options: only UIApplication is suitable
            if current is UIApplication {
                targets.append(current)
            }
            responder = current.next
        }
        let sharedSelector = NSSelectorFromString("sharedApplication")
        if UIApplication.responds(to: sharedSelector),
           let app = UIApplication.perform(sharedSelector)?.takeUnretainedValue() as? NSObject,
           app is UIApplication
        {
            targets.append(app)
        }
        for target in targets {
            if target.responds(to: selector), let imp = target.method(for: selector) {
                let function = unsafeBitCast(imp, to: OpenFunction.self)
                function(target, selector, url, [:], nil)
                return
            }
        }
    }
"""
s = s[: m.start()] + NEW_OPEN + s[m.end():]
p.write_text(s)
print("share sheet patch OK")
print("sync patch OK")
