import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { EMAIL, HOURS_SHORT, REMOVED_SENTENCES, editText, fixHref } from "./edits";
import { parseInline, parseMarkdown, plainText } from "./markdown";

const ROOT = path.join(process.cwd(), "content", "old-site");
const files = ["pages", "blog"].flatMap((d) => readdirSync(path.join(ROOT, d)).map((f) => path.join(ROOT, d, f)));
const body = (f: string) => parseMarkdown(readFileSync(f, "utf8")).blocks.map((b) => (b.type === "list" ? b.items.join("\n") : "text" in b ? b.text : "")).join("\n");

describe("editorial rules", () => {
  it("each removed founding-year sentence exists in the collected content exactly once", () => {
    const all = files.map((f) => readFileSync(f, "utf8").replace(/\r\n/g, "\n")).join("\n");
    for (const s of REMOVED_SENTENCES) expect(all.split(s).length - 1, s).toBe(1);
  });

  it("no founding year (2020, 2021, 2022) is left in any page or post once the rules are applied", () => {
    for (const f of files) {
      if (f.includes("home.md")) continue; // the home page is rebuilt from sections; its 'Founded in 2022' heading is never shown
      expect(editText(body(f)), f).not.toMatch(/\b(2020|2021|2022)\b/);
    }
  });

  it("writes Alumni Challenge, never Alumnus Challenge", () => {
    expect(editText("Thank you for your interest in the Alumnus Challenge event.")).toBe("Thank you for your interest in the Alumni Challenge event.");
    for (const f of files) expect(editText(body(f)), f).not.toContain("Alumnus Challenge");
  });

  it("uses one set of opening hours", () => {
    expect(editText("phone 0104 063 038 between 09:00 and 18:00 Mon-Sat.")).toBe(`phone 0104 063 038 ${HOURS_SHORT}.`);
    expect(HOURS_SHORT).toBe("Mon to Fri 08:00 to 17:00, Sat 09:00 to 12:00");
  });

  it("repairs the dead and broken links", () => {
    expect(fixHref("http://mailto:admin@alumnichallenge.foundation")).toBe(`mailto:${EMAIL}`);
    expect(fixHref("http://mailto:admin@alumnichallenge.foundation/")).toBe(`mailto:${EMAIL}`);
    expect(fixHref("mailto:#")).toBeNull();
    expect(fixHref("https://alumnichallenge.foundation/programs/")).toBe("/programs");
    expect(fixHref("https://alumnichallenge.foundation/about-us-2/")).toBe("/our-story");
    expect(fixHref("https://alumnichallenge.foundation/2023/08/02/some-post/")).toBe("/blog/some-post");
    expect(fixHref("https://alumnichallenge.foundation/category/uncategorized/")).toBeNull();
    expect(fixHref("https://example.org/x")).toBe("https://example.org/x");
  });

  it("every link in the collected content resolves to a route, a mailto/tel, or an outside site", () => {
    const routes = new Set(["/", "/about", "/our-story", "/team", "/programs", "/partners", "/get-involved", "/blog", "/contact"]);
    for (const f of files) {
      const raw = readFileSync(f, "utf8");
      for (const m of raw.matchAll(/\]\(([^)\s]+)\)/g)) {
        if (m[1].startsWith("../images/")) continue;
        const fixed = fixHref(m[1]);
        if (fixed === null || fixed.startsWith("mailto:") || fixed.startsWith("tel:") || /^https?:/.test(fixed)) continue;
        expect(routes.has(fixed) || fixed.startsWith("/blog/"), `${f}: ${m[1]} -> ${fixed}`).toBe(true);
      }
    }
  });
});

describe("markdown reader", () => {
  it("reads front matter, headings, lists and images", () => {
    const p = parseMarkdown('---\ntitle: "A"\ndate: null\n---\n\n## Head\n\nText **bold** here.\n\n- one\n- two\n\n![](../images/x.jpg)  <!-- background image -->\n');
    expect(p.meta).toEqual({ title: "A", date: null });
    expect(p.blocks).toEqual([
      { type: "heading", level: 2, text: "Head" },
      { type: "p", text: "Text **bold** here." },
      { type: "list", ordered: false, items: ["one", "two"] },
      { type: "image", alt: "", file: "x.jpg" },
    ]);
  });

  it("keeps spaces around bold and links exactly as written", () => {
    expect(parseInline("a **b** , [c](/d) e")).toEqual([
      { t: "text", v: "a " }, { t: "b", v: [{ t: "text", v: "b" }] }, { t: "text", v: " , " },
      { t: "a", href: "/d", v: [{ t: "text", v: "c" }] }, { t: "text", v: " e" },
    ]);
    expect(plainText("a **b** , [c](/d) e")).toBe("a b , c e");
  });
});
