"use client";

import { EmptyState, ErrorState, LinkButton, Skeleton } from "@/components/ui";
import { ApiError } from "@/lib/api/client";
import { useEventToEdit } from "@/lib/api/hooks";
import { EventEditor } from "./event-editor";

/** Loads one event fresh, then hands it to the editor. */
export function EditEvent({ id }: { id: string }) {
  const event = useEventToEdit(id);
  if (event.isLoading) return <Skeleton className="mx-auto h-96 max-w-3xl rounded-[1.75rem]" />;
  if (event.isError) {
    const status = event.error instanceof ApiError ? event.error.status : 0;
    if (status === 404 || status === 422) {
      return <EmptyState title="We can’t find that event" body="It may have been deleted." action={<LinkButton href="/admin/events" variant="secondary">All events</LinkButton>} />;
    }
    return <ErrorState onRetry={() => void event.refetch()} />;
  }
  if (!event.data) return null;
  if (!event.data.can_manage) {
    return <EmptyState title="You can’t edit this event" body="Only the people who run it can." action={<LinkButton href="/events" variant="secondary">See events</LinkButton>} />;
  }
  return <EventEditor key={event.data.id} initial={event.data} />;
}
