"use client";

import { ArrowLeft, Globe, GraduationCap, Pencil, ScrollText, Users } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { DomainsPanel } from "@/components/org/domains-panel";
import { EditPanel } from "@/components/org/edit-panel";
import { OrgGate, type OrgKind } from "@/components/org/gate";
import { RosterPanel } from "@/components/org/roster-panel";
import { TeamPanel } from "@/components/org/team-panel";
import { OrgLogo } from "@/components/public/org";
import { Section, StaffPage } from "@/components/staff/page";
import { Badge, LinkButton, Skeleton } from "@/components/ui";
import { useOrg, useOrgMembers, useRoster } from "@/lib/api/hooks";
import type { Organization } from "@/lib/api/types";

function Detail({ org }: { org: Organization }) {
  const school = org.type === "school";
  const team = useOrgMembers(org.id, 0);
  const everyone = useRoster(org.id, { unverifiedOnly: false, year: "" }, 0);
  const waiting = useRoster(org.id, { unverifiedOnly: true, year: "" }, 0);
  const tiles = [
    { label: "People with a role", value: team.data?.total ?? "–" },
    ...(school
      ? [
          { label: "Alumni who named this school", value: everyone.data?.total ?? "–" },
          { label: "Waiting for verification", value: waiting.data?.total ?? "–", gold: (waiting.data?.total ?? 0) > 0 },
        ]
      : []),
  ];

  return (
    <StaffPage
      title={org.name}
      subtitle={
        <span className="flex flex-wrap items-center gap-2">
          <OrgLogo org={org} size={28} />
          <Badge tone={school ? "brand" : "gold"}>{school ? "School" : "Partner"}</Badge>
          <span>{org.slug}</span>
        </span>
      }
      tiles={tiles}
      actions={
        <>
          <Link href="/admin/organizations" className="inline-flex min-h-11 items-center gap-1.5 text-small text-muted hover:text-ink">
            <ArrowLeft className="size-4" aria-hidden /> Schools and partners
          </Link>
          <LinkButton href="/admin/activity" variant="secondary"><ScrollText className="size-4" aria-hidden /> Activity log</LinkButton>
        </>
      }
    >
      <Section icon={Pencil} tone="ember" title="Details and logo" hint="What visitors see on the public page.">
        <EditPanel key={`${org.id}-${org.name}-${org.description ?? ""}`} org={org} bare />
      </Section>

      <div className="grid items-start gap-5 xl:grid-cols-2">
        <Section icon={Users} tone="sky" title="Team" hint="Who can help run this organization.">
          <TeamPanel org={org} bare />
        </Section>
        {school && (
          <Section icon={Globe} tone="moss" title="Email domains" hint="Alumni with these email addresses are verified automatically.">
            <DomainsPanel org={org} bare />
          </Section>
        )}
      </div>

      {school && (
        <Section icon={GraduationCap} tone="gold" title="Alumni" hint="Everyone who named this school, and who is waiting to be verified.">
          <RosterPanel org={org} />
        </Section>
      )}
    </StaffPage>
  );
}

export default function AdminOrgDetail() {
  const { id } = useParams<{ id: string }>();
  const org = useOrg(id);
  if (org.isLoading) return <Skeleton className="mx-auto h-48 max-w-3xl rounded-card" />;
  const kind: OrgKind = org.data?.type ?? "school";
  return <OrgGate id={id} kind={kind}>{(o) => <Detail org={o} />}</OrgGate>;
}
