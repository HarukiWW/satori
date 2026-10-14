# v1.75: reading. A volume is a row of its own, so a folded volume is a card like the rest of the list; its title
# has the whole width (the number of chapters, the grade and the download button go under it or to the side, the
# author's wide spaces are folded), so fewer titles break into two lines. The jump goes to the volume row.
import pathlib


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


def between(text, start, end, new, label):
    assert text.count(start) == 1, "start not found exactly once: " + label
    a = text.index(start)
    b = text.index(end, a)
    return text[:a] + new + text[b:]


hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")

s = once(s, '''                ForEach(allVolumes) { volume in
                    Section {
                        if expanded.contains(volume.id) {
''', '''                ForEach(allVolumes) { volume in
                    Section {
                        volumeRow(volume, saved: saved)
                            .id(volume.id)
                        if expanded.contains(volume.id) {
''', "volume row in section")
s = once(s, '''                    } header: {
                        volumeHeader(volume, saved: saved)
                            .id(volume.id)
                    }
''', '''                    }
''', "no volume header")
s = once(s, '''        expanded.insert(volume.id)
        guard let first = volume.episodes.first?.number else { return }
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.15) {
            withAnimation {
                proxy.scrollTo(first, anchor: .top)
            }
        }
''', '''        expanded.insert(volume.id)
        let target = volume.id
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.15) {
            withAnimation {
                proxy.scrollTo(target, anchor: .top)
            }
        }
''', "jump to the volume row")
s = between(s, "    private func volumeHeader(_ volume: Volume, saved: Set<Int>) -> some View {\n",
            "    private func episodeRow(_ episode: NovelEpisode, saved: Bool, read: Bool) -> some View {", '''    /// A volume: a tap folds or opens it; the title has the whole width, the numbers go under it.
    private func volumeRow(_ volume: Volume, saved: Set<Int>) -> some View {
        let numbers = volume.episodes.map { $0.number }
        let missing = numbers.filter { !saved.contains($0) }
        let grade = analyzer.brief(ncode, numbers)
        let open = expanded.contains(volume.id)
        let title: String = volume.title.isEmpty ? "Главы" : NovelDetailView.cleanTitle(volume.title)
        let have = numbers.count - missing.count
        let count: String = have > 0 && !missing.isEmpty
            ? String(numbers.count) + " гл., скачано " + String(have)
            : String(numbers.count) + " гл."
        return HStack(alignment: .center, spacing: 10) {
            Image(systemName: "chevron.right")
                .font(.footnote.weight(.semibold))
                .foregroundColor(.secondary)
                .rotationEffect(.degrees(open ? 90 : 0))
            VStack(alignment: .leading, spacing: 4) {
                Text(title)
                    .font(.subheadline.weight(.semibold))
                    .lineLimit(2)
                    .minimumScaleFactor(0.85)
                HStack(spacing: 8) {
                    Text(count)
                        .font(.caption)
                        .foregroundColor(.secondary)
                    if let grade {
                        AnalysisBadges(known: grade.known, difficulty: grade.difficulty)
                    }
                }
            }
            Spacer(minLength: 6)
            if !missing.isEmpty {
                Button {
                    store.download(ncode, missing)
                } label: {
                    Image(systemName: "arrow.down.circle")
                        .font(.title3)
                }
                .buttonStyle(.borderless)
            }
        }
        .padding(.vertical, 2)
        .contentShape(Rectangle())
        .onTapGesture {
            toggle(volume.id)
        }
    }

''', "volume row")
s = once(s, "Том сворачивается нажатием на его название; свайп по главе → «Слова».",
         "Том сворачивается нажатием на него, ↓ скачивает его главы; свайп по главе → «Слова».", "novel footer")
hv.write_text(s, encoding="utf-8")
print("v1.75 reader applied")
