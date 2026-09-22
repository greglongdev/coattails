"""Embed data/feed.json into the app as web/feed.js and mirror web/ into the Android assets."""
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
feed = json.loads((ROOT / "data" / "feed.json").read_text())
js = "window.GONKA_FEED = " + json.dumps(feed, separators=(",", ":"), ensure_ascii=False) + ";\n"
(ROOT / "web" / "feed.js").write_text(js)
# Named explicitly so a scratch file in web/ can never end up inside the APK.
APP_FILES = ["index.html", "styles.css", "logos.js", "format.js", "feed.js", "app.js"]

assets = ROOT / "android" / "app" / "src" / "main" / "assets" / "www"
assets.mkdir(parents=True, exist_ok=True)
for name in APP_FILES:
    shutil.copy(ROOT / "web" / name, assets / name)
for stale in assets.iterdir():
    if stale.is_file() and stale.name not in APP_FILES:
        stale.unlink()
print("bundled feed generated_at", feed["generated_at"], "->", assets)
