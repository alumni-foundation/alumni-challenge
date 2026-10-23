import { OrgPage } from "@/components/public/org-page";

export default async function SchoolPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <OrgPage id={id} type="school" />;
}
