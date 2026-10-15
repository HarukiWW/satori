# v1.80: reading.
# - Smart furigana: the reading over the kanji of the words the analysis does not count as known; a button in the
#   reader turns it off and on. A paragraph with furigana keeps the room for it over every word, so lines stay even.
# - The search button searches the chapter (it opened the dictionary): the paragraphs with the text, a tap goes to
#   the paragraph and marks it for a moment.
# The code is v180-reader.swift.
import pathlib


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


def between(text, start, end, new, label):
    assert text.count(start) == 1, "start not found exactly once: " + label
    a = text.index(start)
    b = text.index(end, a)
    return text[:a] + new + text[b:]


here = pathlib.Path(__file__).resolve().parent
hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")

# ---------- furigana in a paragraph ----------
s = once(s, '''    @State private var tokens: [LookupToken] = []
    @State private var colors: [Int: Color] = [:]
    @State private var ready = false

    private var baseColor: Color {
        secondary ? .secondary : .primary
    }
''', '''    @State private var tokens: [LookupToken] = []
    @State private var colors: [Int: Color] = [:]
    @State private var rubies: [Int: ReaderFurigana.Ruby] = [:]
    @State private var ready = false
    @AppStorage("ykReaderFurigana") private var furigana = true

    private var baseColor: Color {
        secondary ? .secondary : .primary
    }

    /// A word; with furigana, the reading over the kanji of an unknown word (every word of the paragraph keeps the
    /// room for it, so the lines stay even).
    @ViewBuilder
    private func word(_ token: LookupToken) -> some View {
        let color = colors[token.id] ?? baseColor
        if !furigana || rubies.isEmpty {
            Text(token.text)
                .font(.system(size: fontSize))
                .foregroundColor(color)
        } else if let ruby = rubies[token.id] {
            HStack(alignment: .bottom, spacing: 0) {
                Text(ruby.head)
                VStack(spacing: 0) {
                    Text(ruby.reading)
                        .font(.system(size: fontSize * 0.5))
                        .foregroundColor(.secondary)
                        .lineLimit(1)
                        .fixedSize()
                    Text(ruby.core)
                }
                Text(ruby.tail)
            }
            .font(.system(size: fontSize))
            .foregroundColor(color)
        } else {
            VStack(spacing: 0) {
                Text(" ")
                    .font(.system(size: fontSize * 0.5))
                Text(token.text)
                    .font(.system(size: fontSize))
                    .foregroundColor(color)
            }
        }
    }
''', "paragraph furigana")
s = once(s, '''                    ForEach(tokens) { token in
                        Text(token.text)
                            .font(.system(size: fontSize))
                            .foregroundColor(colors[token.id] ?? baseColor)
                            .padding(.vertical, fontSize * 0.17)
                            .contentShape(Rectangle())
                            .onTapGesture {
                                onTap(ReaderLookup.make(tokens, at: token.id))
                            }
                    }
''', '''                    ForEach(tokens) { token in
                        word(token)
                            .padding(.vertical, fontSize * 0.17)
                            .contentShape(Rectangle())
                            .onTapGesture {
                                onTap(ReaderLookup.make(tokens, at: token.id))
                            }
                    }
''', "paragraph words")
s = once(s, '''        tokens = result
        colors = result.isEmpty ? [:] : HighlightData.colors(for: result)
    }
''', '''        tokens = result
        colors = result.isEmpty ? [:] : HighlightData.colors(for: result)
        rubies = ReaderFurigana.shared.rubies(for: result)
    }
''', "paragraph rubies")

# ---------- the reader: furigana button, search in the chapter ----------
s = once(s, '''    @State private var showSearch = false
    @State private var topParagraph = 0
''', '''    @State private var showSearch = false
    @AppStorage("ykReaderFurigana") private var furigana = true
    /// a paragraph found by the search: the list goes to it and marks it for a moment
    @State private var jumpTo: Int? = nil
    @State private var marked: Int? = nil
    @State private var topParagraph = 0
''', "reader state")
s = once(s, '''                        ForEach(Array(text.body.enumerated()), id: \\.offset) { index, paragraph in
                            ReaderParagraph(text: paragraph, fontSize: fontSize, onTap: open)
                                .id(index)
''', '''                        ForEach(Array(text.body.enumerated()), id: \\.offset) { index, paragraph in
                            ReaderParagraph(text: paragraph, fontSize: fontSize, onTap: open)
                                .background(marked == index ? Color.accentColor.opacity(0.18) : Color.clear)
                                .id(index)
''', "marked paragraph")
s = once(s, '''            .task(id: number) {
                await load(proxy)
            }
        }
''', '''            .task(id: number) {
                await load(proxy)
            }
            .onChange(of: jumpTo) { value in
                guard let value else { return }
                jumpTo = nil
                lastActivity = CACurrentMediaTime()
                withAnimation {
                    proxy.scrollTo(value, anchor: .top)
                }
                marked = value
                DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
                    if marked == value {
                        withAnimation {
                            marked = nil
                        }
                    }
                }
            }
        }
''', "jump to the paragraph")
s = once(s, '''                Button {
                    lookup = nil
                    showSearch = true
                } label: {
                    Image(systemName: "magnifyingglass")
                }
                Button {
                    fontSize = max(13, fontSize - 1)
''', '''                Button {
                    lookup = nil
                    showSearch = true
                } label: {
                    Image(systemName: "magnifyingglass")
                }
                Button {
                    furigana.toggle()
                } label: {
                    Image(systemName: furigana ? "textformat.superscript" : "textformat")
                }
                Button {
                    fontSize = max(13, fontSize - 1)
''', "furigana button")
s = once(s, '''        .sheet(isPresented: $showSearch) {
            ReaderSearchSheet()
        }
''', '''        .sheet(isPresented: $showSearch) {
            ChapterSearchSheet(paragraphs: text?.body ?? []) { index in
                jumpTo = index
            }
        }
''', "chapter search")
s = between(s, "/// A word typed while reading: the dictionary of the app, the Japanese keyboard opens at once.\n",
            "/// The saved novels.\n", "", "dictionary search out")
s = once(s, '''            reachedEnd = false
            text = loaded
''', '''            reachedEnd = false
            await ReaderFurigana.shared.prepare()
            text = loaded
''', "furigana ready before the text")
s = s.rstrip("\n") + "\n" + (here / "v180-reader.swift").read_text(encoding="utf-8")
hv.write_text(s, encoding="utf-8")
print("v1.80 reader applied")
