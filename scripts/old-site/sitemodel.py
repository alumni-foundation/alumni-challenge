"""Reads the cached HTML of the old site into one model: pages, posts, team, partners, menu, footer, buttons.
No network here. The writer (build_content.py) and the image downloader (download_images.py) both use it."""

import json
import os
import re
from datetime import datetime
from urllib.parse import urlparse

from bs4 import BeautifulSoup

import extract as ex

BASE = "https://alumnichallenge.foundation"
MENU_PAGES = [
    ("home", "/", "Home"),
    ("about-us", "/about-us/", "About Us"),
    ("about-us-2", "/about-us-2/", "Our Story"),
    ("the-team", "/the-team/", "The Team"),
    ("programs", "/programs/", "Programs"),
    ("partners", "/partners/", "Partners"),
    ("get-involved", "/get-involved/", "Get Involved"),
    ("blog", "/blog/", "Blog"),
    ("contact", "/contact/", "Contact"),
]
# The repeated "Donate / Volunteer / Newsletters / Get Involved" band and the latest-posts strip begin at this heading.
BAND_START = {"type": "heading", "level": 1, "text": "01"}


def read(cache: str, slug: str) -> BeautifulSoup:
    with open(os.path.join(cache, slug + ".html"), encoding="utf-8") as f:
        return BeautifulSoup(f.read(), "lxml")


def post_slug(url: str) -> str:
    return urlparse(url).path.strip("/").split("/")[-1]


def split_band(blocks: list[dict]) -> tuple[list[dict], list[dict]]:
    """(page's own blocks, the repeated band at the end). The band is only cut if it really starts at BAND_START."""
    for i, b in enumerate(blocks):
        if b == BAND_START:
            return blocks[:i], blocks[i:]
    return blocks, []


def parse_post(cache: str, fname: str, listing: dict[str, dict]) -> dict:
    soup = read(cache, fname)
    art = soup.find("article")
    url = ex.meta(soup, "og:url")
    canon = soup.find("link", rel="canonical")
    url = (canon or {}).get("href") if canon else url
    if not url:
        url = BASE + "/" + fname.replace("__", "/") + "/"
    title = ex.clean(art.find("h1").get_text(" ")) if art and art.find("h1") else ex.page_title(soup)
    date_text = ex.clean(art.select_one(".post-date .right").get_text()) if art and art.select_one(".post-date .right") else ""
    try:
        iso = datetime.strptime(date_text, "%B %d, %Y").date().isoformat()
    except ValueError:
        iso = ""
    author = ex.clean(art.select_one(".post-author").get_text()) if art and art.select_one(".post-author") else ""
    media = art.select_one(".post-media img") if art else None
    featured = ex.best_image_url(media) if media else None
    body = art.select_one(".post-body") if art else None
    blocks = ex.blocks(body) if body else []
    return {
        "slug": post_slug(url), "url": url, "title": title, "date": iso, "date_text": date_text, "author": author,
        "featured": featured, "excerpt": listing.get(url, {}).get("excerpt", ""), "blocks": blocks,
        "category": ex.clean(art.select_one(".ova-cat").get_text()) if art and art.select_one(".ova-cat") else "",
    }


def parse_listing(cache: str) -> list[dict]:
    soup = read(cache, "blog")
    rows = []
    for art in soup.find_all("article"):
        a = art.select_one(".post-title a")
        if not a:
            continue
        ex_p = art.select_one(".post-excerpt")
        rows.append({
            "url": a["href"], "title": ex.clean(a.get_text()), "excerpt": ex.clean(ex_p.get_text(" ")) if ex_p else "",
            "date_text": ex.clean(art.select_one(".post-date .right").get_text()) if art.select_one(".post-date .right") else "",
        })
    return rows


def parse_footer(soup: BeautifulSoup) -> dict:
    f = ex.footer_block(soup)
    lines = list(f.stripped_strings) if f else []
    links = [{"label": ex.clean(a.get_text(" ")), "raw_href": a.get("href")} for a in f.find_all("a")] if f else []
    return {"lines": lines, "links": links}


def parse_menu(soup: BeautifulSoup) -> list[dict]:
    """The desktop menu from the header: top-level labels in order, with sub-items under 'Who We Are'."""
    h = ex.header_block(soup)
    items = []
    # first <nav>-like list that contains 'Home'
    for ul in h.find_all("ul"):
        if ul.find("li") and "Home" in ul.get_text(" "):
            for li in ul.find_all("li", recursive=False):
                a = li.find("a")
                sub = li.find("ul")
                entry = {"label": ex.clean(a.get_text(" ")) if a else "", "href": ex.absolute(a.get("href")) if a and a.get("href") != "#" else None, "raw_href": a.get("href") if a else None}
                if sub:
                    entry["children"] = [{"label": ex.clean(x.get_text(" ")), "href": ex.absolute(x.get("href"))} for x in sub.find_all("a")]
                items.append(entry)
            break
    header_links = [{"label": ex.clean(a.get_text(" ")), "raw_href": a.get("href")} for a in h.find_all("a") if ex.clean(a.get_text(" ")) in ("Donate",) or (a.get("href") or "").startswith("tel:")]
    logo = h.find("img")
    return {"items": items, "header_links": header_links, "logo": ex.best_image_url(logo) if logo else None, "logo_alt": logo.get("alt") if logo else None}


