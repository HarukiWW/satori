# v2.27: the dictionary of the player opens at once, closes by a tap anywhere at the top.
# - The dictionary of the player (landscape) was a new page every time: the panel was taken away when it closed, so
#   every open loaded the dictionary again (up to a second). Now the panel stays (below the screen) while the video is
#   open and is made with the player, so its page has loaded before the first word; a new line goes into the open
#   page (satoriLookup), which only searches.
# - A tap anywhere along the top closes it (the whole width); the thin edges around the panel still do nothing.
# - The double tap on the black bar opens the dictionary on the first highlighted word of the line (the colours of
#   the subtitles: the JLPT levels and the frequency range of the settings), the line start when none is.
import pathlib


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


def first(text, old, new, label):
    assert text.count(old) == 2, "pattern not found twice (the video player, then YouTube): " + label
    return text.replace(old, new, 1)


hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")

s = once(s, '''    /// the last long press that queued a word: the tap that ends it does not close the dictionary
    @State private var heldAt = Date.distantPast
''', '''    /// the last long press that queued a word: the tap that ends it does not close the dictionary
    @State private var heldAt = Date.distantPast
    /// the word of the line the dictionary opens on (nil: the start)
    @State private var lookupCharAt: Int? = nil
''', "char at state")
s = once(s, '''                            if rect.minX >= 20, location.x < rect.minX, !line.isEmpty {
                                openLookup()
                            } else {''', '''                            if rect.minX >= 20, location.x < rect.minX, !line.isEmpty {
                                openLookupOnHighlighted()
                            } else {''', "double tap highlighted")
s = once(s, '''                                // only a tap at the top in the middle closes it: the sides catch the fingers that
                                // hold the phone
                                if location.y < geo.size.height * 0.4,
                                   abs(location.x - geo.size.width / 2) < geo.size.width * 0.35 {
                                    closeLookupByTap()
                                }''', '''                                // only a tap at the top closes it: lower, the sides catch the fingers that hold it
                                if location.y < geo.size.height * 0.4 {
                                    closeLookupByTap()
                                }''', "portrait close")
s = once(s, '''    /// A tap in the middle of the gap or a swipe down on the handle closes it, a long press there queues the chosen
    /// word; the sides of the gap and the edges of the panel do nothing (the fingers that hold the phone rest there).
    private var landscapeLookup: some View {
        GeometryReader { geo in
            VStack(spacing: 0) {
                HStack(spacing: 0) {
                    Color.clear
                        .frame(width: geo.size.width * 0.15)
                        .contentShape(Rectangle())
                        .onTapGesture {}
                    Color.clear
                        .contentShape(Rectangle())
                        .onTapGesture { closeLookupByTap() }
                        .onLongPressGesture(minimumDuration: 0.5) { addChosenWord() }
                    Color.clear
                        .frame(width: geo.size.width * 0.15)
                        .contentShape(Rectangle())
                        .onTapGesture {}
                }
                .frame(height: geo.size.height * 0.22)
                WordLookupSheet(text: lookupWord, docked: true)''', '''    /// A tap on the gap (the whole width) or a swipe down on the handle closes it, a long press there queues the
    /// chosen word; the edges of the panel do nothing (the fingers that hold the phone rest there).
    private var landscapeLookup: some View {
        GeometryReader { geo in
            VStack(spacing: 0) {
                Color.clear
                    .frame(height: geo.size.height * 0.22)
                    .contentShape(Rectangle())
                    .onTapGesture { closeLookupByTap() }
                    .onLongPressGesture(minimumDuration: 0.5) { addChosenWord() }
                WordLookupSheet(text: lookupWord, docked: true, charAt: lookupCharAt)''', "landscape gap")
s = once(s, '''        .sheet(isPresented: Binding(get: { showLookup && verticalSize != .compact },
                                    set: { showLookup = $0 })) {
            WordLookupSheet(text: lookupWord)''', '''        .sheet(isPresented: Binding(get: { showLookup && verticalSize != .compact },
                                    set: { showLookup = $0 })) {
            WordLookupSheet(text: lookupWord, charAt: lookupCharAt)''', "portrait sheet")
# the YouTube player has the same panel code after it: only the first (the video player) changes
s = first(s, '''            withAnimation(.easeIn(duration: 0.22)) {
                panelLowered = true
            }
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.25) {
                if !showLookup {
                    panelMounted = false
                }
            }''', '''            // it stays below the screen: its page is ready for the next word
            withAnimation(.easeIn(duration: 0.22)) {
                panelLowered = true
            }''', "panel stays")
s = once(s, '''        .onAppear {
            // the highlight of the first lines already knows the words in the mining queue
            yomikiriQueuedWordsHook = {
                MiningQueue.queuedWords()
            }
        }''', '''        .onAppear {
            // the highlight of the first lines already knows the words in the mining queue
            yomikiriQueuedWordsHook = {
                MiningQueue.queuedWords()
            }
            // the dictionary is made with the player, below the screen: its page loads before the first word
            panelMounted = true
        }''', "panel ahead")
