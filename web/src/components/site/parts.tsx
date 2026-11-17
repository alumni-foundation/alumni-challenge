import Image from "next/image";
import Link from "next/link";
import { fixHref } from "@/lib/site-content/edits";
import { parseInline, type Block, type Inline as InlineNode } from "@/lib/site-content/markdown";
import type { Pic } from "@/lib/site-content";
import { cn } from "@/lib/utils";

/** A prepared site picture with its real size, so nothing jumps while it loads. */
export function SiteImage({ pic, alt, sizes, className, priority = false }: { pic: Pic; alt: string; sizes: string; className?: string; priority?: boolean }) {
  return <Image src={pic.src} alt={alt} width={pic.width} height={pic.height} sizes={sizes} quality={75} {...(priority ? { loading: "eager" as const, fetchPriority: "high" as const } : {})} className={cn("h-auto w-full", className)} />;
}

function nodes(list: InlineNode[]): React.ReactNode[] {
  return list.map((n, i) => {
    if (n.t === "text") return n.v;
    if (n.t === "b" || n.t === "i") return n.t === "b" ? <strong key={i}>{nodes(n.v)}</strong> : <em key={i}>{nodes(n.v)}</em>;
    if (!("href" in n)) return null;
    const href = fixHref(n.href);
    if (!href) return <span key={i}>{nodes(n.v)}</span>;
    const cls = "font-medium text-brand-ink hover:underline";
    if (href.startsWith("/")) return <Link key={i} href={href} className={cls}>{nodes(n.v)}</Link>;
    const outside = /^https?:/.test(href);
    return <a key={i} href={href} className={cls} {...(outside ? { target: "_blank", rel: "noopener noreferrer" } : {})}>{nodes(n.v)}</a>;
  });
}

/** Text with its **bold**, *italic* and [links](url), exactly as collected. */
export function Inline({ text }: { text: string }) {
  return <>{nodes(parseInline(text))}</>;
}

export const Eyebrow = ({ children, className }: { children: React.ReactNode; className?: string }) => (
  <p className={cn("text-caption font-semibold uppercase tracking-widest text-brand-ink", className)}>{children}</p>
);

/** A title with its last word in the serif italic, the same touch the landing headings have. */
export function Title({ children, as: Tag = "h2", className, id }: { children: string; as?: "h1" | "h2"; className?: string; id?: string }) {
  const words = children.split(" ");
  const last = words.pop();
  return (
    <Tag id={id} className={cn(Tag === "h1" ? "text-title sm:text-display" : "text-display sm:text-[2.5rem] sm:leading-[1.1]", className)}>
      {words.length > 0 && `${words.join(" ")} `}
      <em className="accent-serif">{last}</em>
    </Tag>
  );
}

/** Plain reading text for the blocks that have no special layout. */
export function Body({ blocks, className }: { blocks: Block[]; className?: string }) {
  return (
    <div className={cn("space-y-4 text-body", className)}>
      {blocks.map((b, i) => {
        if (b.type === "heading") return <h2 key={i} className="!mt-8 text-heading font-semibold">{b.text}</h2>;
        if (b.type === "p") return <p key={i} className="[&_strong]:font-semibold"><Inline text={b.text} /></p>;
        if (b.type === "list") {
          const L = b.ordered ? "ol" : "ul";
          return (
            <L key={i} className={cn("space-y-2 pl-6", b.ordered ? "list-decimal" : "list-disc")}>
              {b.items.map((it, j) => <li key={j}><Inline text={it} /></li>)}
            </L>
          );
        }
        return null;
      })}
    </div>
  );
}

/** The blocks after the first block that matches `from`, up to (not including) the first that matches `until`. */
export function between(blocks: Block[], from: (b: Block) => boolean, until: (b: Block) => boolean = () => false): Block[] {
  const start = blocks.findIndex(from);
  if (start < 0) throw new Error("A section this page expects is missing from the collected content");
  const rest = blocks.slice(start + 1);
  const end = rest.findIndex(until);
  return end < 0 ? rest : rest.slice(0, end);
}
export const isHeading = (text: string, level?: number) => (b: Block) => b.type === "heading" && b.text === text && (level === undefined || b.level === level);
export const anyHeading = (b: Block) => b.type === "heading";
export const paras = (blocks: Block[]) => blocks.filter((b): b is Extract<Block, { type: "p" }> => b.type === "p");
