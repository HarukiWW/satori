# v1.52: crash when closing a video. The lock screen buttons (v1.46) held the player strongly; removing them on close
# released the player inside MPRemoteCommandCenter, so its whole teardown ran there. They hold it weakly now, the player
# is released the usual way. Two more marks in the crash trail around the closing steps.
import pathlib

hv = pathlib.Path("src/safari/iOS (App)/HelpView.swift")
s = hv.read_text(encoding="utf-8")


def once(text, old, new, label):
    assert text.count(old) == 1, "pattern not found exactly once: " + label
    return text.replace(old, new)


for command in ("playCommand", "pauseCommand", "togglePlayPauseCommand", "skipForwardCommand", "skipBackwardCommand"):
    s = once(s, f"        commands.{command}.addTarget {{ _ in\n",
             f"        commands.{command}.addTarget {{ [weak layer] _ in\n", command)
s = once(s, "        commands.changePlaybackPositionCommand.addTarget { event in\n",
         "        commands.changePlaybackPositionCommand.addTarget { [weak layer] event in\n", "changePlaybackPosition")

s = once(s, '            CrashTrail.mark("плеер: закрытие")\n            flushWatching()\n            endNowPlaying()\n',
         '            CrashTrail.mark("плеер: закрытие")\n            flushWatching()\n'
         '            CrashTrail.mark("плеер: статистика просмотра сохранена")\n            endNowPlaying()\n', "mark after flush")
s = once(s, "    private func endNowPlaying() {\n        removeRemoteCommands()\n",
         "    private func endNowPlaying() {\n        removeRemoteCommands()\n"
         "        CrashTrail.mark(\"плеер: кнопки медиа-меню сняты\")\n", "mark after commands")

hv.write_text(s, encoding="utf-8")
print("v1.52 fixes applied")
