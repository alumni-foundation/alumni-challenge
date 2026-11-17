// Visits every public page of a running site, follows every internal link found on them, and reports anything that
// is not a 200, any `http://mailto:` link, and any mailto that is not the contact address.
// Usage: node scripts/check-public-routes.mjs [baseUrl]   (default http://localhost:3000)
const base = (process.argv[2] ?? "http://localhost:3000").replace(/\/$/, "");
const START = ["/", "/about", "/our-story", "/team", "/programs", "/schools", "/get-involved", "/blog", "/partners", "/contact", "/terms", "/privacy", "/community-rules"];

const seen = new Map();
const problems = [];
const queue = [...START];

const hrefs = (html) => [...html.matchAll(/<a\b[^>]*?\bhref="([^"]+)"/g)].map((m) => m[1].replaceAll("&amp;", "&"));

while (queue.length) {
  const path = queue.shift();
  if (seen.has(path)) continue;
  const res = await fetch(base + path, { redirect: "manual" });
  seen.set(path, res.status);
  if (res.status !== 200) {
    problems.push(`${res.status} ${path}`);
    continue;
  }
  if (!(res.headers.get("content-type") ?? "").includes("text/html")) continue;
  const html = await res.text();
  for (const href of hrefs(html)) {
    if (href.startsWith("http://mailto:") || href.startsWith("https://mailto:")) problems.push(`broken mailto on ${path}: ${href}`);
    else if (href.startsWith("mailto:") && href.split("?")[0] !== "mailto:admin@alumnichallenge.foundation") problems.push(`unexpected mailto on ${path}: ${href}`);
    else if (href.startsWith("/") && !href.startsWith("//")) {
      const clean = href.split("#")[0].split("?")[0];
      // Only follow public pages: the sign-in pages are checked on their own, and files are not pages.
      if (clean && !seen.has(clean) && !/^\/(api|_next|login|register)/.test(clean) && !/\.[a-z0-9]+$/i.test(clean)) queue.push(clean);
    } else if (href.startsWith(base)) queue.push(href.slice(base.length).split("#")[0] || "/");
  }
}

console.log(`Checked ${seen.size} pages on ${base}`);
if (problems.length) {
  console.error(problems.join("\n"));
  process.exit(1);
}
console.log("All public pages return 200 and no broken links were found.");
