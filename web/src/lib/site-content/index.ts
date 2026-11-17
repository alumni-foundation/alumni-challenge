import { readFileSync } from "node:fs";
import path from "node:path";
import manifest from "../../../content/old-site/site-images.json";
import partnersJson from "../../../content/old-site/partners.json";
import teamJson from "../../../content/old-site/team.json";
import siteJson from "../../../content/old-site/site.json";
import { editText } from "./edits";
import { parseMarkdown, type Block } from "./markdown";

const ROOT = path.join(process.cwd(), "content", "old-site");
const sizes = manifest as unknown as Record<string, [number, number]>;

export type Pic = { src: string; width: number; height: number };

/** A picture in public/images/site with its real size, so next/image can reserve the space. */
export function pic(src: string): Pic {
  const s = sizes[src];
  if (!s) throw new Error(`Unknown site image ${src}. Run scripts/old-site/prepare_site_images.py`);
  return { src, width: s[0], height: s[1] };
}

/** Which prepared picture each collected page image became. */
const PAGE_IMAGES: Record<string, string> = {
  "alumni_aboutii.jpg": "/images/site/about.jpg",
  "mission.jpg": "/images/site/about-mission.jpg",
  "alumni_about-scaled.jpg": "/images/site/our-story.jpg",
  "kenya-high-school-alumni.jpg": "/images/site/programs-golf.jpg",
  "mentorship.jpg": "/images/site/programs-mentorship.jpg",
  "polikophotography-206.jpg": "/images/site/get-involved.jpg",
  "home.jpg": "/images/site/who-we-are.jpg",
};

export type Slug = "home" | "about-us" | "about-us-2" | "the-team" | "programs" | "get-involved" | "blog";

/** The collected Markdown for one page, with the wording edits applied and empty blocks dropped. */
export function loadPage(slug: Slug | string, dir: "pages" | "blog" = "pages") {
  const parsed = parseMarkdown(readFileSync(path.join(ROOT, dir, `${slug}.md`), "utf8"));
  const blocks: Block[] = [];
  for (const b of parsed.blocks) {
    if (b.type === "p" || b.type === "heading") {
      const text = editText(b.text);
      if (text) blocks.push({ ...b, text });
    } else if (b.type === "list") {
      blocks.push({ ...b, items: b.items.map(editText).filter(Boolean) });
    } else {
      blocks.push(b);
    }
  }
  return { meta: parsed.meta, blocks };
}

export function pageImage(file: string): Pic | null {
  const src = PAGE_IMAGES[file];
  return src ? pic(src) : null;
}

/* ---- Blog ----------------------------------------------------------------------------------- */

export type Post = { slug: string; title: string; date: string; dateLabel: string; excerpt: string; image: Pic; blocks: Block[] };

const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
export const longDate = (iso: string) => {
  const [y, m, d] = iso.split("-").map(Number);
  return `${d} ${MONTHS[m - 1]} ${y}`;
};

/** The order the old /blog/ list used (newest first; the posts all share one date). */
function postOrder(): string[] {
  const list = parseMarkdown(readFileSync(path.join(ROOT, "pages", "blog.md"), "utf8"));
  return list.blocks.flatMap((b) => {
    const m = b.type === "heading" ? /\/(\d{4}\/\d{2}\/\d{2})\/([^/)]+)\/?\)/.exec(b.text) : null;
    return m ? [m[2]] : [];
  });
}

export function loadPost(slug: string): Post {
  const { meta, blocks } = loadPage(slug, "blog");
  return {
    slug,
    title: editText(meta.title ?? slug),
    date: meta.date ?? "",
    dateLabel: meta.date ? longDate(meta.date) : "",
    excerpt: editText(meta.excerpt ?? ""),
    image: pic(`/images/site/blog/${slug}.jpg`),
    blocks,
  };
}

export const allPosts = (): Post[] => postOrder().map(loadPost);
export const postSlugs = (): string[] => postOrder();

/* ---- People, supporters, contact ------------------------------------------------------------ */

export type Person = { name: string; role: string | null; photo: Pic | null; bio: string[] };

export function team(): Person[] {
  return teamJson.map((p) => {
    const slug = (p.photo_file ?? "").replace(/^team-/, "").replace(/\.[a-z]+$/, "");
    return {
      name: p.name,
      role: p.role,
      photo: p.photo_file ? pic(`/images/site/team/${slug}.jpg`) : null,
      bio: (p.bio ?? "").split(/\n{2,}/).map(editText).filter(Boolean),
    };
  });
}

export type Supporter = { name: string; logo: Pic; url: string | null };

/** Supporter logos whose name is known. A logo whose name was only a guess from its file name is left out. */
export function supporters(): { shown: Supporter[]; leftOut: string[] } {
  const shown: Supporter[] = [];
  const leftOut: string[] = [];
  for (const p of partnersJson) {
    if (!p.name_confirmed) {
      leftOut.push(p.name);
      continue;
    }
    shown.push({ name: p.name, logo: pic(`/images/site/partners/${p.logo_file.replace("partner-", "")}`), url: p.website_url });
  }
  return { shown, leftOut };
}

/** The "Donate / Volunteer / Newsletters / Get Involved" band, in the old wording (hours corrected). */
export function involvedBand() {
  const blocks = siteJson.shared_sections.call_to_action_band_and_latest_posts as { type: string; text?: string; label?: string }[];
  const texts = blocks.filter((b) => b.type === "paragraph").map((b) => editText(b.text ?? ""));
  const pitch = blocks.find((b) => b.type === "paragraph" && b.text?.startsWith("Join the Alumni Movement"));
  const [title, ...rest] = (pitch?.text ?? "").split(/(?<=Movement) /);
  return {
    actions: ["Donate Now", "Volunteer", "Newsletters", "Get Involved"].filter((a) => texts.includes(a)),
    title: title || "Join the Alumni Movement",
    text: editText(rest.join(" ")),
    callBack: texts.find((t) => /call back/i.test(t))?.replace(/^\[|\]\(.*$/g, "") ?? "Request a Call Back",
  };
}
