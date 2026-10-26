import { ArrowLeft, CalendarDays, Hash, MapPin, User } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ClaimTicket } from "@/components/events/claim-ticket";
import { TicketQr } from "@/components/events/ticket-qr";
import { Badge, Card, EmptyState, LinkButton } from "@/components/ui";
import { dayText, rangeText, ticketChip } from "@/lib/events";
import { hasSession } from "@/lib/server/auth";
import { fetchTicket } from "@/lib/server/public-api";

// The code in this address is the credential for the ticket: keep the page out of search results and never send the
// address on to other sites. The page is built fresh for every request, so nothing is stored for anyone else.
export const metadata: Metadata = { title: "Ticket", robots: { index: false, follow: false }, referrer: "no-referrer" };
export const dynamic = "force-dynamic";

export default async function TicketPage({ params }: { params: Promise<{ code: string }> }) {
  const { code } = await params;
  const result = await fetchTicket(code);
  if (result.ticket === null) {
    if (result.reason === "missing") notFound();
    return <EmptyState title="We can’t load this ticket right now" body="Please try again in a moment." />;
  }
  const t = result.ticket;
  const signedIn = await hasSession();
  const chip = ticketChip(t.status);
  const active = t.status === "valid";

  return (
    <div className="mx-auto max-w-xl">
      {signedIn && (
        <Link href="/tickets" className="mb-5 inline-flex min-h-11 items-center gap-1.5 text-small font-medium text-ink hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink">
          <ArrowLeft className="size-4" aria-hidden /> My tickets
        </Link>
      )}
      <Card elevation="raised" className="space-y-6 p-6 sm:p-8">
        <div className="space-y-3">
          <Badge tone={chip.tone}>{chip.label}</Badge>
          <h1 className="text-title">{t.event.title}</h1>
        </div>

        <TicketQr code={code} active={active} />

        <ul className="space-y-3 border-t border-line pt-5 text-body text-ink">
          <li className="flex items-start gap-3"><User className="mt-1 size-4 shrink-0 text-muted" aria-hidden /> <span><span className="block text-small text-muted">Ticket holder</span><span className="font-semibold">{t.holder_name}</span></span></li>
          <li className="flex items-start gap-3"><CalendarDays className="mt-1 size-4 shrink-0 text-muted" aria-hidden /> <span><span className="block text-small text-muted">When</span><span className="font-semibold">{dayText(t.slot.starts_at)}</span><span className="block text-small">{rangeText(t.slot.starts_at, t.slot.ends_at)}{t.slot.label ? ` · ${t.slot.label}` : ""}</span></span></li>
          {t.event.venue_name && <li className="flex items-start gap-3"><MapPin className="mt-1 size-4 shrink-0 text-muted" aria-hidden /> <span><span className="block text-small text-muted">Where</span><span className="font-semibold">{t.event.venue_name}</span>{t.event.venue_address && <span className="block text-small">{t.event.venue_address}</span>}</span></li>}
          <li className="flex items-start gap-3"><Hash className="mt-1 size-4 shrink-0 text-muted" aria-hidden /> <span><span className="block text-small text-muted">Booking reference</span><span className="font-semibold tracking-wide">{t.booking_reference}</span></span></li>
        </ul>

        <div className="border-t border-line pt-5">
          {signedIn ? (
            t.claimed ? <p className="text-small text-ink">This ticket is in an account.</p> : <ClaimTicket code={code} />
          ) : (
            <div className="space-y-3">
              <p className="text-small text-ink">Want to keep this ticket in your account? Log in, then open the link from your email again.</p>
              <LinkButton href="/login" variant="secondary" size="sm">Log in</LinkButton>
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}
