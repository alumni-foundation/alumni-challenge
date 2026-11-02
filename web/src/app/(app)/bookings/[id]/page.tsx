"use client";

import { useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, CalendarDays, CheckCircle2, CreditCard, MapPin, Users } from "lucide-react";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { HoldCountdown } from "@/components/events/hold-countdown";
import { Alert, Badge, Button, Card, ConfirmDialog, EmptyState, ErrorState, LinkButton, Skeleton, useToast } from "@/components/ui";
import { ApiError, api } from "@/lib/api/client";
import { useBooking, useBookingTickets } from "@/lib/api/hooks";
import type { Booking } from "@/lib/api/types";
import { bookingChip, dayText, priceText, rangeText, ticketChip } from "@/lib/events";

function Tickets({ booking }: { booking: Booking }) {
  const tickets = useBookingTickets(booking.id, booking.status === "confirmed");
  return (
    <Card className="p-5 sm:p-6">
      <h2 className="text-heading">{booking.party_size > 1 ? "Tickets" : "Your ticket"}</h2>
      {tickets.isLoading ? (
        <Skeleton className="mt-4 h-16 rounded-2xl" />
      ) : tickets.isError ? (
        <p className="mt-3 text-body text-ink">We couldn’t load the tickets just now. <button type="button" className="font-semibold text-brand-ink underline" onClick={() => void tickets.refetch()}>Try again</button></p>
      ) : (
        <ul className="mt-3 divide-y divide-line">
          {(tickets.data ?? []).map((t) => {
            const chip = ticketChip(t.status);
            return (
              <li key={t.code} className="flex flex-wrap items-center gap-3 py-3">
                <div className="min-w-0 flex-1">
                  <p className="truncate font-semibold">{t.holder_name}</p>
                  <p className="mt-0.5"><Badge tone={chip.tone}>{chip.label}</Badge></p>
                </div>
                <LinkButton href={`/tickets/${t.code}`} prefetch={false} variant="dark" size="sm">Show ticket</LinkButton>
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}

function BookingDetail() {
  const { id } = useParams<{ id: string }>();
  const fresh = useSearchParams().get("new") === "1";
  const qc = useQueryClient();
  const toast = useToast();
  const query = useBooking(id);
  const [cancelling, setCancelling] = useState(false);
  const b = query.data;

  if (query.isLoading) return <div className="mx-auto max-w-3xl space-y-4" role="status" aria-label="Loading booking"><Skeleton className="h-8 w-40" /><Skeleton className="h-64 rounded-card" /></div>;
  if (query.isError || !b) {
    const missing = query.error instanceof ApiError && query.error.status === 404;
    return (
      <div className="mx-auto max-w-3xl">
        {missing ? <EmptyState title="We can’t find that booking" body="It may belong to someone else, or it no longer exists." action={<LinkButton href="/bookings" variant="secondary" size="sm">My bookings</LinkButton>} /> : <ErrorState onRetry={() => void query.refetch()} />}
      </div>
    );
  }

  const chip = bookingChip(b.status);
  const paid = b.amount_minor > 0;
  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ["booking", b.id] });
    void qc.invalidateQueries({ queryKey: ["bookings"] });
    void qc.invalidateQueries({ queryKey: ["event", b.event.id] });
    void qc.invalidateQueries({ queryKey: ["tickets"] });
  };

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <Link href="/bookings" className="inline-flex min-h-11 items-center gap-1.5 text-small font-medium text-ink hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink">
        <ArrowLeft className="size-4" aria-hidden /> My bookings
      </Link>

      {fresh && b.status === "confirmed" && (
        <Alert tone="ok"><p className="flex items-center gap-2 font-semibold"><CheckCircle2 className="size-4" aria-hidden /> You’re in. Your place is confirmed.</p><p className="mt-0.5">Your ticket is below. We also emailed it to you.</p></Alert>
      )}
      {fresh && b.status === "pending_payment" && (
        <Alert tone="warn"><p className="font-semibold">Your places are held.</p><p className="mt-0.5">They are yours until the time below. A booking is only confirmed once it is paid.</p></Alert>
      )}

      <Card elevation="raised" className="space-y-5 p-5 sm:p-7">
        <div className="flex flex-wrap items-center gap-3">
          <Badge tone={chip.tone}>{chip.label}</Badge>
          <span className="text-small tracking-wide text-muted">Reference <strong className="font-semibold text-ink">{b.reference}</strong></span>
        </div>
        <h1 className="text-title">
          <Link href={`/events/${b.event.id}`} className="hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink">{b.event.title}</Link>
        </h1>
        <ul className="space-y-3 text-body text-ink">
          <li className="flex items-start gap-3"><CalendarDays className="mt-1 size-4 shrink-0 text-muted" aria-hidden /> <span><span className="block font-semibold">{dayText(b.slot.starts_at)}</span><span className="block text-small">{rangeText(b.slot.starts_at, b.slot.ends_at)}{b.slot.label ? ` · ${b.slot.label}` : ""}</span></span></li>
          {b.event.venue_name && <li className="flex items-start gap-3"><MapPin className="mt-1 size-4 shrink-0 text-muted" aria-hidden /> <span className="font-semibold">{b.event.venue_name}</span></li>}
          <li className="flex items-start gap-3"><Users className="mt-1 size-4 shrink-0 text-muted" aria-hidden /> <span><span className="font-semibold">{b.party_size} {b.party_size === 1 ? "person" : "people"}</span><span className="block text-small">{b.participants.map((p) => p.full_name).join(", ")}</span></span></li>
          <li className="flex items-start gap-3"><CreditCard className="mt-1 size-4 shrink-0 text-muted" aria-hidden /> <span><span className="font-semibold">{priceText(b.amount_minor, b.currency)}</span>{paid && <span className="block text-small">{b.party_size} × {priceText(b.unit_price_minor, b.currency)}</span>}</span></li>
        </ul>
      </Card>

      {b.status === "pending_payment" && (
        <Card className="space-y-4 p-5 sm:p-7">
          <h2 className="text-heading">Seats held</h2>
          {b.hold_expires_at && <HoldCountdown until={b.hold_expires_at} onExpire={refresh} />}
          <div className="rounded-2xl border border-dashed border-line-strong bg-canvas/60 p-4">
            <p className="text-small font-semibold text-ink">Payment</p>
            <p className="mt-1 text-body text-ink">Amount to pay: <strong className="font-semibold">{priceText(b.amount_minor, b.currency)}</strong></p>
            <p className="mt-2 text-small text-muted">Payment instructions will appear here. (Not available yet: nothing on this page takes a payment.)</p>
          </div>
        </Card>
      )}

      {b.status === "confirmed" && <Tickets booking={b} />}

      {(b.status === "cancelled" || b.status === "expired" || b.status === "refunded") && (
        <Card className="space-y-3 p-5 sm:p-6">
          <p className="text-body text-ink">
            {b.status === "expired" ? "The hold ran out before this booking was paid, so the places were released." : b.status === "refunded" ? "This booking was refunded." : "This booking was cancelled."}
            {b.cancel_reason ? ` Reason: ${b.cancel_reason}` : ""}
          </p>
          <LinkButton href={`/events/${b.event.id}`} variant="secondary" size="sm">See the event</LinkButton>
        </Card>
      )}

      {b.can_cancel ? (
        <div>
          <Button variant="secondary" onClick={() => setCancelling(true)}>Cancel booking</Button>
          <ConfirmDialog
            open={cancelling}
            title="Cancel this booking?"
            body={`Your ${b.party_size === 1 ? "place" : `${b.party_size} places`} will be given back to other people.${b.status === "pending_payment" ? " Nothing has been charged." : ""}`}
            confirmLabel="Cancel booking"
            danger
            onClose={() => setCancelling(false)}
            onConfirm={async () => {
              await api(`bookings/${b.id}/cancel`, { method: "POST", body: {} });
              refresh();
              toast("Booking cancelled.");
            }}
          />
        </div>
      ) : (
        b.status === "confirmed" && paid && <p className="text-small text-ink">To cancel a paid booking, please contact the organizers of the event.</p>
      )}
    </div>
  );
}

export default function BookingPage() {
  return <Suspense><BookingDetail /></Suspense>;
}
