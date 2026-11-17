/**
 * A reader for the small Markdown subset the old-site collection uses: front matter, headings, paragraphs,
 * bullet and numbered lists, images, and inline **bold**, *italic* and [links](url). Nothing else is needed.
 */

export type Block =
  | { type: "heading"; level: number; text: string }
  | { type: "p"; text: string }
  | { type: "list"; ordered: boolean; items: string[] }
  | { type: "image"; alt: string; file: string };

export type Inline = { t: "text"; v: string } | { t: "b" | "i"; v: Inline[] } | { t: "a"; href: string; v: Inline[] };

export type Parsed = { meta: Record<string, string | null>; blocks: Block[] };

export function parseMarkdown(source: string): Parsed {
  const text = source.replace(/\r\n/g, "\n");
  const meta: Record<string, string | null> = {};
  let body = text;
  const fm = /^---\n([\s\S]*?)\n---\n/.exec(text);
  if (fm) {
    body = text.slice(fm[0].length);
    for (const line of fm[1].split("\n")) {
      const m = /^([a-z_]+): (.*)$/.exec(line);
      if (m) meta[m[1]] = JSON.parse(m[2]) as string | null;
    }
  }
  const blocks: Block[] = [];
  for (const chunk of body.split(/\n{2,}/)) {
    const c = chunk.trim();
    if (!c || c.startsWith("**Form**")) continue; // the old contact form: not rebuilt
    const h = /^(#{1,6}) (.+)$/.exec(c);
    if (h) {
      blocks.push({ type: "heading", level: h[1].length, text: h[2].trim() });
      continue;
    }
    const img = /^!\[([^\]]*)\]\(([^)]+)\)/.exec(c);
    if (img) {
      blocks.push({ type: "image", alt: img[1], file: img[2].split("/").pop() ?? img[2] });
      continue;
    }
    const lines = c.split("\n");
    if (lines.every((l) => l.startsWith("- "))) {
      blocks.push({ type: "list", ordered: false, items: lines.map((l) => l.slice(2).trim()) });
    } else if (lines.every((l) => /^\d+\. /.test(l))) {
      blocks.push({ type: "list", ordered: true, items: lines.map((l) => l.replace(/^\d+\. /, "").trim()) });
    } else {
      blocks.push({ type: "p", text: c.replace(/\s*<!--.*?-->/g, "") });
    }
  }
  return { meta, blocks };
}

const TOKEN = /\*\*([^*]+?)\*\*|\*([^*\s][^*]*?)\*|\[([^\]]+)\]\(([^)\s]+)\)/;

/** Splits a line of text into plain text, bold, italic and link pieces. Spaces are kept exactly as written. */
export function parseInline(text: string): Inline[] {
  const out: Inline[] = [];
  let rest = text;
  while (rest) {
    const m = TOKEN.exec(rest);
    if (!m) {
      out.push({ t: "text", v: rest });
      break;
    }
    if (m.index > 0) out.push({ t: "text", v: rest.slice(0, m.index) });
    if (m[1] !== undefined) out.push({ t: "b", v: parseInline(m[1]) });
    else if (m[2] !== undefined) out.push({ t: "i", v: parseInline(m[2]) });
    else out.push({ t: "a", href: m[4], v: parseInline(m[3]) });
    rest = rest.slice(m.index + m[0].length);
  }
  return out;
}

/** The words of a piece of Markdown with all the marks taken off. */
export function plainText(text: string): string {
  const flat = (nodes: Inline[]): string => nodes.map((n) => (n.t === "text" ? n.v : flat(n.v))).join("");
  return flat(parseInline(text)).replace(/\s+/g, " ").trim();
}
