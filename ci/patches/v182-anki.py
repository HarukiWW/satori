# v1.82: the meaning in the note. The glosses of a meaning go as a list with dots, one per line (not after commas),
# and every example sentence is a framed block: the sentence with the word in green, the translation under it.
# Inline styles: the note looks this way whatever the card's CSS is.
import pathlib


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


p = pathlib.Path("src/main/src/lib/anki/ankiBuilder.ts")
t = p.read_text(encoding="utf-8")
t = once(t, '''          const itemsLine =
            escapeHTML(items.join(", ")) +
            (withExamples && format !== "line" ? examplesHtml(sense) : "");
''', '''          const itemsLine =
            format === "line"
              ? escapeHTML(items.join(", "))
              : glossesHtml(items) + (withExamples ? examplesHtml(sense) : "");
''', "full meaning")
t = once(t, '''    line += escapeHTML(items.join(", ")) + (withExamples ? examplesHtml(sense) : "");
''', '''    // "one line" (the Kaishi look): the glosses after commas and no examples, also for a chosen meaning
    line +=
      opts.full_format === "line"
        ? escapeHTML(items.join(", "))
        : glossesHtml(items) + (withExamples ? examplesHtml(sense) : "");
''', "single meaning")
start = t.index("/** The example sentences of a sense with their translations;")
end = t.index("/** The examples of the chosen meaning, or of the first meaning that has some. */")
t = t[:start] + r'''/** The glosses of a meaning, one per line after a dot. */
function glossesHtml(items: string[]): string {
  return (
    '<div class="yomi-glosses" style="text-align: left;">' +
    items.map((item) => "<div>• " + escapeHTML(item) + "</div>").join("") +
    "</div>"
  );
}

/** The example sentences of a sense, each in a frame: the sentence with the word (marked \ue000 … \ue001) in
 * green, the translation under it. */
function examplesHtml(sense: unknown, _lead = ""): string {
  const examples =
    (sense as { examples?: { japanese: string; translation: string }[] }).examples ?? [];
  return examples
    .map((example) => {
      const japanese = escapeHTML(example.japanese)
        .replace(/\ue000/g, '<span style="color: #6abf69;">')
        .replace(/\ue001/g, "</span>");
      return (
        '<div class="yomi-example" style="text-align: left; margin: 8px 0 4px; padding: 8px 12px; ' +
        'border-left: 3px solid #555; border-radius: 8px; background: rgba(255, 255, 255, 0.06);">' +
        '<div style="font-size: 1.15em; line-height: 1.5;">' +
        japanese +
        "</div>" +
        '<div style="font-size: 0.9em; opacity: 0.75;">' +
        escapeHTML(example.translation) +
        "</div></div>"
      );
    })
    .join("");
}

''' + t[end:]
p.write_text(t, encoding="utf-8")
print("v1.82 anki applied")
