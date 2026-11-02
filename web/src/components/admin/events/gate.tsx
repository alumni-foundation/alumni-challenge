"use client";

import { EmptyState, LinkButton, Skeleton } from "@/components/ui";
import { useRoles } from "@/lib/api/hooks";
import { isOrgAdmin, isPlatformAdmin } from "@/lib/roles";

/**
 * Who may open the event screens: platform admins, and the school and partner admins who run events for their own
 * organization. The server decides what each person can do with a given event; this only spares the rest a pile of errors.
 */
export function EventsGate({ children }: { children: React.ReactNode }) {
  const roles = useRoles();
  if (roles.isLoading) return <Skeleton className="mx-auto h-48 max-w-3xl rounded-[1.75rem]" />;
  if (!isPlatformAdmin(roles.data) && !isOrgAdmin(roles.data)) {
    return (
      <EmptyState
        title="You can’t create events"
        body="Creating and publishing events is for platform admins and the admins of a school or partner."
        action={<LinkButton href="/events" variant="secondary">See events</LinkButton>}
      />
    );
  }
  return <>{children}</>;
}
