"use client";

import { BadgeCheck, CalendarDays, Circle, Search, UserPlus, Users } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { Avatar, Button, Card, LinkButton, Skeleton, VerifiedMark, useToast } from "@/components/ui";
import { Icon3D } from "@/components/ui/icon3d";
import { api } from "@/lib/api/client";
import { friendlyError } from "@/lib/api/messages";
import { NO_FILTERS, useDirectorySearch, useOrgs, useWrite } from "@/lib/api/hooks";
import type { Connection, EventSummary, Profile } from "@/lib/api/types";
import { timeAgo } from "@/lib/notifications";
import { Bar, BarHeader, BarList } from "./bars";

export const VOUCHES_NEEDED = 3;

const cardTitle = "flex items-center gap-3 text-heading";

/** The profile fields people can fill in, and whether each one is filled. The owner sees all of their own. */
export function profileChecklist(p: Profile): { label: string; done: boolean }[] {
  return [
    { label: "your school", done: Boolean(p.school_id) },
    { label: "your graduation year", done: Boolean(p.graduation_year) },
    { label: "your profession", done: Boolean(p.profession) },
    { label: "your company", done: Boolean(p.company) },
    { label: "a short bio", done: Boolean(p.bio) },
    { label: "your skills", done: p.skills.length > 0 },
    { label: "your interests", done: p.interests.length > 0 },
    { label: "a photo", done: Boolean(p.avatar_url) },
  ];
}

function Meter({ value, max, label }: { value: number; max: number; label: string }) {
  return (
    <div role="progressbar" aria-label={label} aria-valuemin={0} aria-valuemax={max} aria-valuenow={value} className="h-2 overflow-hidden rounded-full bg-sunken">
      <div className="h-full rounded-full bg-gold" style={{ width: `${Math.round((value / max) * 100)}%` }} />
    </div>
  );
}

/** A ring drawn from real counts: `value` of `max` done. */
function Ring({ value, max, label }: { value: number; max: number; label: string }) {
  const r = 46;
  const c = 2 * Math.PI * r;
  return (
    <div role="img" aria-label={label} className="relative size-[7.5rem] shrink-0">
      <svg viewBox="0 0 110 110" className="size-full -rotate-90" aria-hidden>
        <circle cx="55" cy="55" r={r} fill="none" strokeWidth="10" className="stroke-sunken" />
        <circle
          cx="55" cy="55" r={r} fill="none" strokeWidth="10" strokeLinecap="round"
          className="stroke-gold transition-[stroke-dashoffset] duration-700 ease-out motion-reduce:transition-none"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - value / max)}
        />
      </svg>
      <div aria-hidden className="absolute inset-0 grid place-items-center text-center">
        <div>
          <span className="font-serif text-[2rem] font-semibold leading-none text-gold [font-variant-numeric:lining-nums]">{value}</span>
          <span className="block text-caption font-medium text-ink">of {max}</span>
        </div>
      </div>
    </div>
  );
}

/* ---- Your profile (ring) ------------------------------------------------------------------- */

export function ProfileRingCard({ profile }: { profile: Profile | null | undefined }) {
  const list = profile ? profileChecklist(profile) : [];
  const done = list.filter((i) => i.done).length;
  const todo = list.filter((i) => !i.done);
  return (
    <Card className="flex flex-col">
      <h2 className={cardTitle}>
        <Icon3D icon={Users} tone="sky" size="sm" /> Your profile
      </h2>
      {profile === undefined ? (
        <Skeleton className="mt-5 h-28" />
      ) : (
        <div className="mt-4 flex flex-1 flex-col gap-4">
          <div className="flex items-center gap-5">
            <Ring value={done} max={list.length} label={`${done} of ${list.length} profile items done`} />
            <div className="min-w-0 text-small text-ink">
              {todo.length === 0 ? (
                <p className="text-body">Your profile is complete. People can find you by school, year, work and skills.</p>
              ) : (
                <>
                  <p className="font-semibold">Still to add</p>
                  <ul className="mt-1.5 space-y-0.5">
                    {todo.slice(0, 3).map((i) => (
                      <li key={i.label}>
                        <Link href="/profile" className="inline-flex min-h-11 items-center gap-2 hover:underline">
                          <Circle className="size-3 shrink-0 text-faint" aria-hidden /> {i.label}
                        </Link>
                      </li>
                    ))}
                  </ul>
                  {todo.length > 3 && <p className="mt-1 text-muted">and {todo.length - 3} more</p>}
                </>
              )}
            </div>
          </div>
          {todo.length > 0 && <LinkButton href="/profile" variant="dark" size="sm" className="mt-auto self-start">Add details</LinkButton>}
        </div>
      )}
    </Card>
  );
}

