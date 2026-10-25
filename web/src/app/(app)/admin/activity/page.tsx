"use client";

import { ActivityPanel } from "@/components/org/activity-panel";
import { EmptyState, PageHeader, Skeleton } from "@/components/ui";
import { useRoles } from "@/lib/api/hooks";
import { canViewAuditLog } from "@/lib/roles";

export default function AuditLogPage() {
  const roles = useRoles();
  if (roles.isLoading) return <Skeleton className="h-40 max-w-3xl rounded-card" />;
  if (!canViewAuditLog(roles.data)) {
    return <EmptyState title="You can’t view the activity log" body="It’s open to platform administrators and school or partner admins." />;
  }
  return (
    <div className="max-w-3xl">
      <PageHeader title="Activity log" subtitle="Newest first." />
      <ActivityPanel />
    </div>
  );
}
