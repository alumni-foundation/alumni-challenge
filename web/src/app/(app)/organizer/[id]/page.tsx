"use client";

import { CalendarDays, ChevronRight } from "lucide-react";
import Link from "next/link";
import { use } from "react";
import { Dashboard } from "@/components/admin/dashboard/dashboard";
import { EmptyState, ErrorState, Icon3D, LinkButton, Skeleton } from "@/components/ui";
import { useOrg, useRoles } from "@/lib/api/hooks";

/** An event manager's own organization: the same dashboard as its admins, without the admin-only links. */
export default function OrganizerPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const roles = useRoles();
  const org = useOrg(id);
  if (roles.isLoading || org.isLoading) return <Skeleton className="h-48 max-w-3xl rounded-[1.75rem]" />;
  if (org.isError && (org.error as { status?: number }).status !== 404) return <ErrorState onRetry={() => void org.refetch()} />;
  const mine = (roles.data ?? []).some((m) => m.organization_id === id && m.role === "event_manager");
  if (!org.data || !mine) {
    return <EmptyState title="We can’t find that organization" body="This page is for the event managers of an organization." action={<LinkButton href="/start" variant="secondary">Go to my home</LinkButton>} />;
  }
  return (
    <div className="mx-auto max-w-[1280px] space-y-8">
      <Dashboard scope={{ kind: "organizer", organizationId: org.data.id }} org={org.data} />
      <section aria-label="Manage" className="space-y-3">
        <h2 className="text-lead font-semibold">Your events</h2>
        <Link href="/events" className="flex min-h-16 max-w-xl items-center gap-4 rounded-2xl border border-line bg-surface px-4 py-3 shadow-resting transition-[transform,box-shadow] duration-200 hover:-translate-y-0.5 hover:shadow-raised focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink motion-reduce:transition-none">
          <Icon3D icon={CalendarDays} tone="gold" size="sm" />
          <span className="min-w-0 flex-1">
            <span className="block font-semibold">Events</span>
            <span className="mt-0.5 block text-small text-muted">See what is on and who has booked. Screens for organizing events come next.</span>
          </span>
          <ChevronRight className="size-5 shrink-0 text-faint" aria-hidden />
        </Link>
      </section>
    </div>
  );
}
