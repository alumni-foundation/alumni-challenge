# Collecting the old website

Copies the public content of https://alumnichallenge.foundation/ (WordPress + Elementor) into `web/content/old-site/`.
Needs Python 3.12 and `pip install beautifulsoup4 lxml` (Pillow is not needed). Polite by design: one request at a
time, 1 second apart, a browser user agent, two retries, and a hard stop at 100 requests.

Run from this folder, with a cache folder outside the repo (raw HTML is not committed):

    python fetch_pages.py  <cache_dir>                          # 1. page HTML -> cache
    python download_images.py <cache_dir> ../../web/content/old-site   # 2. images (originals, not thumbnails)
    python build_content.py   <cache_dir> ../../web/content/old-site   # 3. Markdown, JSON, INVENTORY.md

- `client.py` is the polite HTTP client, `extract.py` turns Elementor HTML into text blocks, `sitemodel.py` reads
  the whole site into one model.
- `partner_names.json` holds partner names read by eye from the logo images (the page has no alt text).
- `contradictions.json` is the hand-written list of conflicting facts shown at the end of INVENTORY.md.
