"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { DomainsPanel } from "@/components/org/domains-panel";
import { EditPanel } from "@/components/org/edit-panel";
import { OrgGate, OrgHeader, type OrgKind } from "@/components/org/gate";
import { TeamPanel } from "@/components/org/team-panel";
import { Skeleton } from "@/components/ui";
import { useOrg } from "@/lib/api/hooks";

/** The platform admin's view of one organization: the same tools the organization's own admins get. */
function Inner({ id, kind }: { id: string; kind: OrgKind }) {
  return (
    <OrgGate id={id} kind={kind}>
      {(org) => (
        <div className="mx-auto max-w-3xl">
          <Link href="/admin/organizations" className="mb-3 inline-flex min-h-11 items-center gap-1.5 text-small text-muted hover:text-ink">
            <ArrowLeft className="size-4" aria-hidden /> Schools and partners
          </Link>
          <OrgHeader org={org} />
          <div className="space-y-6">
            <EditPanel key={`${org.id}-${org.name}-${org.description ?? ""}`} org={org} />
            <TeamPanel org={org} />
            {org.type === "school" && <DomainsPanel org={org} />}
            <Link href="/admin/activity" className="inline-flex min-h-11 items-center text-small font-medium text-brand-ink hover:underline">See the activity log</Link>
          </div>
        </div>
      )}
    </OrgGate>
  );
}

export default function AdminOrgDetail() {
  const { id } = useParams<{ id: string }>();
  const org = useOrg(id);
  if (org.isLoading) return <Skeleton className="mx-auto h-48 max-w-3xl rounded-card" />;
  return <Inner id={id} kind={org.data?.type ?? "school"} />;
}