s = once(s, '''    private func openLookup() {
        if !showLookup {
            lookupWasPlaying = coordinator.playerLayer?.player.isPlaying ?? playing
        }
        lookupWord = line
        coordinator.playerLayer?.pause()''', '''    /// The dictionary on the first highlighted word of the line on screen (the colours of the subtitles), else on its
    /// start.
    private func openLookupOnHighlighted() {
        let clean = SubtitleTokenCache.clean(line)
        let tokens = SubtitleTokenCache.shared.tokens(clean)
        let colors = HighlightData.colors(for: tokens)
        openLookup(text: clean, charAt: tokens.first { colors[$0.id] != nil }?.start)
    }

    private func openLookup(text: String? = nil, charAt: Int? = nil) {
        if !showLookup {
            lookupWasPlaying = coordinator.playerLayer?.player.isPlaying ?? playing
        }
        lookupWord = text ?? line
        lookupCharAt = charAt
        // the page of the panel is open already: it only searches
        LookupWeb.show(lookupWord, charAt ?? 0)
        coordinator.playerLayer?.pause()''', "open lookup")

# --- the dictionary page that is open already gets the new line
s = once(s, '''                    .onLoadComplete { web in
                        LookupWeb.current = web
                    }''', '''                    .onLoadComplete { web in
                        LookupWeb.loaded(web)
                    }''', "loaded")
s = once(s, '''        .presentationDetents([.medium, .large])
        .presentationDragIndicator(.visible)
        .opacity(sheetOpacity)
        .modifier(SheetTransparency())''', '''        .presentationDetents([.medium, .large])
        .presentationDragIndicator(.visible)
        .opacity(sheetOpacity)
        .modifier(SheetTransparency())
        .onAppear {
            LookupWeb.show(text, charAt ?? 0)
        }''', "show on appear")
s = once(s, '''/// The dictionary of the lookup opened last (in the player: the one on screen), for the ⊕ of a long press.
enum LookupWeb {
    static weak var current: WKWebView?
}''', '''/// The dictionary of the lookup opened last (in the player: the one on screen), for the ⊕ of a long press and for a
/// new line in a page that is open already (v2.27).
enum LookupWeb {
    static weak var current: WKWebView?
    /// the line the dictionary shows; a page that loads later gets it then
    private static var shown: (text: String, charAt: Int) = ("", 0)

    static func show(_ text: String, _ charAt: Int) {
        shown = (text, charAt)
        guard let web = current, let data = try? JSONSerialization.data(withJSONObject: [text, charAt] as [Any]),
              let args = String(data: data, encoding: .utf8) else { return }
        web.evaluateJavaScript("window.satoriLookup && window.satoriLookup.apply(null, " + args + ")") { _, _ in }
    }

    static func loaded(_ web: WKWebView) {
        current = web
        show(shown.text, shown.charAt)
    }
}''', "lookup web")
hv.write_text(s, encoding="utf-8")

# --- the web: a new line without loading the page again
tk = pathlib.Path("src/main/src/components/dictionary/Tokenize.svelte")
t = tk.read_text(encoding="utf-8")
t = once(t, '''  /** the character the first search opens on */
  export let initialCharAt = 0;
''', '''  /** the character the first search opens on */
  export let initialCharAt = 0;
  /** changed by a new lookup in a page that stays open (the player): the word to open on is chosen again */
  export let lookupStamp = 0;
''', "stamp prop")
t = once(t, '''  $: void search(searchText, selectedCharAt);''', '''  // a new line or a new lookup: back to the word it opens on
  $: {
    void searchText;
    void lookupStamp;
    selectedCharAt = initialCharAt;
  }

  $: void search(searchText, selectedCharAt);''', "reset selection")
tk.write_text(t, encoding="utf-8")

av = pathlib.Path("src/main/src/iosapp/DictionaryView.svelte")
v = av.read_text(encoding="utf-8")
v = once(v, '''  async function openGrammar() {''', '''  // the player keeps this page open below the screen: a new line comes without loading it again
  let lookupStamp = 0;
  (window as unknown as { satoriLookup?: (text: string, charAt: number) => void }).satoriLookup = (text, charAt) => {
    searchText = text;
    initialCharAt = charAt;
    lookupStamp += 1;
    document.querySelector(".search > .entries")?.scrollTo(0, 0);
  };

  async function openGrammar() {''', "satori lookup")
v = once(v, '''    <Tokenize
      bind:searchText
      {initialCharAt}''', '''    <Tokenize
      bind:searchText
      {initialCharAt}
      {lookupStamp}''', "stamp pass")
av.write_text(v, encoding="utf-8")
print("v2.27 player lookup applied")
