/**
 * The only changes made to the words collected from the old website. Everything else is shown as it was written.
 * Each rule is listed here (and tested), so it is easy to see exactly what differs from the old site.
 */

/** Sentences that state a founding year. The old site contradicts itself (2020, 2021, 2022), so none are shown. */
export const REMOVED_SENTENCES = [
  "Founded in October 2021 as a response to the financial hardships faced by Kenyan schools during the Covid-19 pandemic, Alumni Challenge emerged with the primary aim of providing financial assistance to these struggling educational institutions.",
  "It started with a news article in 2020.",
  "After years of anticipation, he turned his vision into reality in 2022.",
] as const;

/** One set of opening hours everywhere (the footer's; the old home page said something different). */
export const HOURS_SHORT = "Mon to Fri 08:00 to 17:00, Sat 09:00 to 12:00";
const OLD_HOURS = "between 09:00 and 18:00 Mon-Sat";

/** Pages on the old site, and where each now lives. */
const ROUTES: Record<string, string> = {
  "about-us": "/about",
  "about-us-2": "/our-story",
  "the-team": "/team",
  programs: "/programs",
  partners: "/partners",
  "get-involved": "/get-involved",
  blog: "/blog",
  contact: "/contact",
};

export const EMAIL = "admin@alumnichallenge.foundation";

/** Turns an old-site link into one that works here. Returns null for a link that should show as plain text. */
export function fixHref(href: string): string | null {
  if (/^https?:\/\/mailto:/i.test(href)) return `mailto:${EMAIL}`; // the old posts wrote "http://mailto:..."
  if (href === "mailto:#" || href === "#") return null;
  if (/^(mailto:|tel:)/.test(href)) return href;
  const m = /^https?:\/\/(?:www\.)?alumnichallenge\.foundation(\/[^?#]*)?/.exec(href);
  if (!m) return href;
  const path = (m[1] ?? "/").replace(/^\/+|\/+$/g, "");
  if (path === "") return "/";
  if (path in ROUTES) return ROUTES[path];
  const post = /^\d{4}\/\d{2}\/\d{2}\/([^/]+)$/.exec(path);
  if (post) return `/blog/${post[1]}`;
  if (path.startsWith("team/")) return "/team";
  return null; // category and author pages have no equivalent here
}

/** The wording fixes that apply inside any piece of text. */
export function editText(text: string): string {
  let t = text;
  for (const s of REMOVED_SENTENCES) t = t.replace(s, "");
  return t.replace(/Alumnus Challenge/g, "Alumni Challenge").replace(OLD_HOURS, HOURS_SHORT).replace(/ {2,}/g, " ").trim();
}