/* ---- Next event ------------------------------------------------------------------------------ */

const nairobi = (iso: string, opts: Intl.DateTimeFormatOptions) => new Intl.DateTimeFormat("en-KE", { timeZone: "Africa/Nairobi", ...opts }).format(new Date(iso));
const eventWhen = (iso: string) => nairobi(iso, { weekday: "short", day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });

/** "12 seats left", "Full", or nothing when the event has no cap. */
function seatsText(e: EventSummary): string | null {
  if (e.spots_left === null) return null;
  if (e.spots_left <= 0) return "Full";
  return `${e.spots_left} ${e.spots_left === 1 ? "seat" : "seats"} left`;
}

/** The date as a small calendar tile: used where an event has no poster, so nothing is made up. */
function DateTile({ iso }: { iso: string }) {
  return (
    <span className="flex size-20 shrink-0 flex-col items-center justify-center rounded-2xl bg-gold-soft text-gold" aria-hidden>
      <span className="text-caption font-semibold uppercase tracking-wide">{nairobi(iso, { month: "short" })}</span>
      <span className="font-serif text-[2rem] font-semibold leading-none [font-variant-numeric:lining-nums]">{nairobi(iso, { day: "numeric" })}</span>
    </span>
  );
}

export function NextEventCard({ events, loading, failed }: { events: EventSummary[]; loading: boolean; failed: boolean }) {
  const next = events[0];
  return (
    <Card className="flex flex-col">
      <h2 className={cardTitle}>
        <Icon3D icon={CalendarDays} tone="gold" size="sm" /> Next event
      </h2>
      {loading ? (
        <Skeleton className="mt-5 h-28" />
      ) : !next ? (
        <p className="mt-4 text-body text-ink">
          {failed ? "We couldn’t load events just now." : "No events yet. When your school or the community publishes one, it will show up here."}
        </p>
      ) : (
        <div className="mt-4 flex flex-1 flex-col gap-4">
          <div className="flex items-start gap-4">
            {next.poster_url ? (
              <Image src={next.poster_url} alt="" width={80} height={112} quality={75} className="h-28 w-20 shrink-0 rounded-2xl bg-sunken object-cover" />
            ) : (
              <DateTile iso={next.starts_at} />
            )}
            <div className="min-w-0">
              <p className="line-clamp-2 text-lead font-semibold leading-snug">{next.title}</p>
              <p className="mt-1 text-small text-ink">{eventWhen(next.starts_at)}</p>
              {next.venue_name && <p className="truncate text-small text-muted">{next.venue_name}</p>}
              {seatsText(next) && <p className="mt-1 text-small font-semibold text-ink">{seatsText(next)}</p>}
            </div>
          </div>
          <LinkButton href={`/events/${next.id}`} variant="dark" size="sm" className="mt-auto self-start">View</LinkButton>
        </div>
      )}
    </Card>
  );
}

/* ---- People from your school ------------------------------------------------------------------ */

const PEOPLE_COLS = "md:grid-cols-[minmax(0,1.5fr)_minmax(0,1.1fr)_minmax(0,1fr)_auto]";

