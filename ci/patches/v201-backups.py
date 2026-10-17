# v2.01: the folder of the backups, three ways and a check.
# - The picker's «Открыть» does nothing for the folders of AnkiMobile even on iOS 26.7.1 (iOS enables it only in
#   folders it considers writable for the app), so the folder is taken three ways:
#   1. the picker with several folders allowed: its «Выбрать» mode ticks a folder instead of opening it;
#   2. dragging the folder in from «Файлы»: the folder comes from Files itself (in place), not from the picker;
#   3. a check: the picker opens in Satori's own folder — when even that one is not taken, the picker does not work
#      in this install of Satori at all, whatever the folder.
# - The deprecated picker of 1.98 («Другой способ выбора папки») is gone: it failed the same way.
import pathlib


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")

# ---------- the picker: several folders, a starting folder ----------
s = once(s, '''    static func present(_ onPick: @escaping (URL) -> Void, onCancel: @escaping (Bool) -> Void = { _ in },
                        legacy: Bool = false) {
''', '''    static func present(_ onPick: @escaping (URL) -> Void, onCancel: @escaping (Bool) -> Void = { _ in },
                        multiple: Bool = false, start: URL? = nil) {
''', "present params")
s = once(s, '''        // the older API: the same picker made another way (deprecated, still there)
        let picker = legacy
            ? UIDocumentPickerViewController(documentTypes: ["public.folder"], in: .open)
            : UIDocumentPickerViewController(forOpeningContentTypes: [.folder], asCopy: false)
        picker.allowsMultipleSelection = false
''', '''        let picker = UIDocumentPickerViewController(forOpeningContentTypes: [.folder], asCopy: false)
        // several allowed: the picker gets its «Выбрать» mode, where a folder is ticked instead of opened
        picker.allowsMultipleSelection = multiple
        if let start {
            picker.directoryURL = start
        }
''', "picker setup")

# ---------- a folder dragged in from Files ----------
s = once(s, '''    /// One backup chosen as a file (a copy): read once like the newest one of the folder.
    func read(_ file: URL) {
''', '''    /// A folder dragged in from «Файлы». In place it is kept like a chosen folder; a copy of it is read once (its
    /// newest backup), since a copy is gone after the drop.
    func dropFolder(_ providers: [NSItemProvider]) -> Bool {
        let folderType = UTType.folder.identifier
        let urlType = UTType.fileURL.identifier
        guard let provider = providers.first(where: { item in
            item.hasItemConformingToTypeIdentifier(folderType) || item.hasItemConformingToTypeIdentifier(urlType)
        }) else {
            status = "Satori ждёт папку: перетащите папку «Anki» или папку с бэкапами"
            return false
        }
        status = "Получаю перетащенную папку…"
        if provider.hasItemConformingToTypeIdentifier(folderType) {
            _ = provider.loadInPlaceFileRepresentation(forTypeIdentifier: folderType) { url, inPlace, error in
                guard let url else {
                    let reason = error?.localizedDescription ?? "нет ответа"
                    Task { @MainActor in
                        AnkiBackupSync.shared.say("Папку не удалось получить: " + reason)
                    }
                    return
                }
                if inPlace {
                    Task { @MainActor in
                        AnkiBackupSync.shared.choose(url)
                    }
                    return
                }
                // a copy lives only inside this handler: its newest backup is kept now
                let kept = AnkiBackupSync.keepNewest(in: url)
                Task { @MainActor in
                    AnkiBackupSync.shared.readCopy(kept, folder: url.lastPathComponent)
                }
            }
        } else {
            provider.loadItem(forTypeIdentifier: urlType, options: nil) { item, error in
                let url = (item as? URL) ?? (item as? Data).flatMap { URL(dataRepresentation: $0, relativeTo: nil) }
                let reason = error?.localizedDescription ?? "нет ответа"
                Task { @MainActor in
                    if let url {
                        AnkiBackupSync.shared.choose(url)
                    } else {
                        AnkiBackupSync.shared.say("Папку не удалось получить: " + reason)
                    }
                }
            }
        }
        return true
    }

    /// The newest backup of a dragged copy of a folder (and of its folders «Backups…»), copied where it outlives the
    /// drop; nil when there is none.
    nonisolated static func keepNewest(in folder: URL) -> URL? {
        let manager = FileManager.default
        let keys: [URLResourceKey] = [.contentModificationDateKey]
        var files = (try? manager.contentsOfDirectory(at: folder, includingPropertiesForKeys: keys)) ?? []
        for sub in files where sub.lastPathComponent.lowercased().hasPrefix("backups") {
            files += (try? manager.contentsOfDirectory(at: sub, includingPropertiesForKeys: keys)) ?? []
        }
        var newest: URL? = nil
        var newestDate = Date.distantPast
        for file in files where file.pathExtension.lowercased() == "colpkg" {
            let date = (try? file.resourceValues(forKeys: [.contentModificationDateKey]))?.contentModificationDate ?? .distantPast
            if newest == nil || date > newestDate {
                newest = file
                newestDate = date
            }
        }
        guard let newest else { return nil }
        let target = manager.temporaryDirectory.appendingPathComponent(newest.lastPathComponent)
        try? manager.removeItem(at: target)
        return (try? manager.copyItem(at: newest, to: target)) != nil ? target : nil
    }

    /// The newest backup of a dragged copy: read once.
    func readCopy(_ file: URL?, folder: String) {
        guard !importing else {
            status = "Satori уже читает бэкап: перетащите папку чуть позже"
            return
        }
        guard let file else {
            status = "iOS отдала копию папки «" + folder + "», а в ней нет бэкапов (.colpkg)"
            return
        }
        read(file)
        status = "iOS отдала копию папки, а не саму папку: бэкап «" + file.lastPathComponent
            + "» прочитан один раз, следить за новыми так нельзя"
    }

    /// One backup chosen as a file (a copy): read once like the newest one of the folder.
    func read(_ file: URL) {
''', "drop folder")

