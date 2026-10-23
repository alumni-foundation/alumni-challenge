import { OrgSectionPage } from "@/components/org/pages";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <OrgSectionPage kind="school" id={id} section="roster" />;
}
