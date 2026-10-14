# v1.70: the dictionary panel of landscape (both players) slides in and out, and it reaches the bottom edge: the 6 pt
# padding and the rounded bottom corners left a strip of video under it. Deleting a YouTube video asks first and
# animates, like the other videos.
import pathlib


def times(text, old, new, count, label):
    assert text.count(old) == count, "pattern not found " + str(count) + " times: " + label
    return text.replace(old, new)


hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")

# ---------- the panel: docked at the bottom edge ----------
s = times(s, """struct WordLookupSheet: View {
    let text: String
""", """struct WordLookupSheet: View {
    let text: String
    /// the landscape panel at the bottom of the screen: square bottom corners and no gap under it
    var docked = false
""", 1, "docked flag")
s = times(s, """                    .clipShape(RoundedRectangle(cornerRadius: 22, style: .continuous))
                    .padding(.horizontal, 8)
                    .padding(.top, 10)
                    .padding(.bottom, 6)
""", """                    .clipShape(RoundedRectangle(cornerRadius: 22, style: .continuous))
                    // docked: the corners at the bottom edge are filled with the colour of the page
                    .background(alignment: .bottom) {
                        if docked {
                            Color(red: 28 / 255, green: 28 / 255, blue: 30 / 255)
                                .frame(height: 30)
                        }
                    }
                    .padding(.horizontal, 8)
                    .padding(.top, 10)
                    .padding(.bottom, docked ? 0 : 6)
""", 1, "docked look")
s = times(s, """                WordLookupSheet(text: lookupWord)
                    .overlay(alignment: .top) {""", """                WordLookupSheet(text: lookupWord, docked: true)
                    .overlay(alignment: .top) {""", 2, "panels docked")

# ---------- the panel slides in and out ----------
s = times(s, """            if showLookup && verticalSize == .compact {
                landscapeLookup
                    .ignoresSafeArea(edges: .bottom)
            }
        }
        .toolbar(.hidden, for: .tabBar)
""", """            if showLookup && verticalSize == .compact {
                landscapeLookup
                    .ignoresSafeArea(edges: .bottom)
                    .transition(.move(edge: .bottom))
            }
        }
        .animation(.easeOut(duration: 0.25), value: showLookup)
        .toolbar(.hidden, for: .tabBar)
""", 1, "file player panel animation")
s = times(s, """            if landscape && showLookup {
                landscapeLookup
            }
        }
        .preferredColorScheme(.dark)
""", """            if landscape && showLookup {
                landscapeLookup
                    .ignoresSafeArea(edges: .bottom)
                    .transition(.move(edge: .bottom))
            }
        }
        .animation(.easeOut(duration: 0.25), value: showLookup)
        .preferredColorScheme(.dark)
""", 1, "youtube panel animation")

# ---------- deleting a YouTube video: a question and the animation ----------
s = times(s, """struct YouTubeRecentSection: View {
    /// loaded by the list when it appears
    @Binding var items: [YouTubeItem]
""", """struct YouTubeRecentSection: View {
    /// loaded by the list when it appears
    @Binding var items: [YouTubeItem]
    @State private var pendingDelete: YouTubeItem? = nil
""", 1, "pending delete")
s = times(s, """                        .swipeActions(edge: .trailing, allowsFullSwipe: true) {
                            Button(role: .destructive) {
                                YouTubeHistory.remove(item.id)
                                items = YouTubeHistory.load()
                            } label: {
                                Label("Удалить", systemImage: "trash")
                            }
                        }
""", """                        .swipeActions(edge: .trailing, allowsFullSwipe: false) {
                            Button(role: .destructive) {
                                pendingDelete = item
                            } label: {
                                Label("Удалить", systemImage: "trash")
                            }
                        }
                        .contextMenu {
                            Button(role: .destructive) {
                                pendingDelete = item
                            } label: {
                                Label("Удалить", systemImage: "trash")
                            }
                        }
""", 1, "youtube swipe")
s = times(s, """                } header: {
                    Text("YouTube")
                }
            }
        }
    }
}
""", """                } header: {
                    Text("YouTube")
                }
            }
        }
        // the same question and animation as for the other videos
        .alert(pendingDelete.map { "Удалить «" + ($0.title.isEmpty ? $0.id : $0.title) + "»?" } ?? "Удалить?",
               isPresented: Binding(get: { pendingDelete != nil }, set: { if !$0 { pendingDelete = nil } })) {
            Button("Удалить", role: .destructive) {
                if let item = pendingDelete {
                    withAnimation(.easeInOut(duration: 0.35)) {
                        YouTubeHistory.remove(item.id)
                        items = YouTubeHistory.load()
                    }
                }
                pendingDelete = nil
            }
            Button("Отмена", role: .cancel) {
                pendingDelete = nil
            }
        } message: {
            Text("Видео пропадёт из списка вместе с сохранённой позицией.")
        }
    }
}
""", 1, "youtube delete alert")
hv.write_text(s, encoding="utf-8")
print("v1.70 lookup panel applied")
