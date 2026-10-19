# v2.25: the queue sends a package from 10 notes, «Отправить все» is the button of the queue.
# - A package needs the share sheet (iOS gives no way to hand a file to AnkiMobile without it, and AnkiMobile has no
#   URL command for an import): it pays from 10 notes on; fewer go one by one, as before 2.18.
# - The button at the top of the queue is «Отправить все» («Отправить готовые» while some still wait); «Выбрать»
#   moved into the menu «•••» next to it. The words say «Отправить», not «Добавить».
import pathlib


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")

s = once(s, '''        guard sending.count > 1, !packing else {''', '''        // the share sheet pays from 10 notes: fewer go one by one
        guard sending.count >= 10, !packing else {''', "package from 10")

s = once(s, '''        if !queue.sending.isEmpty {
            return "Добавляю… " + String(queue.sending.count)
        }
        let all = queue.entries.filter { video == nil || $0.video == video }.count
        return readyCount < all ? "Добавить готовые" : "Добавить все"''', '''        if !queue.sending.isEmpty {
            return "Отправляю… " + String(queue.sending.count)
        }
        let all = queue.entries.filter { video == nil || $0.video == video }.count
        return readyCount < all ? "Отправить готовые" : "Отправить все"''', "send words")

s = once(s, '''                ToolbarItem(placement: .primaryAction) {
                    if !choosing && queue.sending.isEmpty && queue.entries.contains(where: { video == nil || $0.video == video }) {
                        Button("Выбрать") { choosing = true }
                    }
                }
                ToolbarItem(placement: .confirmationAction) {
                    if choosing {
                        Button("Добавить (" + String(chosen.count) + ")") {
                            queue.send(chosen)
                            choosing = false
                            chosen = []
                        }
                        .disabled(chosen.isEmpty || !queue.sending.isEmpty || queue.packing)
                    } else {
                        Button(sendTitle) {
                            queue.sendAll(video: video)
                        }
                        .disabled(!queue.sending.isEmpty || queue.packing || !queue.packed.isEmpty || readyCount == 0)
                    }
                }''', '''                // «Отправить все» is the button of the queue, «Выбрать» waits in «•••» next to it
                ToolbarItemGroup(placement: .primaryAction) {
                    if choosing {
                        Button("Отправить (" + String(chosen.count) + ")") {
                            queue.send(chosen)
                            choosing = false
                            chosen = []
                        }
                        .disabled(chosen.isEmpty || !queue.sending.isEmpty || queue.packing)
                    } else {
                        Button(sendTitle) {
                            queue.sendAll(video: video)
                        }
                        .disabled(!queue.sending.isEmpty || queue.packing || !queue.packed.isEmpty || readyCount == 0)
                        if queue.sending.isEmpty && queue.entries.contains(where: { video == nil || $0.video == video }) {
                            Menu {
                                Button {
                                    choosing = true
                                } label: {
                                    Label("Выбрать", systemImage: "checkmark.circle")
                                }
                            } label: {
                                Label("Ещё", systemImage: "ellipsis")
                            }
                        }
                    }
                }''', "toolbar")
hv.write_text(s, encoding="utf-8")
print("v2.25 queue send applied")
