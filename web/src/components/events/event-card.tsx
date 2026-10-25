import { CalendarDays, MapPin } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { Badge, LinkButton } from "@/components/ui";
import type { EventSummary } from "@/lib/api/types";
import { dayNumber, monthShort, priceText, seatsText, whenText } from "@/lib/events";

const CATEGORY: Record<string, string> = {
  homecoming: "Homecoming",
  golf_tournament: "Golf",
  sports: "Sports",
  networking: "Networking",
  forum: "Forum",
  mentorship: "Mentorship",
  leadership: "Leadership",
  philanthropy: "Philanthropy",
  other: "Event",
};
export const categoryLabel = (c: string) => CATEGORY[c] ?? "Event";

/** The date as a tile, used wherever there is no poster, so nothing is made up. */
export function DateTile({ iso, className = "" }: { iso: string; className?: string }) {
  return (
    <span className={`flex flex-col items-center justify-center bg-gold-soft text-gold ${className}`} aria-hidden>
      <span className="text-small font-semibold uppercase tracking-widest">{monthShort(iso)}</span>
      <span className="font-serif text-[3.25rem] font-semibold leading-none [font-variant-numeric:lining-nums]">{dayNumber(iso)}</span>
    </span>
  );
}

/** One event in the list: poster (or a date tile), the facts people choose by, and a View pill. */
export function EventCard({ event, ended = false }: { event: EventSummary; ended?: boolean }) {
  const seats = seatsText(event.spots_left);
  const free = event.price_minor <= 0;
  return (
    <article className="relative flex w-full flex-col overflow-hidden rounded-card border border-line bg-surface shadow-resting transition-[transform,box-shadow] duration-200 hover:-translate-y-0.5 hover:shadow-raised motion-reduce:transition-none motion-reduce:hover:translate-y-0">
      <div className="relative aspect-[16/9] w-full overflow-hidden bg-sunken">
        {event.poster_url ? (
          <Image src={event.poster_url} alt="" fill sizes="(min-width: 1280px) 384px, (min-width: 640px) 50vw, 100vw" quality={75} className="object-cover" />
        ) : (
          <DateTile iso={event.starts_at} className="size-full" />
        )}
      </div>
      <div className="flex flex-1 flex-col gap-3 p-5">
        <div className="flex flex-wrap items-center gap-2">
          <Badge>{categoryLabel(event.category)}</Badge>
          <Badge tone={free ? "ok" : "gold"}>{priceText(event.price_minor, event.currency)}</Badge>
          {ended && <Badge>Ended</Badge>}
        </div>
        <h2 className="text-lead font-semibold leading-snug">
          <Link href={`/events/${event.id}`} className="after:absolute after:inset-0 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink">
            {event.title}
          </Link>
        </h2>
        <ul className="space-y-1.5 text-small text-ink">
          <li className="flex items-start gap-2"><CalendarDays className="mt-0.5 size-4 shrink-0 text-muted" aria-hidden /> <span>{whenText(event.starts_at)}</span></li>
          {event.venue_name && <li className="flex items-start gap-2"><MapPin className="mt-0.5 size-4 shrink-0 text-muted" aria-hidden /> <span className="min-w-0">{event.venue_name}</span></li>}
        </ul>
        <div className="mt-auto flex items-center justify-between gap-3 pt-2">
          <span className={`text-small font-semibold ${seats === "Full" ? "text-brand-ink" : "text-ink"}`}>{ended ? "" : seats}</span>
          <LinkButton href={`/events/${event.id}`} variant="dark" size="sm" className="relative z-10">View</LinkButton>
        </div>
      </div>
    </article>
  );
}
