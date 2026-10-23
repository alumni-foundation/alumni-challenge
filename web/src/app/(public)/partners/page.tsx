import type { Metadata } from "next";
import { OrgGrid } from "@/components/public/org";
import { PageHeader } from "@/components/ui";
import { fetchOrgs } from "@/lib/server/public-api";

export const metadata: Metadata = { title: "Partners" };

export default async function PartnersPage() {
  const partners = await fetchOrgs("partner");
  return (
    <>
      <PageHeader title="Partners" subtitle="The organisations that support the alumni community." />
      <OrgGrid orgs={partners} base="/partners" noun="partners" />
    </>
  );
}
