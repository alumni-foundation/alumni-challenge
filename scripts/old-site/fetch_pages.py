"""Step 1: download the HTML of every public page and blog post into a cache folder (not committed).

usage: python -I fetch_pages.py <cache_dir>
Starts from the menu pages, follows blog pagination, and adds every blog post and any other internal page
the menu or the footer links to. Failures are written to <cache_dir>/failures.json.
"""

import json
import os
import re
import sys
from urllib.parse import urldefrag, urljoin, urlparse

from bs4 import BeautifulSoup

from client import Client

BASE = "https://alumnichallenge.foundation"
SEED = ["/", "/about-us/", "/about-us-2/", "/the-team/", "/programs/", "/partners/", "/get-involved/", "/blog/", "/contact/"]
SKIP = re.compile(r"(wp-content|wp-includes|wp-json|wp-admin|xmlrpc|/feed|\?ical|\?replytocom|#)")


def slug_for(url: str) -> str:
    path = urlparse(url).path.strip("/")
    return path.replace("/", "__") or "home"


def internal_links(html: str, page_url: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    found = []
    for a in soup.find_all("a", href=True):
        href = urldefrag(urljoin(page_url, a["href"]))[0]
        p = urlparse(href)
        if p.netloc.replace("www.", "") != "alumnichallenge.foundation" or SKIP.search(href):
            continue
        if re.search(r"\.(jpg|jpeg|png|gif|webp|svg|pdf|zip)$", p.path, re.I):
            continue
        if "?" in href and "paged" not in href:
            continue
        found.append(href if href.endswith("/") or "?" in href else href + "/")
    return found


def main(cache: str) -> None:
    os.makedirs(cache, exist_ok=True)
    client = Client(os.path.join(cache, "requests.log"))
    queue = [BASE + p for p in SEED]
    seen: set[str] = set()
    failures: dict[str, str] = {}
    while queue:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        cached = os.path.join(cache, slug_for(url) + ".html")
        if os.path.exists(cached):  # already downloaded on an earlier run: no new request
            status, body, err = 200, open(cached, "rb").read(), ""
        else:
            status, body, _, err = client.get(url)
        if status != 200:
            failures[url] = err or f"HTTP {status}"
            print("FAILED", url, failures[url])
            continue
        with open(os.path.join(cache, slug_for(url) + ".html"), "wb") as f:
            f.write(body)
        print("ok", url, len(body))
        html = body.decode("utf-8", "replace")
        for link in internal_links(html, url):
            if link in seen or link in queue:
                continue
            # Only follow: dated blog posts, blog pagination, and pages linked from the menu/footer.
            if re.search(r"/\d{4}/\d{2}/\d{2}/", link) or "/blog/page/" in link or "paged" in link:
                queue.append(link)
            elif urlparse(link).path.strip("/").count("/") == 0 or "/team/" in link:
                queue.append(link)
    with open(os.path.join(cache, "failures.json"), "w", encoding="utf-8") as f:
        json.dump(failures, f, indent=2)
    print("requests used:", client.used(), "failures:", len(failures))


if __name__ == "__main__":
    main(sys.argv[1])
