"use client";

import { ArrowLeft, Building2, CalendarDays, Info, Mail, MapPin, Phone } from "lucide-react";
import Link from "next/link";
import { Badge, Card, LinkButton, Skeleton } from "@/components/ui";
import { useEvent, useMe, useMyProfile } from "@/lib/api/hooks";
import type { EventDetail } from "@/lib/api/types";
import { bookingChip, dayText, priceText, rangeText, whenText } from "@/lib/events";
import { BookingForm } from "./booking-form";
import { categoryLabel, DateTile } from "./event-card";
import { HoldCountdown } from "./hold-countdown";
import { SlotPicker } from "./slot-picker";

/** What to say when the event cannot be booked right now. */
function closedMessage(event: EventDetail): string | null {
  const r = event.registration;
  switch (r.state) {
    case "open": return null;
    case "not_open_yet": return r.opens_at ? `Registration opens ${whenText(r.opens_at)}.` : "Registration hasn’t opened yet.";
    case "closed": return "Registration for this event is closed.";
    case "ended": return "This event has finished.";
    case "cancelled": return "This event was cancelled.";
    case "draft": return "This event isn’t open for registration yet.";
    default: return "Registration isn’t open for this event.";
  }
}

function Fact({ icon: Icon, children }: { icon: React.ElementType; children: React.ReactNode }) {
  return (
    <li className="flex items-start gap-3 text-body text-ink">
      <Icon className="mt-1 size-4 shrink-0 text-muted" aria-hidden />
      <span className="min-w-0">{children}</span>
    </li>
  );
}

/** A person who already has a place: say so, with the booking, instead of showing the form again. */
function BookedCard({ event }: { event: EventDetail }) {
  const mine = event.my_booking;
  if (!mine) return null;
  const chip = bookingChip(mine.status);
  return (
    <Card elevation="raised" className="space-y-3 p-5 sm:p-7">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="text-heading">You have a booking</h2>
        <Badge tone={chip.tone}>{chip.label}</Badge>
      </div>
      <p className="text-small text-ink">Reference <strong className="font-semibold tracking-wide">{mine.reference}</strong> · {mine.party_size} {mine.party_size === 1 ? "person" : "people"}</p>
      {mine.status === "pending_payment" && mine.hold_expires_at && <HoldCountdown until={mine.hold_expires_at} />}
      <LinkButton href={`/bookings/${mine.id}`} variant="dark" size="sm">View my booking</LinkButton>
    </Card>
  );
}

/** For someone signed in: the form (or their booking). Their name and email come from their account. */
function MemberPanel({ event }: { event: EventDetail }) {
  const me = useMe();
  const profile = useMyProfile();
  const closed = closedMessage(event);
  if (event.my_booking && ["confirmed", "pending_payment", "waitlisted"].includes(event.my_booking.status)) return <BookedCard event={event} />;
  if (closed) return <Card className="flex items-start gap-3 p-5"><Info className="mt-0.5 size-5 shrink-0 text-muted" aria-hidden /><p className="text-body text-ink">{closed}</p></Card>;
  if (me.isLoading || profile.isLoading) return <Skeleton className="h-64 rounded-card" />;
  return <BookingForm event={event} defaultName={profile.data?.full_name ?? ""} email={me.data?.email ?? ""} />;
}

/** For a visitor: the sessions to look at, and a way to sign in and come back to this page. */
function VisitorPanel({ event }: { event: EventDetail }) {
  const closed = closedMessage(event);
  const here = `/events/${event.id}`;
  return (
    <Card elevation="raised" className="space-y-5 p-5 sm:p-7">
      {event.slots.length > 0 && <SlotPicker slots={event.slots} readOnly />}
      {closed ? (
        <p className="text-body text-ink">{closed}</p>
      ) : (
        <div className="space-y-3 border-t border-line pt-5">
          <h2 className="text-heading">Log in to {event.price_minor > 0 ? "reserve" : "RSVP"}</h2>
          <p className="text-body text-ink">You need an account to book. We’ll bring you straight back here.</p>
          <div className="flex flex-wrap gap-3">
            <LinkButton href={`/login?next=${encodeURIComponent(here)}`} variant="dark">Log in</LinkButton>
            <LinkButton href="/register" variant="secondary">Create an account</LinkButton>
          </div>
        </div>
      )}
    </Card>
  );
}

