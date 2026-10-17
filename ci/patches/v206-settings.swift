
// MARK: - Satori v2.06: the Anki template and the marked words, native

/// What AnkiMobile tells about its collection (infoForAdding): the decks and the note types with their fields.
struct AnkiMobileInfo {
    var decks: [String] = []
    var notetypes: [(name: String, fields: [String])] = []

    init?(json: String) {
        guard let data = json.data(using: .utf8),
              let root = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] else { return nil }
        decks = ((root["decks"] as? [[String: Any]]) ?? []).compactMap { $0["name"] as? String }
        for item in (root["notetypes"] as? [[String: Any]]) ?? [] {
            guard let name = item["name"] as? String else { continue }
            let fields = ((item["fields"] as? [[String: Any]]) ?? []).compactMap { $0["name"] as? String }
            notetypes.append((name: name, fields: fields))
        }
    }
}

/// What a field of the note gets (the "content" of a field of anki.anki_template, as the web builder reads it).
enum AnkiFieldContent {
    static let all: [(id: String, name: String)] = [
        ("", "—"), ("word", "Слово"), ("sentence", "Предложение"), ("translated-sentence", "Перевод предложения"),
        ("meaning", "Значение"), ("example", "Примеры из словаря"), ("audio", "Произношение слова"),
        ("url", "Адрес страницы"), ("link", "Ссылка на страницу"),
    ]
    static let forms: [(id: String, name: String)] = [
        ("as-is", "Как в тексте"), ("dict-form", "Словарная форма"), ("main-dict-form", "Основная форма из словаря"),
    ]
    static let styles: [(id: String, name: String)] = [
        ("basic", "Без фуриганы"), ("furigana-anki", "Фуригана Anki"), ("furigana-html", "Фуригана HTML"),
        ("kana-only", "Только кана"),
    ]
    static let marks: [(id: String, name: String)] = [
        ("none", "Не выделять"), ("cloze", "Cloze"), ("bold", "Жирным"), ("span", "В span"),
    ]
    static let formats: [(id: String, name: String)] = [
        ("numbered", "Нумерованный список"), ("unnumbered", "Маркированный список"), ("line", "Одна строка"),
        ("div", "Блоки div"), ("yomichan", "Как в Yomichan"),
    ]

    static func name(_ id: String) -> String {
        all.first { $0.id == id }?.name ?? id
    }

    /// A new field with this content and the defaults of the web editor (newAnkiTemplateField).
    static func make(_ field: String, _ content: String) -> [String: Any] {
        var made: [String: Any] = ["name": field, "content": content]
        if content == "word" {
            made["form"] = "as-is"
            made["style"] = "basic"
        } else if content == "sentence" {
            made["style"] = "basic"
            made["word"] = "none"
        } else if content == "meaning" {
            made["full_format"] = "numbered"
            made["full_pos"] = false
            made["full_max_item"] = 0
            made["single_pos"] = false
            made["single_max_item"] = 0
        }
        return made
    }
}

/// Настройки → Anki → «Шаблон Anki»: the deck, the note type and what goes into every field. The fields are kept
/// per name, so a change of the note type loses nothing; every change is saved at once.
struct AnkiTemplateView: View {
    /// AnkiMobile's answer on the pasteboard (after Satori asked it); throws when there is none
    let loadInfo: () async throws -> String
    @StateObject private var config = NativeConfig()
    @State private var info: AnkiMobileInfo? = nil
    @State private var loaded = false
    @State private var deck = ""
    @State private var notetype = ""
    @State private var tags = ""
    @State private var fields: [String: [String: Any]] = [:]
    @State private var savedNames: [String] = []

    private var fieldNames: [String] {
        info?.notetypes.first { $0.name == notetype }?.fields ?? savedNames
    }

    private var deckChoices: [String] {
        var list = info?.decks ?? []
        if !deck.isEmpty && !list.contains(deck) {
            list.append(deck)
        }
        return list
    }

    private var notetypeChoices: [String] {
        var list = info?.notetypes.map { $0.name } ?? []
        if !notetype.isEmpty && !list.contains(notetype) {
            list.append(notetype)
        }
        return list
    }

