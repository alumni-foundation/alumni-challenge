import type { Metadata } from "next";
import { Eyebrow, SiteImage, Title } from "@/components/site/parts";
import { team } from "@/lib/site-content";

export const metadata: Metadata = {
  title: "The team",
  description: "Meet Mark Macharia, the visionary behind Alumni Challenge, and the Alumni Lead Transformers.",
};

export default function TeamPage() {
  const [founder, ...others] = team();
  return (
    <div className="space-y-16 sm:space-y-20">
      <section className="grid items-start gap-8 md:grid-cols-[2fr_3fr] md:gap-12">
        <div className="mx-auto w-full max-w-sm overflow-hidden rounded-[1.75rem] shadow-lifted md:max-w-none">
          {founder.photo && <SiteImage pic={founder.photo} alt={founder.name} sizes="(min-width: 768px) 40vw, 100vw" priority className="object-cover" />}
        </div>
        <div>
          <Eyebrow>the Founder</Eyebrow>
          <h1 className="mt-2 text-title sm:text-display">{founder.name}</h1>
          <p className="mt-1 text-lead text-muted">{founder.role}</p>
          <div className="mt-6 space-y-4 text-body text-muted">
            {founder.bio.map((p) => <p key={p}>{p}</p>)}
          </div>
        </div>
      </section>

      <section aria-labelledby="our-team">
        <Eyebrow>OUR TEAM</Eyebrow>
        <Title id="our-team" className="mt-2">Alumni Lead Transformers</Title>
        <ul className="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {others.map((p) => (
            <li key={p.name}>
              <div className="h-full overflow-hidden rounded-card border border-line bg-surface shadow-raised">
                <div className="aspect-[4/5] overflow-hidden bg-sunken">
                  {p.photo && <SiteImage pic={p.photo} alt={p.name} sizes="(min-width: 1024px) 384px, (min-width: 640px) 50vw, 100vw" className="h-full object-cover object-top" />}
                </div>
                <div className="p-5">
                  <h3 className="text-heading font-semibold">{p.name}</h3>
                  {p.role && <p className="mt-0.5 text-small text-muted">{p.role}</p>}
                  {p.bio.map((b) => <p key={b} className="mt-3 text-small text-muted">{b}</p>)}
                </div>
              </div>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
