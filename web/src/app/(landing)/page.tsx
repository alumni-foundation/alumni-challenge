import { OrgGrid } from "@/components/public/org";
import { Hero, MIN_STAT, PARTNER_STAT, SCHOOL_STAT, countLabel, type HeroStat } from "@/components/landing/hero";
import { Points, SectionHead } from "@/components/landing/sections";
import { hasSession } from "@/lib/server/auth";
import { fetchOrgs } from "@/lib/server/public-api";

const PAGE_LIMIT = 100; // what fetchOrgs asks for

export default async function Home() {
  const [schools, partners, signedIn] = await Promise.all([fetchOrgs("school"), fetchOrgs("partner"), hasSession()]);

  // Real counts from the public API, shown only when both are big enough to mean something.
  const stats: HeroStat[] = [];
  if (schools && partners && schools.length >= MIN_STAT && partners.length >= MIN_STAT) {
    stats.push({ ...SCHOOL_STAT, value: countLabel(schools.length, PAGE_LIMIT), label: "Schools" });
    stats.push({ ...PARTNER_STAT, value: countLabel(partners.length, PAGE_LIMIT), label: "Partners" });
  }

  return (
    <>
      <Hero signedIn={signedIn} stats={stats} />
      <Points />
      <div className="mx-auto max-w-6xl space-y-20 px-4 pb-4 sm:px-6 lg:px-10">
        <section aria-labelledby="schools-title" id="schools" className="scroll-mt-6">
          <SectionHead eyebrow="Schools" id="schools-title" href="/schools">
            Find the school you <em className="accent-serif">belong</em> to.
          </SectionHead>
          <OrgGrid orgs={schools?.slice(0, 6) ?? null} base="/schools" noun="schools" />
        </section>
        <section aria-labelledby="partners-title" id="partners" className="scroll-mt-6">
          <SectionHead eyebrow="Partners" id="partners-title" href="/partners">
            Organisations that back the <em className="accent-serif">community</em>.
          </SectionHead>
          <OrgGrid orgs={partners?.slice(0, 6) ?? null} base="/partners" noun="partners" />
        </section>
      </div>
    </>
  );
}