    private func field(_ name: String) -> Binding<[String: Any]> {
        Binding(get: {
            fields[name] ?? AnkiFieldContent.make(name, "")
        }, set: { value in
            fields[name] = value
            save()
        })
    }

    private func summary(_ name: String) -> String {
        AnkiFieldContent.name((fields[name]?["content"] as? String) ?? "")
    }

    var body: some View {
        Form {
            if !loaded {
                HStack(spacing: 10) {
                    ProgressView()
                    Text("Читаю ответ AnkiMobile…")
                }
            } else {
                Section {
                    Picker("Колода", selection: $deck) {
                        ForEach(deckChoices, id: \.self) { name in
                            Text(name).tag(name)
                        }
                    }
                    Picker("Тип заметки", selection: $notetype) {
                        ForEach(notetypeChoices, id: \.self) { name in
                            Text(name).tag(name)
                        }
                    }
                    if info == nil {
                        Text("AnkiMobile не ответил: колоды и поля — из сохранённого шаблона.")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                } header: {
                    Text("AnkiMobile")
                }
                Section {
                    ForEach(fieldNames, id: \.self) { name in
                        NavigationLink(destination: AnkiFieldEditor(field: field(name))) {
                            HStack {
                                Text(name)
                                Spacer()
                                Text(summary(name))
                                    .foregroundColor(.secondary)
                            }
                        }
                    }
                } header: {
                    Text("Поля")
                }
                Section {
                    TextField("через пробел", text: $tags)
                        .disableAutocorrection(true)
                        .textInputAutocapitalization(.never)
                } header: {
                    Text("Теги")
                }
            }
        }
        .navigationTitle("Шаблон Anki")
        .navigationBarTitleDisplayMode(.inline)
        .navigationBarHidden(false)
        .satoriBackdrop()
        .animation(.default, value: loaded)
        .task {
            await load()
        }
        .onChange(of: deck) { _ in
            save()
        }
        .onChange(of: notetype) { _ in
            save()
        }
        .onChange(of: tags) { _ in
            save()
        }
    }

    @MainActor
    private func load() async {
        guard !loaded else { return }
        if let json = try? await loadInfo() {
            info = AnkiMobileInfo(json: json)
        }
        config.reload()
        let saved = config.values["anki.anki_template"] as? [String: Any]
        deck = (saved?["deck"] as? String) ?? info?.decks.first ?? ""
        notetype = (saved?["notetype"] as? String) ?? info?.notetypes.first?.name ?? ""
        tags = (saved?["tags"] as? String) ?? ""
        for item in (saved?["fields"] as? [[String: Any]]) ?? [] {
            guard let name = item["name"] as? String else { continue }
            fields[name] = item
            savedNames.append(name)
        }
        loaded = true
        save()
    }

    /// The template the web builder reads: the fields of the chosen note type, in its order.
    private func save() {
        guard loaded else { return }
        var list: [[String: Any]] = []
        for name in fieldNames {
            list.append(fields[name] ?? AnkiFieldContent.make(name, ""))
        }
        let template: [String: Any] = ["deck": deck, "notetype": notetype, "tags": tags, "fields": list]
        config.set("anki.anki_template", template)
    }
}

/// One field of the template: its content and the options of that content.
struct AnkiFieldEditor: View {
    @Binding var field: [String: Any]
    /// the options of the other contents, kept while the content is switched back and forth
    @State private var kept: [String: [String: Any]] = [:]

    private var kind: String {
        (field["content"] as? String) ?? ""
    }

    private var content: Binding<String> {
        Binding(get: {
            kind
        }, set: { value in
            let name = (field["name"] as? String) ?? ""
            kept[kind] = field
            field = kept[value] ?? AnkiFieldContent.make(name, value)
        })
    }

    private func text(_ key: String, _ fallback: String) -> Binding<String> {
        Binding(get: { (field[key] as? String) ?? fallback }, set: { field[key] = $0 })
    }

    private func flag(_ key: String) -> Binding<Bool> {
        Binding(get: { (field[key] as? Bool) ?? false }, set: { field[key] = $0 })
    }

    private func number(_ key: String) -> Binding<Int> {
        Binding(get: { (field[key] as? NSNumber)?.intValue ?? 0 }, set: { field[key] = $0 })
    }

