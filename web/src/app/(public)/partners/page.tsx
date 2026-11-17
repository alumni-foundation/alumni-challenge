import type { Metadata } from "next";
import { Eyebrow, SiteImage, Title } from "@/components/site/parts";
import { OrgGrid } from "@/components/public/org";
import { PageHeader } from "@/components/ui";
import { fetchOrgs } from "@/lib/server/public-api";
import { supporters } from "@/lib/site-content";

export const metadata: Metadata = {
  title: "Partners",
  description: "The organisations that support the alumni community, and the sponsors of our events.",
};

export default async function PartnersPage() {
  const partners = await fetchOrgs("partner");
  const { shown } = supporters();
  return (
    <>
      <PageHeader title="Partners" subtitle="The organisations that support the alumni community." />
      <OrgGrid orgs={partners} base="/partners" noun="partners" />

      <section aria-labelledby="supporters" className="mt-16 sm:mt-24">
        <Eyebrow>Alumni Connect</Eyebrow>
        <Title id="supporters" className="mt-2">Supporters</Title>
        <p className="mt-3 text-lead text-muted">Sponsors of our Events</p>
        <ul className="mt-8 grid grid-cols-2 gap-3 sm:grid-cols-3 sm:gap-4 lg:grid-cols-4 xl:grid-cols-6">
          {shown.map((s) => {
            const card = (
              <>
                <span className="grid aspect-[7/3] w-full place-items-center">
                  <SiteImage pic={s.logo} alt={s.name} sizes="(min-width: 1280px) 180px, (min-width: 1024px) 25vw, (min-width: 640px) 33vw, 50vw" className="max-h-full w-auto max-w-full object-contain" />
                </span>
                <span className="mt-2 block text-center text-caption text-muted">{s.name}</span>
              </>
            );
            const cls = "block rounded-card border border-line bg-surface p-4 shadow-resting";
            return (
              <li key={s.name}>
                {s.url ? (
                  <a href={s.url} target="_blank" rel="noopener noreferrer" className={`${cls} transition-shadow hover:shadow-lifted`}>{card}</a>
                ) : (
                  <div className={cls}>{card}</div>
                )}
              </li>
            );
          })}
        </ul>
      </section>
    </>
  );
}
