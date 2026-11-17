import type { Metadata } from "next";
import { InvolvedBand } from "@/components/site/involved-band";
import { Eyebrow, Inline, SiteImage, Title, paras } from "@/components/site/parts";
import { Card } from "@/components/ui";
import { loadPage, pageImage } from "@/lib/site-content";

export const metadata: Metadata = {
  title: "Get involved",
  description: "Your generous donation, big or small, makes a significant difference. Together, let’s empower students, foster community growth, and create a lasting impact through the Alumni Challenge.",
};

export default function GetInvolvedPage() {
  const { blocks } = loadPage("get-involved");
  const eyebrow = blocks.find((b) => b.type === "heading" && b.level === 4);
  const title = blocks.find((b) => b.type === "heading" && b.level === 3);
  const ways = blocks.find((b) => b.type === "list");
  const [thanks, learn] = paras(blocks);

  return (
    <div className="space-y-16 sm:space-y-20">
      <section className="grid items-center gap-8 md:grid-cols-2 md:gap-12">
        <div>
          {eyebrow?.type === "heading" && <Eyebrow>{eyebrow.text}</Eyebrow>}
          <h1 className="mt-2 text-title sm:text-display">Get <em className="accent-serif">involved</em></h1>
          {thanks && <p className="mt-4 text-muted"><Inline text={thanks.text} /></p>}
          {learn && <p className="mt-3 text-muted"><Inline text={learn.text} /></p>}
        </div>
        <div className="overflow-hidden rounded-[1.75rem] shadow-lifted">
          <SiteImage pic={pageImage("polikophotography-206.jpg")!} alt="Alumni presenting a large cheque to a schoolgirl and her teachers" sizes="(min-width: 768px) 50vw, 100vw" priority className="object-cover" />
        </div>
      </section>

      {ways?.type === "list" && (
        <section aria-labelledby="ways">
          <Title id="ways">{title?.type === "heading" ? title.text : "Inspiration and Impact"}</Title>
          <ol className="mt-8 grid gap-4 md:grid-cols-3">
            {ways.items.map((item, i) => {
              const [head, ...body] = item.split(": ");
              return (
                <li key={head}>
                  <Card elevation="raised" className="h-full p-6">
                    <span className="grid size-9 place-items-center rounded-full bg-gold-soft text-small font-semibold text-gold" aria-hidden>{i + 1}</span>
                    <h3 className="mt-4 text-heading font-semibold">{head}</h3>
                    <p className="mt-2 text-muted">{body.join(": ")}</p>
                  </Card>
                </li>
              );
            })}
          </ol>
        </section>
      )}

      <InvolvedBand />
    </div>
  );
}
