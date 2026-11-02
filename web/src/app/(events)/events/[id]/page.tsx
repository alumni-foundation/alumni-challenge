import type { Metadata } from "next";
import { cache } from "react";
import { notFound } from "next/navigation";
import { EventView } from "@/components/events/event-view";
import { EmptyState } from "@/components/ui";
import { hasSession } from "@/lib/server/auth";
import { fetchEvent } from "@/lib/server/public-api";

// The title and the page both need the event: one call per request.
const load = cache(fetchEvent);

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }): Promise<Metadata> {
  const { id } = await params;
  const result = await load(id);
  return { title: result.event ? result.event.title : "Event" };
}

export default async function EventPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const result = await load(id);
  if (result.event === null) {
    if (result.reason === "missing") notFound();
    return <EmptyState title="We can’t load this event right now" body="Please try again in a moment." />;
  }
  return <EventView initial={result.event} signedIn={await hasSession()} />;
}
