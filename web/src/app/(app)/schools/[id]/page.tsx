"use client";

import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Building2, ShieldCheck } from "lucide-react";
import { Badge, Card, EmptyState, Spinner } from "@/components/ui";
import { useOrg, useRoles } from "@/lib/api/hooks";
import { canManageOrg } from "@/lib/roles";

export default function SchoolDetail() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const org = useOrg(id);
  const roles = useRoles();

  if (org.isLoading) return <Spinner label="Loading school" />;
  if (org.isError || !org.data) return <EmptyState title="School not found" />;
  const canManage = canManageOrg(roles.data, org.data.id);

  return (
    <div className="mx-auto max-w-2xl">
      <button onClick={() => router.back()} className="mb-4 flex items-center gap-1 text-sm text-muted hover:text-ink">
        <ArrowLeft className="size-4" /> Back
      </button>
      <Card>
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            <span className="flex size-14 items-center justify-center rounded-xl bg-brand-soft text-brand"><Building2 className="size-7" /></span>
            <div>
              <h1 className="text-xl font-bold">{org.data.name}</h1>
              <Badge tone={org.data.status === "active" ? "ok" : "neutral"}>{org.data.status}</Badge>
            </div>
          </div>
          {canManage && <Badge tone="brand"><ShieldCheck className="mr-1 inline size-3" />You manage this</Badge>}
        </div>
        {org.data.description && <p className="mt-4 text-sm leading-relaxed">{org.data.description}</p>}
      </Card>
    </div>
  );
}
