"use client";

import { BadgeCheck, Circle, Search, UserPlus, Users } from "lucide-react";
import Link from "next/link";
import { Avatar, Button, Card, LinkButton, Skeleton, VerifiedMark, useToast } from "@/components/ui";
import { Icon3D } from "@/components/ui/icon3d";
import { api } from "@/lib/api/client";
import { friendlyError } from "@/lib/api/messages";
import { NO_FILTERS, useDirectorySearch, useWrite } from "@/lib/api/hooks";
import type { Connection, Profile } from "@/lib/api/types";

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

/* ---- Requests waiting for you ------------------------------------------------------------- */

export function RequestsCard({ requests, loading }: { requests: Connection[]; loading: boolean }) {
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

  const shown = requests.slice(0, 3);
  return (
    <Card className="flex flex-col">
      <h2 className={cardTitle}>
        <Icon3D icon={UserPlus} tone="ember" size="sm" /> Connection requests
      </h2>
      {loading ? (
        <div className="mt-5 space-y-3" role="status" aria-label="Loading">
          <Skeleton className="h-14" />
          <Skeleton className="h-14" />
        </div>
      ) : shown.length === 0 ? (
        <div className="mt-4 flex flex-1 flex-col items-start gap-4">
          <p className="text-body text-ink">No one is waiting on you right now. When someone asks to connect, you can accept or decline here.</p>
          <LinkButton href="/directory" variant="secondary" size="sm"><Search className="size-4" aria-hidden /> Find alumni to connect with</LinkButton>
        </div>
      ) : (
        <>
          <ul className="mt-3 divide-y divide-line">
            {shown.map((c) => {
              const name = c.other_full_name ?? "Alumni member";
              return (
                <li key={c.id} className="flex flex-col gap-3 py-3.5 sm:flex-row sm:items-center">
                  <div className="flex min-w-0 flex-1 items-center gap-3">
                    <Avatar name={name} id={c.other_user_id} size={44} />
                    {c.other_profile_id ? (
                      <Link href={`/alumni/${c.other_profile_id}`} className="inline-flex min-h-11 min-w-0 items-center truncate font-semibold hover:underline">{name}</Link>
                    ) : (
                      <span className="min-w-0 truncate font-semibold">{name}</span>
                    )}
                  </div>
                  <div className="flex gap-2 sm:shrink-0">
                    <Button variant="dark" size="sm" loading={accept.isPending && accept.variables === c.id} onClick={() => act(() => accept.mutateAsync(c.id), "You are now connected.")}>Accept</Button>
                    <Button variant="secondary" size="sm" loading={decline.isPending && decline.variables === c.id} onClick={() => act(() => decline.mutateAsync(c.id), "Request declined.")}>Decline</Button>
                  </div>
                </li>
              );
            })}
          </ul>
          {requests.length > shown.length && (
            <Link href="/connections?tab=received" className="mt-1 inline-flex min-h-11 items-center text-small font-semibold text-brand-ink hover:underline">
              See all {requests.length} requests
            </Link>
          )}
        </>
      )}
    </Card>
  );
}

/* ---- Verification ---------------------------------------------------------------------------- */

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

/* ---- Complete your profile ------------------------------------------------------------------- */

export function ProfileCard({ profile }: { profile: Profile | null | undefined }) {
  const list = profile ? profileChecklist(profile) : [];
  const done = list.filter((i) => i.done).length;
  const todo = list.filter((i) => !i.done);
  return (
    <Card className="flex flex-col">
      <h2 className={cardTitle}>
        <Icon3D icon={Users} tone="sky" size="sm" /> Your profile
      </h2>
      {profile === undefined ? (
        <Skeleton className="mt-5 h-24" />
      ) : todo.length === 0 ? (
        <p className="mt-4 text-body text-ink">Your profile is complete. People can find you by school, year, work and skills.</p>
      ) : (
        <>
          <div className="mt-4">
            <div className="mb-2 flex items-baseline justify-between text-small">
              <span className="font-medium text-ink">Still to add</span>
              <span className="font-semibold tabular-nums text-ink">{done} of {list.length} done</span>
            </div>
            <Meter value={done} max={list.length} label="Profile completeness" />
          </div>
          <ul className="mb-4 mt-4 grid gap-x-4 gap-y-1 text-small text-ink sm:grid-cols-2">
            {todo.slice(0, 6).map((i) => (
              <li key={i.label}>
                <Link href="/profile" className="inline-flex min-h-9 items-center gap-2 hover:underline">
                  <Circle className="size-3.5 text-faint" aria-hidden /> {i.label}
                </Link>
              </li>
            ))}
          </ul>
          <LinkButton href="/profile" variant="dark" size="sm" className="self-start">Add details</LinkButton>
        </>
      )}
    </Card>
  );
}

/* ---- People to meet ------------------------------------------------------------------------- */

export function PeopleCard({ profile, connections }: { profile: Profile | null | undefined; connections: Connection[] }) {
  const schoolId = profile?.school_id ?? "";
  const search = useDirectorySearch({ ...NO_FILTERS, schoolId }, 0);
  const known = new Set(connections.map((c) => c.other_profile_id));
  const people = (search.data?.items ?? []).filter((x) => x.id !== profile?.id && !known.has(x.id)).slice(0, 4);
  const loading = profile === undefined || search.isLoading;
  return (
    <Card className="flex flex-col">
      <h2 className={cardTitle}>
        <Icon3D icon={Users} tone="moss" size="sm" /> {schoolId ? "From your school" : "People to meet"}
      </h2>
      {loading ? (
        <div className="mt-5 space-y-3" role="status" aria-label="Loading">
          <Skeleton className="h-12" />
          <Skeleton className="h-12" />
          <Skeleton className="h-12" />
        </div>
      ) : people.length === 0 ? (
        <div className="mt-4 flex flex-col items-start gap-4">
          <p className="text-body text-ink">
            {schoolId ? "No one else from your school is listed yet. Check back soon, or look through the whole directory." : "No one is listed yet. Check back soon."}
          </p>
          <LinkButton href="/directory" variant="secondary" size="sm"><Search className="size-4" aria-hidden /> Open the directory</LinkButton>
        </div>
      ) : (
        <>
          <ul className="mt-3 divide-y divide-line">
            {people.map((x) => {
              const meta = [x.profession, x.graduation_year && `Class of ${x.graduation_year}`].filter(Boolean).join(" · ");
              return (
                <li key={x.id}>
                  <Link href={`/alumni/${x.id}`} className="flex min-h-14 items-center gap-3 py-2.5 hover:bg-sunken/60 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ink">
                    <Avatar name={x.full_name} id={x.id} size={40} />
                    <span className="min-w-0 flex-1">
                      <span className="flex items-center gap-1.5 font-semibold"><span className="truncate">{x.full_name}</span>{x.verification_status === "verified" && <VerifiedMark />}</span>
                      {meta && <span className="block truncate text-small text-muted">{meta}</span>}
                    </span>
                  </Link>
                </li>
              );
            })}
          </ul>
          <Link href="/directory" className="mt-1 inline-flex min-h-11 items-center text-small font-semibold text-brand-ink hover:underline">Open the directory</Link>
        </>
      )}
    </Card>
  );
}
