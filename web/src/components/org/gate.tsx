"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { Badge, EmptyState, ErrorState, LinkButton, Skeleton } from "@/components/ui";
import { OrgLogo } from "@/components/public/org";
import { useOrg, useRoles } from "@/lib/api/hooks";
import type { Organization } from "@/lib/api/types";
import { canManageOrg } from "@/lib/roles";

export type OrgKind = "school" | "partner";

/**
 * Loads one organization and checks the signed-in person may manage it before showing anything.
 * The server enforces this too; the check just means people see a clear message, not a pile of errors.
 */
export function OrgGate({ id, kind, children }: { id: string; kind: OrgKind; children: (org: Organization) => React.ReactNode }) {
  const org = useOrg(id);
  const roles = useRoles();

  if (org.isLoading || roles.isLoading) {
    return (
      <div className="max-w-3xl space-y-4" role="status" aria-label="Loading">
        <Skeleton className="h-16 rounded-card" />
        <Skeleton className="h-48 rounded-card" />
      </div>
    );
  }
  const back = <LinkButton href="/start" variant="secondary">Go to my home</LinkButton>;
  if (org.isError && (org.error as { status?: number }).status !== 404) {
    return <ErrorState onRetry={() => void org.refetch()} />;
  }
  if (org.isError || !org.data || org.data.type !== kind) {
    return <EmptyState title={`We can’t find that ${kind}.`} action={back} />;
  }
  if (!canManageOrg(roles.data, org.data.id)) {
    return <EmptyState title="You can’t manage this organization" body="Only its admins and platform administrators can." action={back} />;
  }
  return <>{children(org.data)}</>;
}

/** Name and logo at the top of every school or partner screen, with a way back to the overview. */
export function OrgHeader({ org, title, subtitle, back }: { org: Organization; title?: string; subtitle?: string; back?: { href: string; label: string } }) {
  return (
    <div className="mb-6">
      {back && (
        <Link href={back.href} className="mb-3 inline-flex min-h-11 items-center gap-1.5 text-small text-muted hover:text-ink">
          <ArrowLeft className="size-4" aria-hidden /> {back.label}
        </Link>
      )}
      <div className="flex items-center gap-4">
        <OrgLogo org={org} size={56} />
        <div className="min-w-0">
          <h1 className="text-title">{title ?? org.name}</h1>
          <p className="flex flex-wrap items-center gap-2 text-small text-muted">
            {subtitle ?? (title ? org.name : null)}
            <Badge tone={org.type === "school" ? "brand" : "gold"}>{org.type === "school" ? "School" : "Partner"}</Badge>
          </p>
        </div>
      </div>
    </div>
  );
}
