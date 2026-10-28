"use client";

import { CalendarDays, CalendarPlus, ChevronRight } from "lucide-react";
import Image from "next/image";
import { useState } from "react";
import { Row, RowList } from "@/components/staff/rows";
import { categoryLabel } from "@/components/events/event-card";
import { Badge, Button, EmptyState, ErrorState, Icon3D, LinkButton, PageHeader, Skeleton } from "@/components/ui";
import { MANAGED_EVENTS_PAGE_SIZE, useManagedEvents, useRoles } from "@/lib/api/hooks";
import type { EventStatus } from "@/lib/api/types";
import { whenText } from "@/lib/events";
import { isPlatformAdmin } from "@/lib/roles";

const STATUS: Record<EventStatus, { label: string; tone: "neutral" | "ok" | "warn" | "danger" | "blue" }> = {
  draft: { label: "Draft", tone: "neutral" },
  published: { label: "Published", tone: "ok" },
  closed: { label: "Registration closed", tone: "warn" },
  cancelled: { label: "Cancelled", tone: "danger" },
  completed: { label: "Completed", tone: "blue" },
};

/** Every event this person runs, drafts included, with a way to start a new one. */
export function EventList() {
  const [page, setPage] = useState(0);
  const roles = useRoles();
  const events = useManagedEvents(page);
  const total = events.data?.total ?? null;
  const rows = events.data?.items ?? [];
  const hasNext = total !== null ? (page + 1) * MANAGED_EVENTS_PAGE_SIZE < total : rows.length === MANAGED_EVENTS_PAGE_SIZE;

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader
        title="Events"
        subtitle={isPlatformAdmin(roles.data) ? "Every event on the platform, drafts included." : "The events you run, drafts included."}
        actions={<LinkButton href="/admin/events/new" variant="dark"><CalendarPlus className="size-4" aria-hidden /> Create event</LinkButton>}
      />
      {events.isLoading ? (
        <div className="space-y-2" role="status" aria-label="Loading events">
          {[0, 1, 2].map((i) => <Skeleton key={i} className="h-16 rounded-2xl" />)}
        </div>
      ) : events.isError ? (
        <ErrorState onRetry={() => void events.refetch()} />
      ) : rows.length === 0 ? (
        <EmptyState
          title="No events yet"
          body="Create the first one. It starts as a draft that only you can see."
          action={<LinkButton href="/admin/events/new" variant="dark">Create event</LinkButton>}
        />
      ) : (
        <>
          <RowList label="Events">
            {rows.map((e) => {
              const s = STATUS[e.status];
              return (
                <Row key={e.id} href={`/admin/events/${e.id}`}>
                  {e.poster_url ? (
                    <span className="relative aspect-[16/9] w-20 shrink-0 overflow-hidden rounded-lg bg-sunken sm:w-24">
                      <Image src={e.poster_url} alt="" fill sizes="96px" quality={60} className="object-cover" />
                    </span>
                  ) : (
                    <Icon3D icon={CalendarDays} tone="gold" size="sm" />
                  )}
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-semibold">{e.title}</span>
                    <span className="mt-0.5 block truncate text-small text-muted">
                      {whenText(e.starts_at)} · {categoryLabel(e.category)} · {e.organizer?.name ?? "Platform"}
                    </span>
                  </span>
                  <Badge tone={s.tone}>{s.label}</Badge>
                  <ChevronRight className="size-5 shrink-0 text-faint" aria-hidden />
                </Row>
              );
            })}
          </RowList>
          {(page > 0 || hasNext) && (
            <div className="mt-4 flex items-center justify-between gap-3">
              <Button variant="secondary" size="sm" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>Previous</Button>
              <span className="text-small text-muted">Page {page + 1}{total !== null ? ` of ${Math.max(1, Math.ceil(total / MANAGED_EVENTS_PAGE_SIZE))}` : ""}</span>
              <Button variant="secondary" size="sm" disabled={!hasNext} onClick={() => setPage((p) => p + 1)}>Next</Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
