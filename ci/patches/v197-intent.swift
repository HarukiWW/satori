
// MARK: - Satori v1.97: a backup of AnkiMobile from Shortcuts

/// Shortcuts: a backup of AnkiMobile handed to Satori. The folder picker of iOS gives Satori no folder of AnkiMobile,
/// Shortcuts can read it: an automation "AnkiMobile closed → the newest file of Anki/Backups → this action" keeps the
/// known words fresh by itself.
@available(iOS 16.0, *)
struct ReadAnkiBackupIntent: AppIntent {
    static var title: LocalizedStringResource = "Обновить знакомые слова из бэкапа Anki"
    static var description = IntentDescription(
        "Satori читает бэкап AnkiMobile (.colpkg): его зрелые карточки становятся знакомыми словами.")

    @Parameter(title: "Бэкап")
    var backup: IntentFile

    func perform() async throws -> some IntentResult & ProvidesDialog {
        let data = backup.data
        let name = backup.filename
        let said = await MainActor.run {
            AnkiBackupSync.shared.drop(data, name: name)
        }
        return .result(dialog: "\(said)")
    }
}
