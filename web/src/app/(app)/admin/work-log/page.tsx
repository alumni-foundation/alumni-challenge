"use client";

import { MyWorkLog } from "@/components/staff/my-work-log";
import { EmptyState, PageHeader, Skeleton } from "@/components/ui";
import { useRoles } from "@/lib/api/hooks";
import { canKeepWorkLog } from "@/lib/roles";

export default function MyWorkLogPage() {
  const roles = useRoles();
  if (roles.isLoading) return <Skeleton className="h-40 max-w-3xl rounded-card" />;
  if (!canKeepWorkLog(roles.data)) {
    return <EmptyState title="You don’t have a work log" body="It’s for platform admins and moderators. Super admins can read everyone’s in the team work log." />;
  }
  return (
    <>
      <PageHeader title="My work log" subtitle="Plan your day and tick things off. Only you and the super admins can see it." />
      <MyWorkLog />
    </>
  );
}