# ---------- the row ----------
s = once(s, '''            Button(sync.connected ? "Папка бэкапов AnkiMobile: выбрана" : "Папка бэкапов AnkiMobile…") {
                sync.say("Зайдите в папку «Anki» (или в папку с бэкапами) и нажмите «Открыть»…")
                FolderPick.present({ url in
                    sync.choose(url)
                }, onCancel: { swiped in
                    sync.say(swiped ? "Окно смахнули: папка не выбрана" : "Окно закрыто кнопкой «Отмена»: папка не выбрана")
                })
            }
            Button("Другой способ выбора папки") {
                sync.say("Другой способ: зайдите в папку «Anki» и нажмите «Открыть»…")
                FolderPick.present({ url in
                    sync.choose(url)
                }, onCancel: { swiped in
                    sync.say(swiped ? "Окно смахнули: папка не выбрана" : "Окно закрыто кнопкой «Отмена»: папка не выбрана")
                }, legacy: true)
            }
''', '''            Button(sync.connected ? "Папка бэкапов AnkiMobile: выбрана" : "Папка бэкапов AnkiMobile…") {
                sync.say("В окне откройте «このiPhone内» (На iPhone), нажмите «選択» (Выбрать) вверху, отметьте «Anki» и нажмите «開く» (Открыть)…")
                FolderPick.present({ url in
                    sync.choose(url)
                }, onCancel: { swiped in
                    sync.say(swiped ? "Окно смахнули: папка не выбрана" : "Окно закрыто кнопкой «Отмена»: папка не выбрана")
                }, multiple: true)
            }
            BackupDropZone(sync: sync)
            Button("Проверка: выбрать папку Satori") {
                sync.say("Проверка: окно откроется в папке самого Satori — сразу нажмите «開く» (Открыть)…")
                let own = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
                FolderPick.present({ url in
                    sync.say("✓ Папка «" + url.lastPathComponent + "» выбралась: окно выбора в Satori работает, iOS не "
                        + "открывает только папку AnkiMobile. Перетащите её из «ファイル» (Файлы) в рамку выше.")
                }, onCancel: { _ in
                    sync.say("✗ Даже папка самого Satori не выбралась: окно выбора папок не работает в этой установке "
                        + "Satori. Пришлите этот текст.")
                }, start: own)
            }
''', "row buttons")
s = once(s, '''        var text = "Выберите папку «Anki» (или папку с бэкапами в ней): Satori читает самый свежий бэкап из «Backups» и "
            + "«Backups for …», а потом новые — сам, при открытии. Для проверки можно выбрать «На iPhone → Satori»: если и "
            + "она не выбирается, iOS не даёт Satori папки вообще."
''', '''        var text = "Нужна папка «Anki» (или папка с бэкапами в ней): Satori читает самый свежий бэкап из «Backups» и "
            + "«Backups for …», а потом новые — сам, при открытии. Если «Открыть» в окне выбора не срабатывает, "
            + "перетащите папку из «ファイル» (Файлы) в рамку."
''', "row footer")

s = s.rstrip("\n") + '''

/// A folder dragged in from «Файлы»: open this page, in «Файлы» hold the folder «Anki» until it lifts, switch to
/// Satori with another finger and drop it here. Files hands the folder itself over, without the picker.
struct BackupDropZone: View {
    @ObservedObject var sync: AnkiBackupSync
    @State private var targeted = false

    var body: some View {
        VStack(spacing: 6) {
            Image(systemName: "folder.badge.plus")
                .font(.title2)
            Text("Перетащите сюда папку «Anki» из «ファイル» (Файлы)")
                .font(.subheadline.weight(.semibold))
            Text("В «ファイル» зажмите папку «Anki», пока она не приподнимется, и, не отпуская, другим пальцем смахните "
                + "от нижнего края и откройте Satori на этой странице. Отпустите папку на рамку.")
                .font(.caption)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 14)
        .background(
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .strokeBorder(style: StrokeStyle(lineWidth: 1.5, dash: [6]))
                .foregroundColor(targeted ? .accentColor : .secondary)
        )
        .onDrop(of: [UTType.folder, UTType.fileURL], isTargeted: $targeted) { providers in
            sync.dropFolder(providers)
        }
    }
}
'''
hv.write_text(s, encoding="utf-8")
print("v2.01 backups applied")
