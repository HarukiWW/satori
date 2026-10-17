# v2.02: fixes of the grammar decks.
# - The level test opened on a black screen: its body was a Group with nothing in it before the questions are made,
#   so its background and onAppear had no view to attach to and the questions were never made. A ZStack with a clear
#   layer is always there.
# - The four answers are the same capsules: a long word («Хорошо», «Трудно») wrapped onto two lines and turned its
#   button round. One line, scaled down when needed, on a capsule of its own.
# - New cards per day are set per deck (0 turns the new cards of a deck off): studying N3 no longer leaves N2 and N1
#   offering new cards every day. The old common value stays the default of a deck without its own.
import pathlib


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")

# ---------- the test: always a view ----------
s = once(s, '''    var body: some View {
        Group {
            if let percent {
                result(percent)
''', '''    var body: some View {
        ZStack {
            // a view is there before the questions are made: the background and onAppear need one
            Color.clear
            if let percent {
                result(percent)
''', "test body")

# ---------- the answers: the same capsules ----------
s = once(s, '''        } label: {
            VStack(spacing: 3) {
                Text(interval)
                    .font(.caption2)
                    .foregroundColor(.secondary)
                Text(title)
                    .font(.subheadline.weight(.semibold))
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 6)
        }
        .buttonStyle(.bordered)
        .tint(color)
    }
''', '''        } label: {
            VStack(spacing: 2) {
                Text(interval)
                    .font(.caption2)
                    .foregroundColor(.secondary)
                Text(title)
                    .font(.subheadline.weight(.semibold))
                    .foregroundColor(color)
            }
            .lineLimit(1)
            .minimumScaleFactor(0.7)
            .padding(.horizontal, 4)
            .frame(maxWidth: .infinity, minHeight: 50)
            .background(Capsule().fill(color.opacity(0.22)))
            .contentShape(Capsule())
        }
        .buttonStyle(.plain)
    }
''', "grade capsules")

# ---------- new cards per deck ----------
s = once(s, '''    var newPerDay = 10
    /// the study day (it starts at 4:00) and the new cards begun on it, per level
''', '''    var newPerDay = 10
    /// new cards a day of each level (the key is the level); a level without one takes newPerDay
    var newPerLevel: [String: Int]? = nil
    /// the study day (it starts at 4:00) and the new cards begun on it, per level
''', "save per level")
s = once(s, '''    func newLeft(_ level: Int, now: Date = Date()) -> Int {
        let begun = save.day == GrammarStore.studyDay(now) ? (save.newToday[String(level)] ?? 0) : 0
        return max(0, save.newPerDay - begun)
    }
''', '''    func newPerDay(level: Int) -> Int {
        save.newPerLevel?[String(level)] ?? save.newPerDay
    }

    func newLeft(_ level: Int, now: Date = Date()) -> Int {
        let begun = save.day == GrammarStore.studyDay(now) ? (save.newToday[String(level)] ?? 0) : 0
        return max(0, newPerDay(level: level) - begun)
    }
''', "new left per level")
s = once(s, '''    func setNewPerDay(_ value: Int) {
        save.newPerDay = min(max(value, 0), 100)
        persist()
    }
''', '''    func setNewPerDay(_ value: Int, level: Int) {
        var map = save.newPerLevel ?? [:]
        map[String(level)] = min(max(value, 0), 100)
        save.newPerLevel = map
        persist()
    }
''', "set per level")
s = once(s, '''                Section {
                    Stepper(value: Binding(get: { store.save.newPerDay }, set: { store.setNewPerDay($0) }),
                            in: 0 ... 50, step: 5) {
                        Text("Новых в день: " + String(store.save.newPerDay))
                    }
                    Toggle("Озвучивать предложение сразу", isOn: $autoPlay)
                } header: {
                    Text("Настройки")
                } footer: {
                    Text("Лимит новых — на каждую колоду. День начинается в 4:00. Голос — из настроек озвучки словаря.")
                }
''', '''                Section {
                    Toggle("Озвучивать предложение сразу", isOn: $autoPlay)
                } header: {
                    Text("Настройки")
                } footer: {
                    Text("Сколько новых в день — в каждой колоде отдельно. День начинается в 4:00. Голос — из настроек "
                        + "озвучки словаря.")
                }
''', "home settings")
s = once(s, '''        var note = "единиц: " + String(GrammarLibrary.level(level).count)
        if let test = store.save.tests[String(level)] {
            note += " · тест " + String(test) + "%"
        }
''', '''        var note = "единиц: " + String(GrammarLibrary.level(level).count)
        if let test = store.save.tests[String(level)] {
            note += " · тест " + String(test) + "%"
        }
        if store.newPerDay(level: level) == 0 {
            note += " · новые выкл."
        }
''', "deck row note")
s = once(s, '''            } footer: {
                Text(testNote())
            }
''', '''            } footer: {
                Text(testNote())
            }
            Section {
                Stepper(value: Binding(get: { store.newPerDay(level: level) },
                                       set: { store.setNewPerDay($0, level: level) }),
                        in: 0 ... 50, step: 5) {
                    Text(newLabel())
                }
            } footer: {
                Text("0 — колода не даёт новых карточек, только повторяет начатые: удобно для уровней, которые вы пока не учите.")
            }
''', "deck settings")
s = once(s, '''    private func testNote() -> String {
''', '''    private func newLabel() -> String {
        let count = store.newPerDay(level: level)
        return count == 0 ? "Новых в день: нет" : "Новых в день: " + String(count)
    }

    private func testNote() -> String {
''', "deck new label")
s = once(s, '''                Text("Новые карточки — завтра: " + String(store.save.newPerDay) + " в день.")
                    .foregroundColor(.secondary)
''', '''                Text(newNote())
                    .foregroundColor(.secondary)
''', "done new text")
s = once(s, '''    private var done: some View {
''', '''    private func newNote() -> String {
        let count = store.newPerDay(level: level)
        if count == 0 {
            return "Новые карточки в этой колоде выключены (настройка колоды)."
        }
        return "Новые карточки — завтра: " + String(count) + " в день."
    }

    private var done: some View {
''', "done new note")

hv.write_text(s, encoding="utf-8")
print("v2.02 grammar fixes applied")
