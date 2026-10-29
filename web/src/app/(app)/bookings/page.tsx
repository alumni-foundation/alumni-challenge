"use client";

import { CalendarDays } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { Bar, BarHeader, BarList } from "@/components/home/bars";
import { Badge, EmptyState, ErrorState, LinkButton, PageHeader, Skeleton } from "@/components/ui";
import { BOOKINGS_PAGE_SIZE, useBookings } from "@/lib/api/hooks";
import type { BookingStatus } from "@/lib/api/types";
import { bookingChip, priceText, whenText } from "@/lib/events";
import { cn } from "@/lib/utils";

const COLS = "md:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)_minmax(0,0.7fr)_minmax(0,1fr)_auto]";
const FILTERS: { value: BookingStatus | ""; label: string }[] = [
  { value: "", label: "All" },
  { value: "confirmed", label: "Confirmed" },
  { value: "pending_payment", label: "Held" },
  { value: "waitlisted", label: "Waitlisted" },
  { value: "cancelled", label: "Cancelled" },
  { value: "expired", label: "Expired" },
  { value: "refunded", label: "Refunded" },
];

export default function BookingsPage() {
  const [status, setStatus] = useState<BookingStatus | "">("");
  const [page, setPage] = useState(0);
  const bookings = useBookings(status, page);
  const items = bookings.data?.items ?? [];
  const total = bookings.data?.total ?? null;
  const hasNext = total !== null ? (page + 1) * BOOKINGS_PAGE_SIZE < total : items.length === BOOKINGS_PAGE_SIZE;

  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader
        title="My bookings"
        subtitle="Your places at events."
        actions={<LinkButton href="/events" variant="secondary" size="sm"><CalendarDays className="size-4" aria-hidden /> Browse events</LinkButton>}
      />
      <div role="group" aria-label="Show bookings" className="mb-5 flex flex-wrap gap-2">
        {FILTERS.map((f) => (
          <button
            key={f.value}
            type="button"
            aria-pressed={status === f.value}
            onClick={() => { setStatus(f.value); setPage(0); }}
            className={cn("h-9 rounded-full border px-4 text-small font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink", status === f.value ? "border-ink bg-ink text-white" : "border-line-strong bg-surface text-ink hover:bg-sunken")}
          >
            {f.label}
          </button>
        ))}
      </div>

      {bookings.isError ? (
        <ErrorState onRetry={() => void bookings.refetch()} />
      ) : bookings.isLoading ? (
        <div className="space-y-2" role="status" aria-label="Loading">
          {[0, 1, 2].map((i) => <Skeleton key={i} className="h-16 rounded-2xl" />)}
        </div>
      ) : items.length === 0 ? (
        <EmptyState
          title={status ? "No bookings with that status" : "You haven’t booked anything yet"}
          body={status ? "Try another filter." : "When you reserve a place at an event, it will show up here."}
          action={<LinkButton href="/events" variant="dark" size="sm">Browse events</LinkButton>}
        />
      ) : (
        <>
          <BarHeader columns={COLS} labels={["Event", "When", "People", "Status", ""]} />
          <BarList>
            {items.map((b) => {
              const chip = bookingChip(b.status);
              return (
                <Bar key={b.id} columns={COLS}>
                  <div className="min-w-0">
                    <Link href={`/bookings/${b.id}`} className="block truncate font-semibold hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink">{b.event.title}</Link>
                    <p className="text-caption tracking-wide text-muted">{b.reference}</p>
                  </div>
                  <p className="text-small text-ink">{whenText(b.slot.starts_at)}</p>
                  <p className="text-small text-ink">{b.party_size} · {priceText(b.amount_minor, b.currency)}</p>
                  <div><Badge tone={chip.tone}>{chip.label}</Badge></div>
                  <div><LinkButton href={`/bookings/${b.id}`} variant="dark" size="sm">View</LinkButton></div>
                </Bar>
              );
            })}
          </BarList>
          {(page > 0 || hasNext) && (
            <nav aria-label="Pages" className="mt-6 flex items-center justify-between gap-3">
              <button type="button" disabled={page === 0} onClick={() => setPage((p) => p - 1)} className="inline-flex h-9 items-center rounded-full border border-line-strong px-4 text-small font-medium disabled:opacity-50">Previous</button>
              <span className="text-small text-ink">Page {page + 1}{total !== null ? ` of ${Math.max(1, Math.ceil(total / BOOKINGS_PAGE_SIZE))}` : ""}</span>
              <button type="button" disabled={!hasNext} onClick={() => setPage((p) => p + 1)} className="inline-flex h-9 items-center rounded-full border border-line-strong px-4 text-small font-medium disabled:opacity-50">Next</button>
            </nav>
          )}
        </>
      )}
    </div>
  );
}
