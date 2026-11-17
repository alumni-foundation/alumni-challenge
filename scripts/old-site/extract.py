"""Step 2: turn the cached HTML into content blocks. Pure functions, no network.

The old site is WordPress + Elementor. Each page has three Elementor blocks: the header template, the page
content, and the footer template. Only the page content (and, separately, the footer) is read here. The text is
kept exactly as written; nothing is summarised or rewritten.
"""

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup, NavigableString, Tag

BASE = "https://alumnichallenge.foundation/"
HEADINGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
SKIP_TAGS = {"script", "style", "noscript", "svg", "template", "head", "iframe", "select", "option", "textarea"}
BLOCK_TAGS = HEADINGS | {"p", "ul", "ol", "li", "div", "section", "table", "figure", "blockquote", "article", "form"}
SIZE_SUFFIX = re.compile(r"-\d+x\d+(?=\.[A-Za-z0-9]+$)")
PLACEHOLDER = re.compile(r"(placeholder\.png|/wp-content/plugins/|gravatar|pixel|spacer\.gif|1x1)", re.I)


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def absolute(url: str | None) -> str | None:
    if not url or url.startswith(("data:", "javascript:", "#")):
        return None
    return urljoin(BASE, url.strip())


def full_size(url: str) -> str:
    """The WordPress thumbnail name (-300x130) is dropped to point at the original upload."""
    return SIZE_SUFFIX.sub("", url)


def best_image_url(img: Tag) -> str | None:
    """The biggest file this <img> mentions: srcset entries first (widest), then lazy-load attributes, then src."""
    cands: list[tuple[int, str]] = []
    for attr in ("srcset", "data-lazy-srcset", "data-srcset"):
        for part in (img.get(attr) or "").split(","):
            bits = part.strip().split()
            if bits:
                w = int(bits[1][:-1]) if len(bits) > 1 and bits[1].endswith("w") and bits[1][:-1].isdigit() else 0
                cands.append((w, bits[0]))
    for attr in ("data-lazy-src", "data-src", "src"):
        if img.get(attr):
            cands.append((0, img[attr]))
    cands = [(w, u) for w, u in cands if absolute(u)]
    if not cands:
        return None
    return absolute(max(cands, key=lambda c: c[0])[1])


def wrap(text: str, before: str, after: str) -> str:
    """Put markdown marks around the words but outside any spaces, so the spacing of the original is unchanged."""
    lead = text[: len(text) - len(text.lstrip())]
    trail = text[len(text.rstrip()):]
    return f"{lead}{before}{text.strip()}{after}{trail}"


def inline(node: Tag) -> str:
    """Inline markdown: **bold**, *italic*, [links](url). The words themselves are untouched."""
    out: list[str] = []
    for child in node.children:
        if isinstance(child, NavigableString):
            out.append(str(child))
        elif isinstance(child, Tag):
            if child.name in SKIP_TAGS:
                continue
            if child.name == "br":
                out.append("\n")
                continue
            text = inline(child)
            if not clean(text):
                out.append(text)
                continue
            if child.name in ("strong", "b"):
                out.append(wrap(text, "**", "**"))
            elif child.name in ("em", "i") and not child.get("class"):
                out.append(wrap(text, "*", "*"))
            elif child.name == "a" and absolute(child.get("href")):
                out.append(wrap(text, "[", f"]({absolute(child['href'])})"))
            else:
                out.append(text)
    return "".join(out)


def is_leaf(tag: Tag) -> bool:
    return not any(isinstance(c, Tag) and (c.name in BLOCK_TAGS) for c in tag.descendants)


def is_button(tag: Tag) -> bool:
    classes = " ".join(tag.get("class") or [])
    return tag.name == "a" and bool(re.search(r"(elementor-button|btn|button)", classes))


