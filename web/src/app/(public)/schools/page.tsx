import type { Metadata } from "next";
import { OrgGrid } from "@/components/public/org";
import { PageHeader } from "@/components/ui";
import { fetchOrgs } from "@/lib/server/public-api";

export const metadata: Metadata = { title: "Schools" };

export default async function SchoolsPage() {
  const schools = await fetchOrgs("school");
  return (
    <>
      <PageHeader title="Schools" subtitle="The schools whose alumni are on Alumni Challenge." />
      <OrgGrid orgs={schools} base="/schools" noun="schools" />
    </>
  );
}
