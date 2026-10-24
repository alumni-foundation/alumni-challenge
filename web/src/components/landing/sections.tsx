import { HeartHandshake, Search, Trophy } from "lucide-react";
import Link from "next/link";
import { Card } from "@/components/ui";
import { Icon3D } from "@/components/ui/icon3d"; // direct import: the ui index is a client module

const POINTS = [
  { icon: Search, tone: "ember", title: "Find your people", body: "Look up classmates and fellow alumni by school, year, country or what they do now." },
  { icon: HeartHandshake, tone: "sky", title: "Stay close to your school", body: "Verified alumni, school staff and partners in one trusted place, and you choose who sees what." },
  { icon: Trophy, tone: "gold", title: "Meet in person", body: "Events bring the community together, starting with golf tournaments." },
] as const;

/** A section heading: a small label, then a headline that may carry one serif word. */
export function SectionHead({ eyebrow, id, children, href, linkLabel }: {
  eyebrow: string; id: string; children: React.ReactNode; href?: string; linkLabel?: string;
}) {
  return (
    <div className="mb-8 flex flex-wrap items-end justify-between gap-3">
      <div>
        <p className="text-caption font-semibold uppercase tracking-widest text-brand-ink">{eyebrow}</p>
        <h2 id={id} className="mt-2 text-display sm:text-[2.5rem] sm:leading-[1.1]">{children}</h2>
      </div>
      {href && (
        <Link href={href} className="inline-flex min-h-11 items-center text-small font-medium text-brand-ink hover:underline">
          {linkLabel ?? "See all"}
        </Link>
      )}
    </div>
  );
}

export function Points() {
  return (
    <section aria-labelledby="why" className="mx-auto max-w-6xl px-4 py-16 sm:px-6 sm:py-24 lg:px-10">
      <SectionHead eyebrow="What it is for" id="why">
        A calm home for your school <em className="accent-serif">family</em>.
      </SectionHead>
      <ul className="grid gap-5 md:grid-cols-3">
        {POINTS.map((p) => (
          <li key={p.title}>
            <Card elevation="raised" className="h-full p-6 sm:p-8">
              <Icon3D icon={p.icon} tone={p.tone} size="lg" />
              <h3 className="mt-6 text-heading">{p.title}</h3>
              <p className="mt-2 text-muted">{p.body}</p>
            </Card>
          </li>
        ))}
      </ul>
    </section>
  );
}
