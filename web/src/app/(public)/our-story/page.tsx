import { BookOpen, GraduationCap, HeartHandshake, School } from "lucide-react";
import type { Metadata } from "next";
import { Eyebrow, Inline, SiteImage, Title, between, anyHeading, isHeading, paras } from "@/components/site/parts";
import { Card } from "@/components/ui";
import { Icon3D } from "@/components/ui/icon3d";
import { loadPage, pageImage } from "@/lib/site-content";

export const metadata: Metadata = {
  title: "Our story",
  description: "As Alumni Challenge, we have a dream of a Kenyan alumni movement made of a mosaic representation of all 47 counties, all working towards equal access to quality education.",
};

const PILLARS = [
  { name: "Student Empowerment", icon: GraduationCap, tone: "ember" },
  { name: "Teacher Recognition", icon: BookOpen, tone: "gold" },
  { name: "Institutional Development", icon: School, tone: "sky" },
  { name: "Community Engagement", icon: HeartHandshake, tone: "moss" },
] as const;

export default function OurStoryPage() {
  const { blocks } = loadPage("about-us-2");
  const eyebrow = blocks.find((b) => b.type === "heading" && b.level === 6);
  const letterEnd = blocks.findIndex((b) => b.type === "heading" && b.text.startsWith("- "));
  const letter = paras(blocks.slice(blocks.findIndex(anyHeading) + 1, letterEnd));
  const signoff = blocks[letterEnd];
  const role = paras(blocks.slice(letterEnd + 1))[0];
  const pillarsEyebrow = blocks.find((b) => b.type === "heading" && b.level === 4);
  const pillarsTitle = blocks.find((b) => b.type === "heading" && b.level === 3 && b.text.startsWith("Pillars"));
  const closing = paras(blocks).at(-1);

  return (
    <div className="space-y-16 sm:space-y-24">
      <section className="grid gap-8 md:grid-cols-[2fr_3fr] md:gap-12">
        <div className="mx-auto w-full max-w-sm overflow-hidden rounded-[1.75rem] shadow-lifted md:sticky md:top-8 md:max-w-none md:self-start">
          <SiteImage pic={pageImage("alumni_about-scaled.jpg")!} alt="A golfer bending to pick up a tee on a green fairway" sizes="(min-width: 768px) 40vw, 100vw" priority className="object-cover" />
        </div>
        <div>
          {eyebrow?.type === "heading" && <Eyebrow>{eyebrow.text}</Eyebrow>}
          <h1 className="mt-2 text-title sm:text-display">Our <em className="accent-serif">story</em></h1>
          <div className="mt-6 space-y-4 text-body text-muted">
            {letter.map((p) => <p key={p.text}><Inline text={p.text} /></p>)}
          </div>
          {signoff?.type === "heading" && (
            <p className="mt-6">
              <span className="block text-heading font-semibold">{signoff.text}</span>
              {role && <span className="block text-small text-muted">{role.text}</span>}
            </p>
          )}
        </div>
      </section>

      <section aria-labelledby="pillars">
        {pillarsEyebrow?.type === "heading" && <Eyebrow>{pillarsEyebrow.text}</Eyebrow>}
        {pillarsTitle?.type === "heading" && <Title id="pillars" className="mt-2">{pillarsTitle.text}</Title>}
        <ul className="mt-8 grid gap-4 sm:grid-cols-2">
          {PILLARS.map((p) => (
            <li key={p.name}>
              <Card elevation="raised" className="h-full p-6">
                <Icon3D icon={p.icon} tone={p.tone} size="md" />
                <h3 className="mt-4 text-heading font-semibold">{p.name}</h3>
                <p className="mt-2 text-muted">{paras(between(blocks, isHeading(p.name), anyHeading))[0]?.text}</p>
              </Card>
            </li>
          ))}
        </ul>
        {closing && <p className="mx-auto mt-8 max-w-3xl text-center text-lead text-muted">{closing.text}</p>}
      </section>
    </div>
  );
}
