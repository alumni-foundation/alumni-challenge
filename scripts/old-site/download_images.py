"""Step 3: download every content image into <out>/images, one request at a time.

usage: python download_images.py <cache_dir> <out_dir>
For each picture it tries the original (the WordPress size suffix such as -300x130 is removed) and falls back
to the exact file the page used. The result of every picture is written to <cache_dir>/image_report.json.
"""

import json
import os
import sys
from urllib.parse import quote

import extract as ex
import sitemodel as sm
from client import Client

IMAGE_TYPES = ("image/", "application/octet-stream")


def main(cache: str, out: str) -> None:
    model = sm.build(cache)
    names = sm.local_names(model)
    os.makedirs(os.path.join(out, "images"), exist_ok=True)
    client = Client(os.path.join(cache, "requests.log"))
    report_path = os.path.join(cache, "image_report.json")
    report: dict = json.load(open(report_path, encoding="utf-8")) if os.path.exists(report_path) else {}
    for url in sm.image_urls(model):
        local = names[url]
        dest = os.path.join(out, "images", local)
        if report.get(url, {}).get("ok") and os.path.exists(dest):
            continue
        candidates = []
        if "/elementor/thumbs/" in url:
            # Elementor makes a cropped copy with a hash in its name; ask WordPress where the original lives.
            term = os.path.basename(url).rsplit("-", 1)[0]
            status, body, _, err = client.get(f"{sm.BASE}/wp-json/wp/v2/media?search={quote(term)}&_fields=source_url")
            if status == 200:
                for row in json.loads(body or b"[]"):
                    candidates.append(row["source_url"])
        if ex.full_size(url) != url:
            candidates.append(ex.full_size(url))
        candidates.append(url)
        result = {"ok": False, "local": local, "tried": []}
        for cand in dict.fromkeys(candidates):
            status, body, ctype, err = client.get(cand)
            result["tried"].append({"url": cand, "status": status, "error": err})
            if status == 200 and body and (ctype or "").startswith(IMAGE_TYPES):
                with open(dest, "wb") as f:
                    f.write(body)
                result.update(ok=True, fetched=cand, bytes=len(body), original_found=(cand == ex.full_size(url) and cand != url))
                break
        report[url] = result
        print("ok " if result["ok"] else "FAIL", local, result.get("bytes", ""), flush=True)
        json.dump(report, open(report_path, "w", encoding="utf-8"), indent=1)
    print("requests used:", client.used())


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
