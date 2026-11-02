"use client";

import { Ticket as TicketIcon } from "lucide-react";
import Link from "next/link";
import { Bar, BarHeader, BarList } from "@/components/home/bars";
import { Badge, EmptyState, ErrorState, LinkButton, PageHeader, Skeleton } from "@/components/ui";
import { useMyTickets } from "@/lib/api/hooks";
import { rangeText, ticketChip, whenText } from "@/lib/events";

const COLS = "md:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,0.8fr)_auto]";

/** My tickets: every ticket for an event that has not ended, whether I booked it or claimed it from an email. */
export default function TicketsPage() {
  const tickets = useMyTickets();
  const items = tickets.data ?? [];
  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader
        title="My tickets"
        subtitle="Show the QR code at the entrance."
        actions={<LinkButton href="/bookings" variant="secondary" size="sm">My bookings</LinkButton>}
      />
      {tickets.isError ? (
        <ErrorState onRetry={() => void tickets.refetch()} />
      ) : tickets.isLoading ? (
        <div className="space-y-2" role="status" aria-label="Loading">
          {[0, 1, 2].map((i) => <Skeleton key={i} className="h-16 rounded-2xl" />)}
        </div>
      ) : items.length === 0 ? (
        <EmptyState
          title="No tickets yet"
          body="Your tickets appear here once a booking is confirmed. Free events confirm straight away."
          action={<LinkButton href="/events" variant="dark" size="sm"><TicketIcon className="size-4" aria-hidden /> Browse events</LinkButton>}
        />
      ) : (
        <>
          <BarHeader columns={COLS} labels={["Event", "When", "Holder", "Status", ""]} />
          <BarList>
            {items.map((t) => {
              const chip = ticketChip(t.status);
              // The ticket page is the one place the code may appear in an address. Not prefetched, so no needless calls.
              const href = `/tickets/${t.code}`;
              return (
                <Bar key={t.code} columns={COLS}>
                  <Link href={href} prefetch={false} className="min-w-0 truncate font-semibold hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink">{t.event.title}</Link>
                  <div className="text-small text-ink">
                    <p>{whenText(t.slot.starts_at)}</p>
                    <p className="text-caption text-muted">{rangeText(t.slot.starts_at, t.slot.ends_at)}{t.slot.label ? ` · ${t.slot.label}` : ""}</p>
                  </div>
                  <p className="truncate text-small text-ink">{t.holder_name}</p>
                  <div><Badge tone={chip.tone}>{chip.label}</Badge></div>
                  <div><LinkButton href={href} prefetch={false} variant="dark" size="sm">Show ticket</LinkButton></div>
                </Bar>
              );
            })}
          </BarList>
        </>
      )}
    </div>
  );
}
