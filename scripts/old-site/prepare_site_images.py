"""Copies the images the public pages use from web/content/old-site/images/ into web/public/images/site/,
shrinks anything wider than 2000px, compresses, and writes a size manifest (web/content/old-site/site-images.json)
so next/image knows each picture's width and height.

usage: python prepare_site_images.py        (run from anywhere; paths are relative to the repo)
Partner logos whose name is not confirmed (name_confirmed: false) are left out.
"""

import json
import os
import re

from PIL import Image

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC = os.path.join(ROOT, "web", "content", "old-site")
OUT = os.path.join(ROOT, "web", "public", "images", "site")
MAX_W = 2000

PAGES = {  # collected file -> public name
    "alumni_aboutii.jpg": "about.jpg",
    "mission.jpg": "about-mission.jpg",
    "alumni_about-scaled.jpg": "our-story.jpg",
    "kenya-high-school-alumni.jpg": "programs-golf.jpg",
    "mentorship.jpg": "programs-mentorship.jpg",
    "polikophotography-206.jpg": "get-involved.jpg",
    "home.jpg": "who-we-are.jpg",
}


def save(src: str, dest: str, manifest: dict) -> None:
    im = Image.open(src)
    if im.width > MAX_W:
        im = im.resize((MAX_W, round(im.height * MAX_W / im.width)), Image.LANCZOS)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if dest.endswith(".png"):
        im.save(dest, optimize=True)
    else:
        if im.mode != "RGB":
            bg = Image.new("RGB", im.size, "white")
            bg.paste(im, mask=im.getchannel("A") if "A" in im.getbands() else None)
            im = bg
        im.save(dest, quality=82, optimize=True, progressive=True)
    manifest["/" + os.path.relpath(dest, os.path.join(ROOT, "web", "public")).replace(os.sep, "/")] = [im.width, im.height]


def main() -> None:
    manifest: dict = {}
    for src, name in PAGES.items():
        save(os.path.join(SRC, "images", src), os.path.join(OUT, name), manifest)
    for f in os.listdir(os.path.join(SRC, "images")):
        if f.startswith("team-"):
            save(os.path.join(SRC, "images", f), os.path.join(OUT, "team", os.path.splitext(f)[0][5:] + ".jpg"), manifest)
        elif f.startswith("blog-"):
            continue
    for post in os.listdir(os.path.join(SRC, "blog")):
        text = open(os.path.join(SRC, "blog", post), encoding="utf-8").read()
        m = re.search(r'^featured_image: "([^"]+)"', text, re.M)
        if m:
            save(os.path.join(SRC, "images", m.group(1)), os.path.join(OUT, "blog", post[:-3] + ".jpg"), manifest)
    skipped = []
    for p in json.load(open(os.path.join(SRC, "partners.json"), encoding="utf-8")):
        if not p["name_confirmed"]:
            skipped.append(p["name"])
            continue
        save(os.path.join(SRC, "images", p["logo_file"]), os.path.join(OUT, "partners", p["logo_file"].replace("partner-", "")), manifest)
    json.dump(dict(sorted(manifest.items())), open(os.path.join(SRC, "site-images.json"), "w", encoding="utf-8"), indent=1)
    print(len(manifest), "images written; left out (name not confirmed):", skipped)


if __name__ == "__main__":
    main()