def build(cache: str) -> dict:
    model: dict = {"pages": {}, "posts": [], "errors": []}
    home = read(cache, "home")
    model["footer"] = parse_footer(home)
    model["menu"] = parse_menu(home)
    home_blocks = None
    for slug, path, label in MENU_PAGES:
        if not os.path.exists(os.path.join(cache, slug + ".html")):
            model["errors"].append(f"{path}: page file missing")
            continue
        soup, pg = ex.page_content(open(os.path.join(cache, slug + ".html"), encoding="utf-8").read())
        url = BASE + path
        entry = {"slug": slug, "url": url, "menu_label": label, "title": ex.page_title(soup), "blocks": [], "band": [], "links": []}
        if slug == "blog":
            entry["listing"] = parse_listing(cache)
        elif pg is None:
            model["errors"].append(f"{path}: no page content block found")
        else:
            all_blocks = ex.blocks(pg)
            own, band = split_band(all_blocks)
            if slug == "home":
                own, band = all_blocks, []
                home_blocks = split_band(all_blocks)[1]
            entry["blocks"], entry["band"] = own, band
            entry["links"] = ex.all_links(pg)
            if slug == "home":
                entry["links_band_included"] = True
        model["pages"][slug] = entry
    home_band = home_blocks or []
    for slug, p in model["pages"].items():
        if slug != "home" and p["band"] and p["band"] != home_band:
            model["errors"].append(f"{slug}: the repeated call-to-action band differs from the home page's; kept in full")
            p["blocks"] += p["band"]
            p["band"] = []
    model["band"] = home_band
    model["listing"] = model["pages"]["blog"].get("listing", [])
    by_url = {r["url"]: r for r in model["listing"]}
    for fname in sorted(os.listdir(cache)):
        if re.match(r"\d{4}__\d{2}__\d{2}__", fname) and fname.endswith(".html"):
            model["posts"].append(parse_post(cache, fname[:-5], by_url))
    model["posts"].sort(key=lambda p: (p["date"], p["slug"]), reverse=True)
    # team: the founder from The Team page, the others from the /team/ index and their own pages
    team_soup = read(cache, "team")
    model["team_index"] = [
        {"name": ex.clean(a.get_text(" ")), "href": a["href"]}
        for a in team_soup.find_all("a", href=re.compile(r"/team/[^/]+/$")) if ex.clean(a.get_text(" "))
    ]
    model["team_pages"] = {}
    for fname in os.listdir(cache):
        if fname.startswith("team__"):
            s = read(cache, fname[:-5])
            h1 = s.find("h1")
            main_imgs = [i for i in s.find_all("img") if "Alumni_Logo01" not in (i.get("src") or "")]
            model["team_pages"][fname[6:-5]] = {
                "name": ex.clean(h1.get_text(" ")) if h1 else "",
                "images": [ex.best_image_url(i) for i in main_imgs if ex.best_image_url(i)],
            }
    return model


def image_urls(model: dict) -> list[str]:
    """Every content image URL, in the order first seen, without repeats."""
    seen: list[str] = []

    def add(u: str | None) -> None:
        if u and u not in seen and not ex.PLACEHOLDER.search(u) and "cropped-Alumnus-Favicon" not in u:
            seen.append(u)

    add(model["menu"].get("logo"))
    for p in model["pages"].values():
        for b in p["blocks"] + p["band"]:
            if b["type"] == "image":
                add(b["src"])
    for p in model["posts"]:
        add(p["featured"])
        for b in p["blocks"]:
            if b["type"] == "image":
                add(b["src"])
    for t in model["team_pages"].values():
        for u in t["images"]:
            add(u)
    return seen


def dump(model: dict, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(model, f, indent=1, ensure_ascii=False)


def local_names(model: dict) -> dict[str, str]:
    """A readable local file name for every image URL. Partner logos, team photos and blog pictures get
    names that say what they are; the rest keep the name the site gave them."""
    wanted: dict[str, str] = {}
    ext = lambda u: os.path.splitext(urlparse(u).path)[1].lower().replace(".jpeg", ".jpeg") or ".jpg"  # noqa: E731

    def stem(u: str) -> str:
        return os.path.splitext(os.path.basename(urlparse(ex.full_size(u)).path))[0]

    if model["menu"].get("logo"):
        wanted[model["menu"]["logo"]] = "alumni-logo" + ext(model["menu"]["logo"])
    for b in model["pages"]["partners"]["blocks"]:
        if b["type"] == "image" and "/2020/11/" in b["src"]:
            wanted[b["src"]] = "partner-" + re.sub(r"-0\d$", "", stem(b["src"]).lower()) + ext(b["src"])
    for slug, t in model["team_pages"].items():
        for u in t["images"]:
            wanted[u] = f"team-{slug}" + ext(u)
    for p in model["posts"]:
        if p["featured"]:
            wanted[p["featured"]] = f"blog-{p['slug'][:60].rstrip('-')}" + ext(p["featured"])
    for u in image_urls(model):
        if u in wanted:
            continue
        if "/elementor/thumbs/" in u:
            wanted[u] = "team-mark-macharia" + ext(u)  # the founder photo on The Team page
        else:
            wanted[u] = re.sub(r"[^A-Za-z0-9._-]", "-", os.path.basename(urlparse(ex.full_size(u)).path)).lower()
    seen: dict[str, str] = {}
    for u, name in list(wanted.items()):  # two different URLs must never share a file name
        if name in seen and seen[name] != u:
            base, e = os.path.splitext(name)
            wanted[u] = f"{base}-{re.search(r'/(\d{4}/\d{2})/', u).group(1).replace('/', '-') if re.search(r'/(\d{4}/\d{2})/', u) else 'alt'}{e}"
        seen[wanted[u]] = u
    return wanted