def blocks(root: Tag) -> list[dict]:
    """Walk the content in reading order and return blocks: heading, paragraph, list, image, button."""
    result: list[dict] = []

    def add_image(img: Tag) -> None:
        url = best_image_url(img)
        if url and not PLACEHOLDER.search(url):
            result.append({"type": "image", "src": url, "alt": clean(img.get("alt") or ""), "title": clean(img.get("title") or "")})

    def visit(node: Tag, link: str | None = None) -> None:
        for el in node.children:
            if not isinstance(el, Tag) or el.name in SKIP_TAGS:
                continue
            classes = " ".join(el.get("class") or [])
            bg = re.search(r"background-image:\s*url\(['\"]?(https?://[^'\")]+)", el.get("style") or "")
            if bg and not PLACEHOLDER.search(bg.group(1)):
                result.append({"type": "image", "src": bg.group(1), "alt": "", "title": "", "background": True})
            if "elementor-widget-spacer" in classes or "elementor-hidden" in classes:
                continue
            if el.name in HEADINGS:
                text = clean(inline(el))
                if text:
                    result.append({"type": "heading", "level": int(el.name[1]), "text": text})
            elif el.name == "p":
                text = inline(el).strip()
                text = re.sub(r"[ \t]+", " ", text.replace("\xa0", " "))
                text = re.sub(r" *\n *", "\n", text).strip()
                if text:
                    block = {"type": "paragraph", "text": text}
                    if link and link != "#":
                        block["link"] = link
                    result.append(block)
                for img in el.find_all("img"):
                    add_image(img)
            elif el.name in ("ul", "ol"):
                for styled in el.find_all(style=True):  # slider slides keep their pictures in inline styles
                    m = re.search(r"background-image:\s*url\(['\"]?(https?://[^'\")]+)", styled["style"])
                    if m and not PLACEHOLDER.search(m.group(1)) and not any(b.get("src") == m.group(1) for b in result):
                        result.append({"type": "image", "src": m.group(1), "alt": "", "title": "", "background": True})
                items = [clean(inline(li)) for li in el.find_all("li", recursive=False)]
                items = [i for i in items if i]
                if items:
                    result.append({"type": "list", "ordered": el.name == "ol", "items": items})
            elif el.name == "img":
                add_image(el)
                # a linked image (partner logo): remember where it points
                if link and result and result[-1]["type"] == "image":
                    result[-1]["link"] = link
            elif el.name == "a" and is_button(el):
                label = clean(el.get_text(" "))
                if label:
                    result.append({"type": "button", "label": label, "href": absolute(el.get("href"))})
            elif el.name == "a" and el.find("img") and not clean(el.get_text(" ")):
                visit(el, absolute(el.get("href")))
            elif el.name == "a" and not is_leaf(el):
                # a link wrapped around a whole box (icon + title): the words inside carry the link
                visit(el, absolute(el.get("href")) or "#")
            elif el.name == "form":
                fields = []
                for f in el.find_all(["input", "textarea"]):
                    if f.get("type") in ("hidden", None) and f.name != "textarea":
                        continue
                    fields.append({"name": f.get("name"), "type": f.get("type") or f.name, "placeholder": f.get("placeholder"), "value": f.get("value") if f.get("type") == "submit" else None})
                result.append({"type": "form", "action": absolute(el.get("action")), "fields": fields})
            elif el.name in BLOCK_TAGS and is_leaf(el) and clean(el.get_text(" ")):
                # a div or span holding only text (icon-box titles, counters, captions)
                text = clean(inline(el))
                counter = el if el.get("data-to-value") else el.find(attrs={"data-to-value": True})
                if counter is not None:  # an animated counter: the page shows 0 until it scrolls into view
                    pre = el.select_one(".elementor-counter-number-prefix")
                    suf = el.select_one(".elementor-counter-number-suffix")
                    text = f"{clean(pre.get_text()) if pre else ''}{counter['data-to-value']}{clean(suf.get_text()) if suf else ''}"
                if text:
                    block = {"type": "paragraph", "text": text}
                    if link:
                        block["link"] = link
                    result.append(block)
            else:
                if el.name == "a" and absolute(el.get("href")) and clean(el.get_text(" ")) and is_leaf(el):
                    result.append({"type": "link", "text": clean(el.get_text(" ")), "href": absolute(el.get("href"))})
                    continue
                visit(el, link)

    visit(root)
    return result


def elementor_block(soup: BeautifulSoup, kind: str) -> Tag | None:
    for b in soup.find_all(attrs={"data-elementor-type": True}):
        if b["data-elementor-type"] == kind:
            return b
    return None


def page_content(html: str) -> tuple[BeautifulSoup, Tag | None]:
    soup = BeautifulSoup(html, "lxml")
    return soup, elementor_block(soup, "wp-page")


def footer_block(soup: BeautifulSoup) -> Tag | None:
    posts = [b for b in soup.find_all(attrs={"data-elementor-type": "wp-post"})]
    return posts[-1] if len(posts) > 1 else None


def header_block(soup: BeautifulSoup) -> Tag | None:
    posts = [b for b in soup.find_all(attrs={"data-elementor-type": "wp-post"})]
    return posts[0] if posts else None


def meta(soup: BeautifulSoup, prop: str) -> str | None:
    m = soup.find("meta", attrs={"property": prop}) or soup.find("meta", attrs={"name": prop})
    return m.get("content") if m and m.get("content") else None


def page_title(soup: BeautifulSoup) -> str:
    h1 = soup.find("h1")
    og = meta(soup, "og:title")
    return clean((og or (soup.title.get_text() if soup.title else "")).split(" – ")[0].split(" � ")[0].split(" | ")[0]) or clean(h1.get_text() if h1 else "")


def all_links(root: Tag) -> list[dict]:
    """Every link with visible words in the page content, in reading order: label and where it points.
    '#' and empty targets are kept and flagged, because a button that goes nowhere is worth knowing about."""
    out = []
    for a in root.find_all("a"):
        label = clean(a.get_text(" "))
        if not label:
            img = a.find("img")
            label = clean((img.get("alt") if img else "") or "")
        if not label:
            continue
        raw = (a.get("href") or "").strip()
        toggle = "elementor-toggle-title" in " ".join(a.get("class") or [])  # an open/close heading, not a button
        out.append({"label": label, "href": absolute(raw), "raw_href": raw, "toggle": toggle,
                    "dead": (raw in ("", "#") or raw.startswith("javascript:")) and not toggle})
    return out
