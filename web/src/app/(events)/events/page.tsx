import { CalendarX2, Ticket } from "lucide-react";
import type { Metadata } from "next";
import { EventCard } from "@/components/events/event-card";
import { EventFilterBar, type EventFilters } from "@/components/events/event-filters";
import { EmptyState, LinkButton } from "@/components/ui";
import { hasSession } from "@/lib/server/auth";
import { fetchEvents } from "@/lib/server/public-api";

export const metadata: Metadata = { title: "Events" };

const PAGE_SIZE = 12;
const one = (v: string | string[] | undefined) => (Array.isArray(v) ? v[0] : v) ?? "";

export default async function EventsPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const sp = await searchParams;
  const filters: EventFilters = {
    when: one(sp.when) === "past" ? "past" : "upcoming",
    price: one(sp.price) === "free" ? "free" : one(sp.price) === "paid" ? "paid" : "all",
    q: one(sp.q).slice(0, 100),
  };
  const page = Math.max(1, Number.parseInt(one(sp.p), 10) || 1);
  const signedIn = await hasSession();
  const all = await fetchEvents({ past: filters.when === "past", q: filters.q });
  // The API has no price filter, so free and paid are picked here from what it returned.
  const matching = (all ?? []).filter((e) => (filters.price === "free" ? e.price_minor <= 0 : filters.price === "paid" ? e.price_minor > 0 : true));
  const shown = matching.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
  const pages = Math.max(1, Math.ceil(matching.length / PAGE_SIZE));
  const filtered = Boolean(filters.q) || filters.price !== "all";

  const link = (p: number) => {
    const params = new URLSearchParams();
    if (filters.when !== "upcoming") params.set("when", filters.when);
    if (filters.price !== "all") params.set("price", filters.price);
    if (filters.q) params.set("q", filters.q);
    if (p > 1) params.set("p", String(p));
    return params.size ? `/events?${params}` : "/events";
  };

  return (
    <div className="mx-auto max-w-6xl">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-title">Events</h1>
          <p className="mt-1 text-body text-ink">Golf days, meetups and evenings with your school family.</p>
        </div>
        {signedIn && (
          <div className="flex gap-2">
            <LinkButton href="/bookings" variant="secondary" size="sm">My bookings</LinkButton>
            <LinkButton href="/tickets" variant="secondary" size="sm"><Ticket className="size-4" aria-hidden /> My tickets</LinkButton>
          </div>
        )}
      </div>
      <EventFilterBar filters={filters} />
      {all === null ? (
        <EmptyState title="We can’t load events right now" body="Please try again in a moment." />
      ) : shown.length === 0 ? (
        <EmptyState
          title={filtered ? "No events match that" : filters.when === "past" ? "No past events yet" : "No events yet"}
          body={filtered ? "Try another word, or clear the filters." : filters.when === "past" ? "Events that have finished will be listed here." : "When your school or the community publishes one, it will show up here."}
          action={filtered || filters.when === "past" ? <LinkButton href="/events" variant="secondary" size="sm"><CalendarX2 className="size-4" aria-hidden /> Show upcoming events</LinkButton> : undefined}
        />
      ) : (
        <>
          <ul className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
            {shown.map((e) => (
              <li key={e.id} className="flex">
                <EventCard event={e} ended={filters.when === "past"} />
              </li>
            ))}
          </ul>
          {pages > 1 && (
            <nav aria-label="Pages" className="mt-8 flex items-center justify-between gap-3">
              {page > 1 ? <LinkButton href={link(page - 1)} variant="secondary" size="sm">Previous</LinkButton> : <span />}
              <span className="text-small text-ink">Page {page} of {pages}</span>
              {page < pages ? <LinkButton href={link(page + 1)} variant="secondary" size="sm">Next</LinkButton> : <span />}
            </nav>
          )}
        </>
      )}
    </div>
  );
}
