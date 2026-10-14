# v1.68: rebranding to Satori, step 1: the name under the icon, the app icon (ci/assets/satori-icon.png, 1024 px,
# no transparency), the name and the icon of the Safari extension, the window titles and the "About" page.
# Bundle IDs and the App Group stay the same, so the app installs over the old one and keeps its data.
# Runs on the macOS runner (sips makes the 128 px extension icon).
import pathlib
import shutil
import subprocess


def times(text, old, new, count, label):
    assert text.count(old) == count, "pattern not found " + str(count) + " times: " + label
    return text.replace(old, new)


def patch(path, edits):
    p = pathlib.Path(path)
    s = p.read_text(encoding="utf-8")
    for old, new, count, label in edits:
        s = times(s, old, new, count, label)
    p.write_text(s, encoding="utf-8")


icon = pathlib.Path(__file__).resolve().parent.parent / "assets" / "satori-icon.png"

# the app icon: the single 1024 px image of the asset catalog
iconset = pathlib.Path("src/safari/Shared (App)/Shared.xcassets/AppIcon.appiconset")
assert (iconset / "11 1024px.png").exists(), "app icon file not found"
shutil.copyfile(icon, iconset / "11 1024px.png")

# the icon of the Safari extension
ext_icon = pathlib.Path("src/main/src/assets/static/images/icon128.png")
assert ext_icon.exists(), "extension icon not found"
shutil.copyfile(icon, ext_icon)
subprocess.run(["sips", "-z", "128", "128", str(ext_icon)], check=True, stdout=subprocess.DEVNULL)

# the names shown by iOS (the app name itself is set again when the .ipa is packaged)
patch("src/safari/Yomikiri.xcodeproj/project.pbxproj", [
    ('INFOPLIST_KEY_CFBundleDisplayName = "Yomikiri Extension";', "INFOPLIST_KEY_CFBundleDisplayName = Satori;", 4,
     "extension name"),
    ('INFOPLIST_KEY_CFBundleDisplayName = "Yomikiri Action";', "INFOPLIST_KEY_CFBundleDisplayName = Satori;", 2,
     "share sheet action name"),
    ("INFOPLIST_KEY_CFBundleDisplayName = Yomikiri;", "INFOPLIST_KEY_CFBundleDisplayName = Satori;", 4, "app name"),
])
patch("src/main/src/manifest.json.ejs", [('  "name": "Yomikiri",\n', '  "name": "Satori",\n', 1, "manifest name")])

# the web pages
patch("src/main/src/iosapp/dictionary.html", [("<title>Yomikiri</title>", "<title>Satori</title>", 1, "dictionary title")])
for page in ["src/main/src/iosapp/options.html", "src/main/src/extension/options/index.html"]:
    patch(page, [("<title>Yomikiri Configuration</title>", "<title>Satori — настройки</title>", 1, "options title")])
patch("src/main/src/iosapp/optionsAnkiTemplate.html", [
    ("<title>Yomikiri Configuration: Anki Template</title>", "<title>Satori — шаблон Anki</title>", 1, "template title")])
patch("src/main/src/extension/x-callback/index.html", [("Yomikiri: Opening last tab...", "Satori: возвращаюсь…", 1,
                                                        "x-callback text")])
patch("src/main/src/components/options/groups/GroupAbout.svelte", [
    ('<OptionBase title="О Yomikiri">', '<OptionBase title="О Satori">', 1, "about title"),
    ("    Yomikiri — проект с открытым исходным кодом. Код можно посмотреть на GitHub.\n",
     "    Satori — проект с открытым исходным кодом на основе Yomikiri (BlueGreenMagick). Код можно посмотреть на\n"
     "    GitHub.\n", 1, "about text"),
])
print("v1.68 Satori applied")