export function PeopleBars({ profile, connections }: { profile: Profile | null | undefined; connections: Connection[] }) {
  const toast = useToast();
  const schools = useOrgs("school");
  const schoolId = profile?.school_id ?? "";
  const search = useDirectorySearch({ ...NO_FILTERS, schoolId }, 0);
  const connect = useWrite((userId: string) => api("connections", { method: "POST", body: { addressee_id: userId } }), [["connections"], ["directory"]]);
  const schoolName = new Map((schools.data ?? []).map((s) => [s.id, s.name]));

  // Left out: you, people you are already connected to, and people who already asked you. Requests you sent stay, as "Requested".
  const out = new Set(connections.filter((c) => c.status === "accepted" || (c.status === "pending" && c.addressee_id === profile?.user_id)).map((c) => c.other_profile_id));
  const sent = new Set(connections.filter((c) => c.status === "pending" && c.requester_id === profile?.user_id).map((c) => c.other_user_id));
  const people = (search.data?.items ?? []).filter((x) => x.id !== profile?.id && !out.has(x.id)).slice(0, 5);
  const loading = profile === undefined || search.isLoading;

  async function doConnect(userId: string) {
    try {
      await connect.mutateAsync(userId);
      toast("Request sent.");
    } catch (e) {
      toast(friendlyError(e), "info");
    }
  }

  return (
    <section aria-labelledby="people-title">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 id="people-title" className={cardTitle}>
          <Icon3D icon={Users} tone="moss" size="sm" /> {schoolId ? "People from your school" : "People to meet"}
        </h2>
        <Link href="/directory" className="inline-flex min-h-11 items-center text-small font-semibold text-brand-ink hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink">Open the directory</Link>
      </div>
      {loading ? (
        <div className="space-y-2" role="status" aria-label="Loading">
          {[0, 1, 2].map((i) => <Skeleton key={i} className="h-16 rounded-2xl" />)}
        </div>
      ) : people.length === 0 ? (
        <Card className="flex flex-col items-start gap-4">
          <p className="text-body text-ink">
            {schoolId ? "No one else from your school is listed yet. Check back soon, or look through the whole directory." : "No one is listed yet. Check back soon."}
          </p>
          <LinkButton href="/directory" variant="secondary" size="sm"><Search className="size-4" aria-hidden /> Open the directory</LinkButton>
        </Card>
      ) : (
        <>
          <BarHeader columns={PEOPLE_COLS} labels={["Name", "School", "Work", ""]} />
          <BarList>
            {people.map((x) => {
              const school = [x.school_id ? schoolName.get(x.school_id) : null, x.graduation_year && `Class of ${x.graduation_year}`].filter(Boolean).join(" · ");
              const work = [x.profession, x.company].filter(Boolean).join(" at ");
              const requested = sent.has(x.user_id);
              return (
                <Bar key={x.id} columns={PEOPLE_COLS}>
                  <Link href={`/alumni/${x.id}`} className="flex min-h-11 min-w-0 items-center gap-3 rounded-lg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink">
                    <Avatar name={x.full_name} id={x.id} size={40} />
                    <span className="flex min-w-0 items-center gap-1.5 font-semibold"><span className="truncate">{x.full_name}</span>{x.verification_status === "verified" && <VerifiedMark />}</span>
                  </Link>
                  <p className="truncate pl-[3.25rem] text-small text-ink md:pl-0">{school || <span className="text-muted">School not shared</span>}</p>
                  <p className="truncate pl-[3.25rem] text-small text-muted md:pl-0">{work || "—"}</p>
                  <div className="pl-[3.25rem] md:pl-0">
                    {requested ? (
                      <span className="inline-flex h-9 items-center rounded-full bg-sunken px-4 text-small font-medium text-ink">Requested</span>
                    ) : (
                      <Button variant="dark" size="sm" loading={connect.isPending && connect.variables === x.user_id} onClick={() => doConnect(x.user_id)}>
                        <UserPlus className="size-4" aria-hidden /> Connect
                      </Button>
                    )}
                  </div>
                </Bar>
              );
            })}
          </BarList>
        </>
      )}
    </section>
  );
}

/* ---- Connection requests -------------------------------------------------------------------- */

const REQ_COLS = "md:grid-cols-[minmax(0,1fr)_auto]";

export function RequestBars({ requests, loading }: { requests: Connection[]; loading: boolean }) {
  const toast = useToast();
  const refresh = [["connections"], ["blocked"], ["directory"]];
  const accept = useWrite((id: string) => api(`connections/${id}/accept`, { method: "PATCH" }), refresh);
  const decline = useWrite((id: string) => api(`connections/${id}/decline`, { method: "PATCH" }), refresh);

  async function act(fn: () => Promise<unknown>, done: string) {
    try {
      await fn();
      toast(done);
    } catch (e) {
      toast(friendlyError(e), "info");
    }
  }

  const shown = requests.slice(0, 4);
  return (
    <section aria-labelledby="requests-title">
      <h2 id="requests-title" className={`${cardTitle} mb-3`}>
        <Icon3D icon={UserPlus} tone="ember" size="sm" /> Connection requests
      </h2>
      {loading ? (
        <div className="space-y-2" role="status" aria-label="Loading">
          <Skeleton className="h-16 rounded-2xl" />
          <Skeleton className="h-16 rounded-2xl" />
        </div>
      ) : shown.length === 0 ? (
        <Card className="flex flex-col items-start gap-4">
          <p className="text-body text-ink">No one is waiting on you right now. When someone asks to connect, you can accept or decline here.</p>
          <LinkButton href="/directory" variant="secondary" size="sm"><Search className="size-4" aria-hidden /> Find alumni to connect with</LinkButton>
        </Card>
      ) : (
        <>
          <BarList>
            {shown.map((c) => {
              const name = c.other_full_name ?? "Alumni member";
              return (
                <Bar key={c.id} columns={REQ_COLS}>
                  <div className="flex min-w-0 items-center gap-3">
                    <Avatar name={name} id={c.other_user_id} size={40} />
                    <div className="min-w-0">
                      {c.other_profile_id ? (
                        <Link href={`/alumni/${c.other_profile_id}`} className="block truncate font-semibold hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink">{name}</Link>
                      ) : (
                        <span className="block truncate font-semibold">{name}</span>
                      )}
                      <p className="text-caption text-muted">{timeAgo(c.created_at)}</p>
                    </div>
                  </div>
                  <div className="flex gap-2 pl-[3.25rem] md:pl-0">
                    <Button variant="dark" size="sm" loading={accept.isPending && accept.variables === c.id} onClick={() => act(() => accept.mutateAsync(c.id), "You are now connected.")}>Accept</Button>
                    <Button variant="secondary" size="sm" loading={decline.isPending && decline.variables === c.id} onClick={() => act(() => decline.mutateAsync(c.id), "Request declined.")}>Decline</Button>
                  </div>
                </Bar>
              );
            })}
          </BarList>
          {requests.length > shown.length && (
            <Link href="/connections?tab=received" className="mt-1 inline-flex min-h-11 items-center text-small font-semibold text-brand-ink hover:underline">See all {requests.length} requests</Link>
          )}
        </>
      )}
    </section>
  );
}

