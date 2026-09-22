"""Embed data/feed.json into the app as web/feed.js and mirror web/ into the Android assets."""
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
feed = json.loads((ROOT / "data" / "feed.json").read_text())
js = "window.GONKA_FEED = " + json.dumps(feed, separators=(",", ":"), ensure_ascii=False) + ";\n"
(ROOT / "web" / "feed.js").write_text(js)
assets = ROOT / "android" / "app" / "src" / "main" / "assets" / "www"
assets.mkdir(parents=True, exist_ok=True)
for f in (ROOT / "web").iterdir():
    if f.is_file():
        shutil.copy(f, assets / f.name)
print("bundled feed generated_at", feed["generated_at"], "->", assets)
