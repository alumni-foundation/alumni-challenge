"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { Dashboard } from "@/components/admin/dashboard/dashboard";
import { Skeleton } from "@/components/ui";
import { useRoles } from "@/lib/api/hooks";
import { canModerate, isPlatformAdmin, landingFor } from "@/lib/roles";

export default function AdminHome() {
  const router = useRouter();
  const roles = useRoles();
  const platform = isPlatformAdmin(roles.data);
  const moderator = !platform && canModerate(roles.data);

  // The dashboard is for platform admins and moderators. Everyone else is sent to their own page.
  useEffect(() => {
    if (roles.data && !platform && !moderator) router.replace(landingFor(roles.data));
  }, [roles.data, platform, moderator, router]);

  if (roles.isLoading || (!platform && !moderator)) {
    return <Skeleton className="h-48 max-w-3xl rounded-card" />;
  }
  return <Dashboard scope={{ kind: platform ? "platform" : "moderator", organizationId: null }} />;
}