/** The event page: what it is, when and where, the sessions, and the way to book. */
export function EventView({ initial, signedIn }: { initial: EventDetail; signedIn: boolean }) {
  const query = useEvent(initial.id, { initialData: initial, enabled: signedIn });
  const event = query.data ?? initial;
  const free = event.price_minor <= 0;
  const first = [...event.slots].sort((a, b) => a.starts_at.localeCompare(b.starts_at))[0];
  return (
    <article className="mx-auto max-w-5xl">
      <Link href="/events" className="mb-5 inline-flex min-h-11 items-center gap-1.5 text-small font-medium text-ink hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink">
        <ArrowLeft className="size-4" aria-hidden /> All events
      </Link>

      <div className="overflow-hidden rounded-[1.75rem] border border-line bg-sunken shadow-resting">
        <div className={event.poster_url ? "aspect-[16/9] max-h-[26rem] w-full sm:aspect-[21/9]" : "h-40 w-full sm:h-48"}>
          {event.poster_url ? (
            // eslint-disable-next-line @next/next/no-img-element -- a poster served by the API through our own origin
            <img src={event.poster_url} alt="" width={1200} height={514} className="size-full object-cover" fetchPriority="high" />
          ) : (
            <DateTile iso={event.starts_at} className="size-full" />
          )}
        </div>
      </div>

      <div className="mt-7 grid grid-cols-[minmax(0,1fr)] gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)] lg:items-start">
        <div className="min-w-0 space-y-6">
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <Badge>{categoryLabel(event.category)}</Badge>
              <Badge tone={free ? "ok" : "gold"}>{priceText(event.price_minor, event.currency)}</Badge>
              {event.status === "cancelled" && <Badge tone="brand">Cancelled</Badge>}
            </div>
            <h1 className="text-display">{event.title}</h1>
          </div>
          <ul className="space-y-3">
            <Fact icon={CalendarDays}>
              <span className="block font-semibold">{dayText(event.starts_at)}</span>
              {first && event.slots.length === 1 ? <span className="block text-small text-muted">{rangeText(first.starts_at, first.ends_at)}</span> : <span className="block text-small text-muted">Starts {whenText(event.starts_at).split(", ").pop()}</span>}
            </Fact>
            {event.venue_name && (
              <Fact icon={MapPin}>
                <span className="block font-semibold">{event.venue_name}</span>
                {event.venue_address && <span className="block text-small text-muted">{event.venue_address}</span>}
              </Fact>
            )}
            {event.organizer && <Fact icon={Building2}>Organised by <span className="font-semibold">{event.organizer.name}</span></Fact>}
            {event.contact_email && <Fact icon={Mail}><a href={`mailto:${event.contact_email}`} className="font-medium text-brand-ink hover:underline">{event.contact_email}</a></Fact>}
            {event.contact_phone && <Fact icon={Phone}><a href={`tel:${event.contact_phone}`} className="font-medium text-brand-ink hover:underline">{event.contact_phone}</a></Fact>}
          </ul>
          {event.description && <p className="whitespace-pre-line text-body text-ink">{event.description}</p>}
          {event.refund_policy_text && (
            <div className="rounded-2xl border border-line bg-surface p-4">
              <p className="text-small font-semibold text-ink">Refunds</p>
              <p className="mt-1 whitespace-pre-line text-small text-ink">{event.refund_policy_text}</p>
            </div>
          )}
        </div>
        <div className="min-w-0">{signedIn ? <MemberPanel event={event} /> : <VisitorPanel event={event} />}</div>
      </div>
    </article>
  );
}
