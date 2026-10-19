# v2.26: mining in the player with the fingers that hold the phone.
# - A double tap on the black bar at the left of the picture (where the video does not reach) opens the dictionary
#   on the line on screen, as a tap on the subtitle does; elsewhere a double tap still repeats the line.
# - With the dictionary open, a long press above it (the gap at the top in landscape, the picture in portrait) adds
#   the chosen word to the queue, as its ⊕: the entry with the chosen meaning, else the first one; a warning
#   vibration when there is nothing to add.
# - The dictionary closes only by a tap at the top in the middle (or the swipe down on its handle). The sides of the
#   gap and the thin edges around the panel do nothing: a finger holding the phone there went through them to the
#   player, and any tap of the player closed the dictionary.
import pathlib


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")

s = once(s, '''    @State private var ankiReturning = false
    /// playing when a word was tapped: closing the lookup goes on only then
    @State private var lookupWasPlaying = false
''', '''    @State private var ankiReturning = false
    /// playing when a word was tapped: closing the lookup goes on only then
    @State private var lookupWasPlaying = false
    /// the last long press that queued a word: the tap that ends it does not close the dictionary
    @State private var heldAt = Date.distantPast
''', "held state")

s = once(s, '''                    KSVideoPlayer(coordinator: coordinator, url: url, options: options)
                        .frame(width: geo.size.width, height: geo.size.height)
                    // a tap on the picture shows or hides the controls
                    Color.black.opacity(0.001)
                        .contentShape(Rectangle())
                        .onTapGesture(count: 2) { replayLine() }
                        .onTapGesture {
                            if showLookup {
                                showLookup = false
                            } else {
                                toggleControls()
                            }
                        }''', '''                    KSVideoPlayer(coordinator: coordinator, url: url, options: options)
                        .frame(width: geo.size.width, height: geo.size.height)
                    // a tap on the picture shows or hides the controls
                    Color.black.opacity(0.001)
                        .contentShape(Rectangle())
                        .onTapGesture(count: 2, coordinateSpace: .local) { location in
                            // the black bar at the left of the picture: the dictionary on the line on screen
                            if rect.minX >= 20, location.x < rect.minX, !line.isEmpty {
                                openLookup()
                            } else {
                                replayLine()
                            }
                        }
                        .onTapGesture(coordinateSpace: .local) { location in
                            if showLookup {
                                // only a tap at the top in the middle closes it: the sides catch the fingers that
                                // hold the phone
                                if location.y < geo.size.height * 0.4,
                                   abs(location.x - geo.size.width / 2) < geo.size.width * 0.35 {
                                    closeLookupByTap()
                                }
                            } else {
                                toggleControls()
                            }
                        }
                        .onLongPressGesture(minimumDuration: 0.5) {
                            if showLookup {
                                addChosenWord()
                            }
                        }''', "player gestures")

s = once(s, '''    /// Landscape: the lookup window sits at the bottom (the free gap is on top, as in portrait), nothing is dimmed.
    /// A tap on the gap or a swipe down on the handle closes it.
    private var landscapeLookup: some View {
        GeometryReader { geo in
            VStack(spacing: 0) {
                Color.clear
                    .frame(height: geo.size.height * 0.22)
                    .contentShape(Rectangle())
                    .onTapGesture { showLookup = false }
                WordLookupSheet(text: lookupWord, docked: true)''', '''    /// Landscape: the lookup window sits at the bottom (the free gap is on top, as in portrait), nothing is dimmed.
    /// A tap in the middle of the gap or a swipe down on the handle closes it, a long press there queues the chosen
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
                WordLookupSheet(text: lookupWord, docked: true)
                    .background(Color.black.opacity(0.001).onTapGesture {})''', "landscape panel")

s = once(s, '''        lookupWord = line
        coordinator.playerLayer?.pause()
        playing = false
        showLookup = true
        prepareMining()
    }
''', '''        lookupWord = line
        coordinator.playerLayer?.pause()
        playing = false
        showLookup = true
        prepareMining()
    }

    /// A tap at the top closes the dictionary, but not the one that ends a long press.
    private func closeLookupByTap() {
        guard Date().timeIntervalSince(heldAt) > 0.6 else { return }
        showLookup = false
    }

    /// The ⊕ of the chosen word in the dictionary (the entry with the chosen meaning, else the first one).
    private func addChosenWord() {
        heldAt = Date()
        guard showLookup, let web = LookupWeb.current else { return }
        web.evaluateJavaScript("window.satoriAddChosen ? window.satoriAddChosen() : false") { result, _ in
            // added, the queue vibrates itself
            if (result as? Bool) != true {
                UINotificationFeedbackGenerator().notificationOccurred(.warning)
            }
        }
    }
''', "player add chosen")

# --- the dictionary panel knows its web view
s = once(s, '''                YomikiriWebView(url: url)
                    .scrollable(false)
                    .overscroll(false)
                    .edgeToEdge(true)
                    .ignoresSafeArea(.keyboard)
                    .clipShape(RoundedRectangle(cornerRadius: 22, style: .continuous))''', '''                YomikiriWebView(url: url)
                    .scrollable(false)
                    .overscroll(false)
                    .edgeToEdge(true)
                    .onLoadComplete { web in
                        LookupWeb.current = web
                    }
                    .ignoresSafeArea(.keyboard)
                    .clipShape(RoundedRectangle(cornerRadius: 22, style: .continuous))''', "lookup web")
s = s.rstrip("\n") + "\n" + '''
// MARK: - Satori v2.26: mining in the player by a long press

/// The dictionary of the lookup opened last (in the player: the one on screen), for the ⊕ of a long press.
enum LookupWeb {
    static weak var current: WKWebView?
}
'''
hv.write_text(s, encoding="utf-8")

# --- the web: the ⊕ of the chosen word, for the player
dv = pathlib.Path("src/main/src/components/dictionary/DicEntryView.svelte")
d = dv.read_text(encoding="utf-8")
d = once(d, '''      {:else if $ankiEnabledConfig && entry.type === "word"}
        <IconedButton
          size="2rem"
          highlight={$selectedMeaning?.entry === entry}''', '''      {:else if $ankiEnabledConfig && entry.type === "word"}
        <!-- found by the long press of the player (satoriAddChosen) -->
        <span class="add-note" style="display: contents">
        <IconedButton
          size="2rem"
          highlight={$selectedMeaning?.entry === entry}''', "add note open")
d = once(d, '''          <IconAddCircleOutline />
        </IconedButton>
      {/if}''', '''          <IconAddCircleOutline />
        </IconedButton>
        </span>
      {/if}''', "add note close")
dv.write_text(d, encoding="utf-8")

av = pathlib.Path("src/main/src/iosapp/DictionaryView.svelte")
v = av.read_text(encoding="utf-8")
v = once(v, '''  async function openGrammar() {''', '''  // the long press of the player: the ⊕ of the entry with the chosen meaning, else of the first entry (an entry
  // already added has no ⊕: nothing is added then)
  (window as unknown as { satoriAddChosen?: () => boolean }).satoriAddChosen = () => {
    const entries = document.getElementById("yomikiri-entries");
    const chosen =
      entries?.querySelector<HTMLButtonElement>(".add-note button.highlight") ??
      entries?.firstElementChild?.querySelector<HTMLButtonElement>(".add-note button") ??
      null;
    if (chosen === null || chosen.disabled) return false;
    chosen.click();
    return true;
  };

  async function openGrammar() {''', "add chosen")
av.write_text(v, encoding="utf-8")
print("v2.26 player mining applied")
