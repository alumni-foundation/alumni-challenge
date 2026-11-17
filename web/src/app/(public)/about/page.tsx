import { CheckCircle2 } from "lucide-react";
import type { Metadata } from "next";
import { Eyebrow, Inline, SiteImage, Title, between, anyHeading, isHeading, paras } from "@/components/site/parts";
import { Card } from "@/components/ui";
import { loadPage, pageImage } from "@/lib/site-content";

export const metadata: Metadata = {
  title: "About us",
  description: "Our vision is to cultivate a diverse alumni movement spanning all 47 counties in Kenya and Africa, working collectively to ensure equitable access to quality education.",
};

export default function AboutPage() {
  const { blocks } = loadPage("about-us");
  const eyebrow = blocks.find((b) => b.type === "heading" && b.level === 6);
  const title = blocks.find((b) => b.type === "heading" && b.level === 2);
  const intro = paras(blocks.slice(0, blocks.findIndex((b) => b.type === "image")));
  // The old counters are a number then its label. "Years of Service" is left out (its number did not fit the dates).
  const all = paras(blocks);
  const stats = all.flatMap((p, i) => (/^\d+$/.test(p.text) && all[i + 1] ? [{ value: p.text, label: all[i + 1].text.replace(/\s+/g, " ") }] : [])).filter((s) => s.label !== "Years of Service");
  const vision = between(blocks, isHeading("Our Vision"), anyHeading);
  const mission = between(blocks, isHeading("Our Mission"), anyHeading);
  const history = between(blocks, isHeading("Our History"));
  const historyIntro = paras(history)[0];
  const historyList = history.find((b) => b.type === "list");
  const missionHead = blocks.find((b) => b.type === "heading" && b.level === 1);

  return (
    <div className="space-y-16 sm:space-y-24">
      <section className="grid items-center gap-8 md:grid-cols-2 md:gap-12">
        <div>
          {eyebrow?.type === "heading" && <Eyebrow>{eyebrow.text}</Eyebrow>}
          {title?.type === "heading" && <Title as="h1" className="mt-2">{title.text}</Title>}
          <div className="mt-5 space-y-4 text-body text-muted">
            {intro.map((p) => <p key={p.text}><Inline text={p.text} /></p>)}
          </div>
        </div>
        <div className="mx-auto w-full max-w-md overflow-hidden rounded-[1.75rem] shadow-lifted md:max-w-none">
          <SiteImage pic={pageImage("alumni_aboutii.jpg")!} alt="Students and teachers clapping together at a school gathering" sizes="(min-width: 768px) 50vw, 100vw" priority className="object-cover" />
        </div>
      </section>

      {stats.length > 0 && (
        <section aria-label="In numbers">
          <dl className="grid gap-3 sm:grid-cols-3">
            {stats.map((s) => (
              <Card key={s.label} elevation="raised" className="text-center">
                <dd className="text-display font-semibold text-gold">{s.value}</dd>
                <dt className="mt-1 text-small text-muted">{s.label}</dt>
              </Card>
            ))}
          </dl>
        </section>
      )}

      <section aria-labelledby="mission" className="grid items-center gap-8 md:grid-cols-[2fr_3fr] md:gap-12">
        <div className="mx-auto w-full max-w-sm overflow-hidden rounded-[1.75rem] shadow-raised md:max-w-none">
          <SiteImage pic={pageImage("mission.jpg")!} alt="Schoolgirls in green uniforms standing together" sizes="(min-width: 768px) 40vw, 100vw" className="object-cover" />
        </div>
        <div className="space-y-5">
          {missionHead?.type === "heading" && <Title id="mission">{missionHead.text}</Title>}
          <Card large>
            <h3 className="text-heading font-semibold">Our Vision</h3>
            <p className="mt-2 text-muted">{paras(vision)[0]?.text}</p>
          </Card>
          <Card large>
            <h3 className="text-heading font-semibold">Our Mission</h3>
            <p className="mt-2 text-muted">{paras(mission)[0]?.text}</p>
          </Card>
        </div>
      </section>

      <section aria-labelledby="history" className="mx-auto max-w-3xl">
        <Title id="history">Our History</Title>
        {historyIntro && <p className="mt-4 text-body text-muted">{historyIntro.text}</p>}
        {historyList?.type === "list" && (
          <ul className="mt-5 grid gap-3 sm:grid-cols-2">
            {historyList.items.map((item) => (
              <li key={item} className="flex items-start gap-3 rounded-card border border-line bg-surface p-4 shadow-resting">
                <CheckCircle2 className="mt-0.5 size-5 shrink-0 text-brand" aria-hidden />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
