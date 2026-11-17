"use client";

import { TeamWorkLog } from "@/components/staff/team-work-log";
import { EmptyState, PageHeader, Skeleton } from "@/components/ui";
import { useRoles } from "@/lib/api/hooks";
import { canReadTeamWorkLog } from "@/lib/roles";

export default function TeamWorkLogPage() {
  const roles = useRoles();
  if (roles.isLoading) return <Skeleton className="h-40 max-w-3xl rounded-card" />;
  if (!canReadTeamWorkLog(roles.data)) {
    return <EmptyState title="You can’t see the team work log" body="Only super admins can read it." />;
  }
  return (
    <>
      <PageHeader title="Team work log" subtitle="What admins and moderators are planning and finishing. You can read it, not change it." />
      <TeamWorkLog />
    </>
  );
}