    private func choice(_ title: String, _ key: String, _ fallback: String,
                        _ options: [(id: String, name: String)]) -> some View {
        Picker(title, selection: text(key, fallback)) {
            ForEach(options, id: \.id) { option in
                Text(option.name).tag(option.id)
            }
        }
    }

    private func limit(_ title: String, _ key: String) -> some View {
        Stepper(value: number(key), in: 0 ... 30) {
            HStack {
                Text(title)
                Spacer()
                Text(number(key).wrappedValue == 0 ? "все" : String(number(key).wrappedValue))
                    .foregroundColor(.secondary)
            }
        }
    }

    var body: some View {
        Form {
            Section {
                Picker("Содержимое", selection: content) {
                    ForEach(AnkiFieldContent.all, id: \.id) { option in
                        Text(option.name).tag(option.id)
                    }
                }
            }
            if kind == "word" {
                Section {
                    choice("Форма", "form", "as-is", AnkiFieldContent.forms)
                    choice("Фуригана", "style", "basic", AnkiFieldContent.styles)
                }
            } else if kind == "sentence" {
                Section {
                    choice("Выбранное слово", "word", "none", AnkiFieldContent.marks)
                    choice("Фуригана", "style", "basic", AnkiFieldContent.styles)
                }
            } else if kind == "meaning" {
                Section {
                    choice("Формат", "full_format", "numbered", AnkiFieldContent.formats)
                    Toggle("Часть речи", isOn: flag("full_pos"))
                    limit("Переводов", "full_max_item")
                } header: {
                    Text("Вся статья")
                }
                Section {
                    Toggle("Часть речи", isOn: flag("single_pos"))
                    limit("Переводов", "single_max_item")
                } header: {
                    Text("Выбранное значение")
                }
            }
        }
        .navigationTitle((field["name"] as? String) ?? "")
        .navigationBarTitleDisplayMode(.inline)
        .satoriBackdrop()
        .animation(.default, value: kind)
    }
}

/// Настройки → Anki → «Отмеченные слова»: the words marked «Знаю» and «Игнор», the newest first; a mark can be taken
/// away (the word comes back into the lists of unknown words).
struct MarkedWordsView: View {
    @State private var known: [String] = []
    @State private var ignored: [String] = []
    @State private var search = ""
    @State private var confirm = false

    private func matching(_ words: [String]) -> [String] {
        search.isEmpty ? words : words.filter { $0.contains(search) }
    }

    private func load() {
        let lists = WordMarks.lists()
        known = lists.known.reversed()
        ignored = lists.ignored.reversed()
    }

    @ViewBuilder
    private func section(_ title: String, _ words: [String]) -> some View {
        let shown = matching(words)
        if !shown.isEmpty {
            Section {
                ForEach(shown, id: \.self) { word in
                    Text(word)
                        .font(.system(size: 20))
                        .swipeActions(edge: .trailing) {
                            Button("Снять") {
                                WordMarks.set(word, nil)
                                withAnimation {
                                    load()
                                }
                            }
                            .tint(.accentColor)
                        }
                }
            } header: {
                Text(title + ": " + String(words.count))
            }
        }
    }

    var body: some View {
        List {
            section("Знаю", known)
            section("Игнор", ignored)
            if known.isEmpty && ignored.isEmpty {
                Text("Отмеченных слов нет")
                    .foregroundColor(.secondary)
            }
        }
        .searchable(text: $search, placement: .navigationBarDrawer(displayMode: .always))
        .navigationTitle("Отмеченные слова")
        .navigationBarTitleDisplayMode(.inline)
        .navigationBarHidden(false)
        .toolbar {
            ToolbarItem(placement: .primaryAction) {
                Button("Сбросить", role: .destructive) {
                    confirm = true
                }
                .disabled(known.isEmpty && ignored.isEmpty)
            }
        }
        .alert("Снять все отметки?", isPresented: $confirm) {
            Button("Снять все", role: .destructive) {
                WordMarks.clear()
                withAnimation {
                    load()
                }
            }
            Button("Отмена", role: .cancel) {}
        } message: {
            Text("Слова «Знаю» и «Игнор» снова появятся в списках незнакомых слов.")
        }
        .onAppear(perform: load)
        .satoriBackdrop()
    }
}