/* ---- Verification --------------------------------------------------------------------------- */

export function VerificationCard({ profile }: { profile: Profile | null | undefined }) {
  const verified = profile?.verification_status === "verified";
  const vouches = Math.min(profile?.vouch_count ?? 0, VOUCHES_NEEDED);
  return (
    <Card className="flex flex-col">
      <div className="flex items-start justify-between gap-3">
        <h2 className={cardTitle}>
          <Icon3D icon={BadgeCheck} tone="gold" size="sm" /> Verification
        </h2>
        {profile === undefined ? <Skeleton className="h-7 w-24 rounded-full" /> : verified ? (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-gold-soft px-3 py-1 text-small font-semibold text-gold"><VerifiedMark /> Verified</span>
        ) : (
          <span className="rounded-full bg-sunken px-3 py-1 text-small font-medium text-ink">Not yet</span>
        )}
      </div>
      {verified ? (
        <p className="mt-4 text-body text-ink">Your school has confirmed you. Other alumni see a <VerifiedMark /> next to your name.</p>
      ) : (
        <>
          <p className="mt-4 text-body text-ink">A verified mark shows other alumni that you really went to your school. There are three ways to get it:</p>
          <ol className="mt-3 list-decimal space-y-1.5 pl-5 text-small text-ink marker:font-semibold marker:text-gold">
            <li>Sign up with a school email address.</li>
            <li>Ask your school’s administrator to verify you.</li>
            <li>Get vouches from verified alumni of your school.</li>
          </ol>
          {profile && (
            <div className="mt-5">
              <div className="mb-2 flex items-baseline justify-between text-small">
                <span className="font-medium text-ink">Vouches so far</span>
                <span className="font-semibold tabular-nums text-ink">{vouches} of {VOUCHES_NEEDED}</span>
              </div>
              <Meter value={vouches} max={VOUCHES_NEEDED} label="Vouches from verified alumni" />
            </div>
          )}
        </>
      )}
    </Card>
  );
}

/* ---- Upcoming events ------------------------------------------------------------------------ */

const EVENT_COLS = "md:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)_minmax(0,0.8fr)_auto]";

/** Shown when two or more events are published: the same bar style, a View pill on each. */
export function UpcomingEvents({ events }: { events: EventSummary[] }) {
  return (
    <section aria-labelledby="events-title">
      <h2 id="events-title" className={`${cardTitle} mb-3`}>
        <Icon3D icon={CalendarDays} tone="gold" size="sm" /> Upcoming events
      </h2>
      <BarHeader columns={EVENT_COLS} labels={["Event", "When", "Seats", ""]} />
      <BarList>
        {events.map((e) => (
          <Bar key={e.id} columns={EVENT_COLS}>
            <div className="flex min-w-0 items-center gap-3">
              {e.poster_url ? (
                <Image src={e.poster_url} alt="" width={40} height={40} quality={75} className="size-10 shrink-0 rounded-xl bg-sunken object-cover" />
              ) : (
                <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-gold-soft text-gold" aria-hidden><CalendarDays className="size-5" /></span>
              )}
              <span className="truncate font-semibold">{e.title}</span>
            </div>
            <p className="truncate pl-[3.25rem] text-small text-ink md:pl-0">{eventWhen(e.starts_at)}</p>
            <p className="truncate pl-[3.25rem] text-small text-muted md:pl-0">{seatsText(e) ?? e.venue_name ?? "—"}</p>
            <div className="pl-[3.25rem] md:pl-0">
              <LinkButton href={`/events/${e.id}`} variant="dark" size="sm">View</LinkButton>
            </div>
          </Bar>
        ))}
      </BarList>
    </section>
  );
}
