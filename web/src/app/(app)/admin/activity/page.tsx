"use client";

import { ActivityPanel } from "@/components/org/activity-panel";
import { StaffPage } from "@/components/staff/page";
import { EmptyState, Skeleton } from "@/components/ui";
import { useRoles } from "@/lib/api/hooks";
import { canViewAuditLog } from "@/lib/roles";

export default function AuditLogPage() {
  const roles = useRoles();
  if (roles.isLoading) return <Skeleton className="h-40 rounded-card" />;
  if (!canViewAuditLog(roles.data)) {
    return <EmptyState title="You can’t view the activity log" body="It’s open to platform administrators and school or partner admins." />;
  }
  return (
    <StaffPage title="Activity log" subtitle="Who changed what, newest first.">
      <ActivityPanel />
    </StaffPage>
  );
}
