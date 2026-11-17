import { Quote } from "lucide-react";
import type { Metadata } from "next";
import { Eyebrow, Inline, SiteImage, Title, between, anyHeading, paras } from "@/components/site/parts";
import { Card } from "@/components/ui";
import { loadPage, pageImage } from "@/lib/site-content";
import type { Block } from "@/lib/site-content/markdown";

export const metadata: Metadata = {
  title: "Programs",
  description: "The Alumni Golf Challenge is a golf series that brings together executives representing their alma mater to participate in a friendly competition.",
};

const isSub = (t: string) => t === "Eligibility criteria" || t === "How to apply" || t.startsWith("What is ");

/** One programme: eyebrow, title, tagline, picture, then each sub-heading with its text or list. */
function Program({ blocks, image, alt, flip }: { blocks: Block[]; image: string; alt: string; flip?: boolean }) {
  const eyebrow = blocks.find((b) => b.type === "heading" && b.level === 4);
  const title = blocks.find((b) => b.type === "heading" && b.level === 3);
  const tagline = paras(blocks)[0];
  const rest = blocks.slice(blocks.findIndex((b) => b.type === "image") + 1);
  const groups: { head: string; body: Block[] }[] = [];
  for (const b of rest) {
    if (b.type === "p" && isSub(b.text)) groups.push({ head: b.text, body: [] });
    else groups.at(-1)?.body.push(b);
  }
  return (
    <section aria-labelledby={`p-${title?.type === "heading" ? title.text.length : 0}`} className="grid items-start gap-8 md:grid-cols-2 md:gap-12">
      <div className={flip ? "md:order-2" : ""}>
        <div className="overflow-hidden rounded-[1.75rem] shadow-lifted">
          <SiteImage pic={pageImage(image)!} alt={alt} sizes="(min-width: 768px) 50vw, 100vw" className="object-cover" />
        </div>
      </div>
      <div>
        {eyebrow?.type === "heading" && <Eyebrow>{eyebrow.text}</Eyebrow>}
        {title?.type === "heading" && <Title id={`p-${title.text.length}`} className="mt-2">{title.text}</Title>}
        {tagline && <p className="mt-3 text-lead text-muted">{tagline.text}</p>}
        <div className="mt-6 space-y-6">
          {groups.map((g) => (
            <div key={g.head}>
              <h3 className="text-heading font-semibold">{g.head}</h3>
              <div className="mt-2 space-y-3 text-muted">
                {g.body.map((b, i) =>
                  b.type === "p" ? (
                    <p key={i}><Inline text={b.text} /></p>
                  ) : b.type === "list" ? (
                    <ul key={i} className="list-disc space-y-1.5 pl-6">{b.items.map((it) => <li key={it}><Inline text={it} /></li>)}</ul>
                  ) : null,
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

export default function ProgramsPage() {
  const { blocks } = loadPage("programs");
  const empowerStart = blocks.findIndex((b) => b.type === "heading" && b.level === 4 && b.text.includes("Empowerment"));
  const testimonialsAt = blocks.findIndex((b) => b.type === "heading" && b.text === "Testimonials");
  const golf = blocks.slice(0, empowerStart);
  const empower = blocks.slice(empowerStart, testimonialsAt);
  // Each testimonial is three lines in a row: what they said, who said it, and who they are.
  const lines = paras(between(blocks, (b) => b.type === "heading" && b.text === "Testimonials", anyHeading));
  const quotes = Array.from({ length: Math.floor(lines.length / 3) }, (_, i) => ({ said: lines[i * 3].text, who: lines[i * 3 + 1].text, role: lines[i * 3 + 2].text }));

  return (
    <div className="space-y-16 sm:space-y-24">
      <header>
        <Eyebrow>Our programs</Eyebrow>
        <h1 className="mt-2 text-title sm:text-display">Programs</h1>
      </header>
      <Program blocks={golf} image="kenya-high-school-alumni.jpg" alt="Four women golfers smiling together on a golf course" />
      <Program blocks={empower} image="mentorship.jpg" alt="A speaker addressing a school hall full of students" flip />
      <section aria-labelledby="testimonials">
        <Title id="testimonials">Testimonials</Title>
        <ul className="mt-8 grid gap-4 md:grid-cols-2">
          {quotes.map((q) => (
            <li key={q.who}>
              <Card elevation="raised" className="flex h-full flex-col p-6">
                <Quote className="size-6 text-gold" aria-hidden />
                <blockquote className="mt-3 flex-1 text-body">{q.said}</blockquote>
                <p className="mt-4 text-small font-semibold">{q.who}</p>
                <p className="text-small text-muted">{q.role}</p>
              </Card>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
