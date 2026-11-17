"""Step 4: write the Markdown, JSON and INVENTORY files from the cached HTML and the image report. No network.

usage: python build_content.py <cache_dir> <out_dir>
The words are copied exactly as the old site has them. This script only arranges them.
"""

import json
import os
import re
import sys
from collections import Counter
from datetime import date

import extract as ex
import sitemodel as sm

HERE = os.path.dirname(os.path.abspath(__file__))


def q(value) -> str:
    """A YAML-safe scalar (JSON strings are valid YAML)."""
    return "null" if value is None else json.dumps(value, ensure_ascii=False)


def front_matter(fields: dict) -> str:
    return "---\n" + "".join(f"{k}: {q(v)}\n" for k, v in fields.items()) + "---\n\n"


class Writer:
    def __init__(self, cache: str, out: str):
        self.cache, self.out = cache, out
        self.model = sm.build(cache)
        self.names = sm.local_names(self.model)
        rp = os.path.join(cache, "image_report.json")
        self.report = json.load(open(rp, encoding="utf-8")) if os.path.exists(rp) else {}
        self.problems: list[str] = []

    # --- images ----------------------------------------------------------
    def local(self, url: str | None) -> str | None:
        if not url:
            return None
        r = self.report.get(url)
        return self.names.get(url) if r and r.get("ok") else None

    def img_md(self, b: dict, depth: str) -> str:
        loc = self.local(b["src"])
        target = f"{depth}images/{loc}" if loc else b["src"]
        alt = b.get("alt") or b.get("title") or ""
        md = f"![{alt}]({target})"
        if b.get("link"):
            md = f"[{md}]({b['link']})"
        return md + ("  <!-- background image -->" if b.get("background") else "") + ("" if loc else "  <!-- NOT DOWNLOADED -->")

    # --- markdown --------------------------------------------------------
    def render(self, blocks: list[dict], depth: str = "../") -> str:
        out: list[str] = []
        for b in blocks:
            t = b["type"]
            if t == "heading":
                out.append("#" * b["level"] + " " + b["text"])
            elif t == "paragraph":
                out.append(f"[{b['text']}]({b['link']})" if b.get("link") and b["link"] != "#" and "](" not in b["text"] else b["text"])
            elif t == "list":
                out.append("\n".join((f"{i}. " if b["ordered"] else "- ") + item for i, item in enumerate(b["items"], 1)))
            elif t == "image":
                out.append(self.img_md(b, depth))
            elif t in ("button", "link"):
                out.append(f"[{b.get('label') or b.get('text')}]({b['href']})")
            elif t == "form":
                fields = "\n".join(
                    f"- {f['type']}: {f.get('placeholder') or f.get('value') or f.get('name')}" for f in b["fields"]
                )
                out.append(f"**Form** (sends to {b['action']}):\n{fields}")
        return "\n\n".join(out) + "\n"

    def words(self, md: str) -> int:
        text = re.sub(r"!\[[^\]]*\]\([^)]*\)|<!--.*?-->", " ", md)
        text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
        return len(re.findall(r"[A-Za-z0-9’'`&-]+", text))

    def first_image(self, blocks: list[dict]) -> str | None:
        for b in blocks:
            if b["type"] == "image":
                return self.local(b["src"])
        return None

    # --- writers ---------------------------------------------------------
    def write(self, rel: str, text: str) -> None:
        path = os.path.join(self.out, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)

    def pages(self) -> list[dict]:
        rows = []
        for slug, p in self.model["pages"].items():
            if slug == "blog":
                body = "\n\n".join(
                    f"## [{r['title']}]({r['url']})\n\n{r['date_text']}\n\n{r['excerpt']}" for r in self.model["listing"]
                ) + "\n"
                blocks: list[dict] = []
            else:
                blocks = p["blocks"]
                body = self.render(blocks)
            fm = {"title": p["title"], "original_url": p["url"], "featured_image": self.first_image(blocks)}
            self.write(f"pages/{slug}.md", front_matter(fm) + body)
            rows.append({"kind": "page", "file": f"pages/{slug}.md", "url": p["url"], "words": self.words(body),
                         "images": sum(1 for b in blocks if b["type"] == "image"), "notes": []})
        # the three team member pages and the team archive page
        for slug, t in self.model["team_pages"].items():
            role = next((r["role"] for r in self.team_rows() if r["slug"] == slug), None)
            photo = self.local(t["images"][0]) if t["images"] else None
            body = f"# {t['name']}\n\n{role or ''}\n\n" + (f"![{t['name']}](../images/{photo})\n" if photo else "")
            self.write(f"pages/team-{slug}.md", front_matter({"title": t["name"], "original_url": f"{sm.BASE}/team/{slug}/", "featured_image": photo}) + body)
            rows.append({"kind": "page", "file": f"pages/team-{slug}.md", "url": f"{sm.BASE}/team/{slug}/", "words": self.words(body), "images": 1 if photo else 0,
                         "notes": ["only a name, a role and a photo on the old page; no biography"]})
        return rows

    def posts(self) -> list[dict]:
        rows = []
        for p in self.model["posts"]:
            body = self.render(p["blocks"])
            fm = {"title": p["title"], "original_url": p["url"], "date": p["date"], "author": p["author"] or None,
                  "featured_image": self.local(p["featured"]), "excerpt": p["excerpt"]}
            self.write(f"blog/{p['slug']}.md", front_matter(fm) + body)
            notes = []
            if not p["excerpt"]:
                notes.append("no excerpt found on the /blog/ list")
            if p["featured"] and not self.local(p["featured"]):
                notes.append("featured image did not download")
            rows.append({"kind": "post", "file": f"blog/{p['slug']}.md", "url": p["url"], "words": self.words(body),
                         "images": (1 if self.local(p["featured"]) else 0) + sum(1 for b in p["blocks"] if b["type"] == "image"), "notes": notes})
        return rows

    # --- team, partners --------------------------------------------------
    def team_rows(self) -> list[dict]:
        pg = self.model["pages"]["the-team"]["blocks"]
        rows = []
        # Mark: the founder's own section (name heading + role paragraph, bio = the paragraphs before them)
        paras = [b["text"] for b in pg if b["type"] == "paragraph"]
        name_i = next(i for i, b in enumerate(pg) if b["type"] == "heading" and b["level"] == 3 and b["text"] == "Mark Macharia")
        bio = [b["text"] for b in pg[:name_i] if b["type"] == "paragraph"]
        founder_img = next((b["src"] for b in pg if b["type"] == "image"), None)
        rows.append({"slug": "mark-macharia", "name": "Mark Macharia", "role": pg[name_i + 1]["text"], "photo_src": founder_img, "bio": "\n\n".join(bio), "url": f"{sm.BASE}/the-team/"})
        for i, b in enumerate(pg):
            if b["type"] == "link" and "/team/" in b["href"]:
                slug = b["href"].rstrip("/").split("/")[-1]
                role = pg[i + 1]["text"] if i + 1 < len(pg) and pg[i + 1]["type"] == "paragraph" else None
                imgs = self.model["team_pages"].get(slug, {}).get("images", [])
                rows.append({"slug": slug, "name": b["text"], "role": role, "photo_src": imgs[0] if imgs else None, "bio": None, "url": b["href"]})
        return rows

    def team_json(self) -> list[dict]:
        out = []
        for r in self.team_rows():
            photo = self.local(r["photo_src"])
            if r["photo_src"] and not photo:
                self.problems.append(f"team photo for {r['name']} did not download")
            out.append({"name": r["name"], "role": r["role"], "photo_file": photo, "bio": r["bio"], "source_url": r["url"]})
        return out

    def partners_json(self) -> list[dict]:
        names = json.load(open(os.path.join(HERE, "partner_names.json"), encoding="utf-8"))
        rows = []
        for b in self.model["pages"]["partners"]["blocks"]:
            if b["type"] != "image" or "/2020/11/" not in b["src"]:
                continue
            stem = re.sub(r"-0\d$", "", os.path.splitext(os.path.basename(ex.full_size(b["src"])))[0])
            known = names.get(stem.lower(), {})
            from_page = b.get("alt") or b.get("title")
            rows.append({
                "name": from_page or known.get("name") or stem,
                "logo_file": self.local(b["src"]),
                "website_url": b.get("link") or None,
                "name_confirmed": bool(from_page or b.get("link") or known.get("confirmed")),
                "name_source": "page alt text or link" if (from_page or b.get("link")) else known.get("source", "file name only"),
            })
        return rows

    # --- site.json -------------------------------------------------------
    def site_json(self) -> dict:
        m = self.model
        lines = m["footer"]["lines"]
        pages = m["pages"]

        def after(label: str, n: int = 1) -> list[str]:
            i = lines.index(label)
            return lines[i + 1:i + 1 + n]

        hours_lines = [l for l in lines if "|" in l]
        hours = [{"days": h.split("|")[0].strip(), "hours": h.split("|")[1].strip(), "as_written": h} for h in hours_lines]
        buttons = []
        for slug, p in pages.items():
            seen = set()
            for l in p["links"]:
                key = (l["label"], l["raw_href"])
                if key in seen:
                    continue
                seen.add(key)
                buttons.append({"page": slug, "label": l["label"], "target": l["href"], "original_href": l["raw_href"], "goes_nowhere": l["dead"], "is_open_close_heading": l["toggle"]})
        contact_blocks = pages["contact"]["blocks"]
        return {
            "site_name": "Alumni Challenge",
            "source": sm.BASE + "/",
            "collected_on": date.today().isoformat(),
            "logo_file": self.local(m["menu"]["logo"]),
            "menu": {
                "note": "Order as on the old site. 'Who We Are' has no page of its own (its link is '#'); it only opens the sub-menu.",
                "items": [
                    {"label": i["label"], "href": i.get("href"), **({"children": i["children"]} if "children" in i else {})}
                    for i in m["menu"]["items"]
                ],
                "header_extras": m["menu"]["header_links"],
            },
            "footer": {
                "address_lines": lines[lines.index("Our Address") + 1:lines.index("Opening Hours")],
                "opening_hours": hours,
                "phone": next((l["label"] for l in m["footer"]["links"] if l["raw_href"].startswith("tel:")), None),
                "phone_href": next((l["raw_href"] for l in m["footer"]["links"] if l["raw_href"].startswith("tel:")), None),
                "email": next((l["label"] for l in m["footer"]["links"] if l["raw_href"].startswith("mailto:")), None),
                "email_href_as_written": next((l["raw_href"] for l in m["footer"]["links"] if l["raw_href"].startswith("mailto:")), None),
                "newsletter_heading": "Newsletter",
                "newsletter_text": after("Newsletter")[0],
                "newsletter_form": "none found in the page HTML (text only)",
                "copyright": lines[-1],
                "all_lines_as_written": lines,
            },
            "contact_page": {
                "address": next((b["text"] for i, b in enumerate(contact_blocks) if b["type"] == "heading" and b["text"].startswith("Address") and contact_blocks[i + 1]["type"] == "paragraph" for b in [contact_blocks[i + 1]]), None),
                "phone": "0104 063 038",
                "email": "admin@alumnichallenge.foundation",
                "social_links": [l for l in pages["contact"]["links"] if re.search(r"twitter|facebook|youtube|linkedin|instagram", l["href"] or "")],
                "form": next((b for b in contact_blocks if b["type"] == "form"), None),
            },
            "hours_mentioned_elsewhere": [{"page": "home (call-to-action band)", "as_written": "Send us a message, or phone 0104 063 038 between 09:00 and 18:00 Mon-Sat."}],
            "shared_sections": {
                "note": "These blocks repeat at the bottom of the home, Partners and Get Involved pages. They are kept in home.md and left out of the other pages.",
                "call_to_action_band_and_latest_posts": m["band"],
            },
            "buttons_and_links": buttons,
        }

    # --- inventory -------------------------------------------------------
    def inventory(self, rows: list[dict], partners: list[dict], team: list[dict], site: dict) -> str:
        failures = json.load(open(os.path.join(self.cache, "failures.json"), encoding="utf-8")) if os.path.exists(os.path.join(self.cache, "failures.json")) else {}
        used = sum(1 for _ in open(os.path.join(self.cache, "requests.log"), encoding="utf-8"))
        n_img = sum(1 for r in self.report.values() if r.get("ok"))
        failed_img = [(u, r) for u, r in self.report.items() if not r.get("ok")]
        L = ["# Old site inventory", "",
             f"Collected from {sm.BASE}/ on {date.today().isoformat()} by `scripts/old-site/`. Nothing was rewritten: the wording is the site's own.", "",
             f"- HTTP requests made: **{used}** (pages, one stylesheet check, a media lookup, and images)",
             f"- Pages: {sum(1 for r in rows if r['kind']=='page')}, blog posts: {sum(1 for r in rows if r['kind']=='post')}, images downloaded: {n_img}, partner logos: {len(partners)}, team members: {len(team)}",
             f"- Pages that failed to load: {len(failures) or 'none'}", ""]
        L += ["## Pages and posts", "", "| File | Original URL | Words | Images | Notes |", "|---|---|---:|---:|---|"]
        for r in rows:
            L.append(f"| `{r['file']}` | {r['url']} | {r['words']} | {r['images']} | {'; '.join(r['notes'])} |")
        L += ["", "## Things that failed or look broken", ""]
        broken = []
        for u, f in failures.items():
            broken.append(f"- Page did not load: {u} ({f})")
        for u, r in failed_img:
            broken.append(f"- Image did not download: {u} ({r['tried'][-1] if r.get('tried') else ''})")
        broken += [f"- {p}" for p in self.problems + self.model["errors"]]
        dead = [b for b in site["buttons_and_links"] if b["goes_nowhere"]]
        for b in dead:
            broken.append(f"- Link \"{b['label']}\" on `{b['page']}` goes nowhere (link is `{b['original_href']}`)")
        for b in site["buttons_and_links"]:
            if b["target"] and re.match(r"https?://(www\.)?(twitter|facebook|youtube|linkedin)\.com/?$", b["target"]):
                broken.append(f"- Social link \"{b['label']}\" on `{b['page']}` points at the network's home page ({b['target']}), not at an Alumni Challenge profile")
        for p in self.model["posts"]:
            for m in re.finditer(r"\]\((https?://mailto:[^)]*)\)", self.render(p["blocks"])):
                broken.append(f"- `blog/{p['slug']}.md`: email link is written `{m.group(1)}` on the old site (not a working link)")
        broken.append(f"- Footer email link is written as `{site['footer']['email_href_as_written']}`, so clicking it would not open a new email to the address shown")
        for r in rows:
            if r["kind"] == "page" and r["words"] == 0:
                broken.append(f"- `{r['file']}` has no text")
        L += list(dict.fromkeys(broken)) or ["- none found"]
        L += ["", "## Partner logos", "", "| Name | Logo file | Website | Name confirmed | Where the name came from |", "|---|---|---|---|---|"]
        for p in partners:
            L.append(f"| {p['name']} | {p['logo_file']} | {p['website_url'] or '-'} | {p['name_confirmed']} | {p['name_source']} |")
        L += ["", "## Not collected", "",
              "- The page-title banner background behind each page's heading comes from the WordPress theme settings, not the page, so it is not in these files.",
              "- The blog category page (`/category/uncategorized/`), the author page (`/author/admin/`) and the events calendar link were not collected: they only list the same eight posts or are empty.",
              "- The Elementor `placeholder.png`, favicons and tracking images were skipped on purpose.",
              "- Blog posts have comments switched off on the old site.", ""]
        return "\n".join(L)


def main(cache: str, out: str) -> None:
    w = Writer(cache, out)
    rows = w.pages() + w.posts()
    partners = w.partners_json()
    team = w.team_json()
    site = w.site_json()
    for name, data in (("partners.json", partners), ("team.json", team), ("site.json", site)):
        w.write(name, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    notes = json.load(open(os.path.join(HERE, "contradictions.json"), encoding="utf-8")) if os.path.exists(os.path.join(HERE, "contradictions.json")) else []
    text = w.inventory(rows, partners, team, site)
    if notes:
        text += "\n## Contradictions found\n\n" + "\n".join(f"- {n}" for n in notes) + "\n"
    w.write("INVENTORY.md", text)
    print("written:", len(rows), "files;", len(partners), "partners;", len(team), "team")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
