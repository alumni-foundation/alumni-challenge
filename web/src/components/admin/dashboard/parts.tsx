"use client";

import { ArrowDownRight, ArrowRight, ArrowUpRight, CalendarDays, ChevronRight, ScrollText, ShieldAlert, TrendingUp } from "lucide-react";
import Link from "next/link";
import { EmptyState, Icon3D, Skeleton } from "@/components/ui";
import {
  attentionRows,
  auditSentence,
  bucketSignups,
  changeOf,
  chartableSignups,
  funnelLabel,
  funnelShares,
  PERIODS,
  type DashboardScope,
  type Overview,
  type OverviewPeriod,
} from "@/lib/admin-overview";
import { cn, formatDate } from "@/lib/utils";

const card = "rounded-[1.75rem] border border-line bg-surface p-5 shadow-resting sm:p-6";
const dayFmt = new Intl.DateTimeFormat("en-KE", { day: "numeric", month: "short", timeZone: "UTC" });
const shortDay = (iso: string) => dayFmt.format(new Date(`${iso}T00:00:00Z`));

function CardTitle({ icon, tone, title, hint, aside }: { icon: React.ElementType; tone: "ember" | "gold" | "moss" | "sky" | "ink"; title: string; hint?: string; aside?: React.ReactNode }) {
  return (
    <div className="mb-4 flex items-start gap-3">
      <Icon3D icon={icon} tone={tone} size="sm" />
      <div className="min-w-0 flex-1">
        <h2 className="text-lead font-semibold leading-7">{title}</h2>
        {hint && <p className="text-small text-muted">{hint}</p>}
      </div>
      {aside}
    </div>
  );
}

/* ---- Five number tiles --------------------------------------------------------------------------------------------- */

export type KpiKey = "members" | "new_members" | "verified_members" | "reports_open" | "payments";
type Kpi = { key: KpiKey; label: string; value: number; change: ReturnType<typeof changeOf>; href?: string; note?: string };

export function kpisFrom(o: Overview): Kpi[] {
  const words = PERIODS.find((p) => p.value === o.period)?.words ?? "";
  const out: Kpi[] = [];
  if (o.totals) {
    out.push({ key: "members", label: "Members", value: o.totals.members.value, change: changeOf(o.totals.members, words) });
    out.push({ key: "new_members", label: "New members", value: o.totals.new_members.value, change: changeOf(o.totals.new_members, words) });
    out.push({
      key: "verified_members",
      label: "Verified members",
      value: o.totals.verified_members.value,
      change: changeOf(o.totals.verified_members, words),
      // The backend cannot know when someone was verified, so the earlier count is a minimum (docs/admin-api.md) and the
      // real change may be smaller than shown. The tile says so.
      note: "Earlier count is a minimum",
    });
  }
  if (o.attention.reports_open !== null) out.push({ key: "reports_open", label: "Open reports", value: o.attention.reports_open, change: null, href: "/admin/reports" });
  if (o.attention.payments_waiting_confirmation !== null) out.push({ key: "payments", label: "Payments to confirm", value: o.attention.payments_waiting_confirmation, change: null, href: "/events" });
  return out;
}

/** The tile worth a glance first, for this kind of person. It gets the gold fill. */
export const goldKeyFor = (scope: DashboardScope["kind"]): KpiKey =>
  scope === "platform" || scope === "moderator" ? "reports_open" : scope === "school" ? "verified_members" : "payments";

function Delta({ change }: { change: NonNullable<ReturnType<typeof changeOf>> }) {
  const Arrow = change.direction === "up" ? ArrowUpRight : change.direction === "down" ? ArrowDownRight : ArrowRight;
  return (
    <span className="inline-flex items-center gap-0.5 text-small tabular-nums text-muted" title={change.label}>
      <Arrow className="size-3.5" aria-hidden />
      <span aria-hidden>{change.text}</span>
      <span className="sr-only">{change.label}</span>
    </span>
  );
}

export function KpiTiles({ kpis, goldKey, loading }: { kpis: Kpi[]; goldKey: KpiKey; loading?: boolean }) {
  return (
    <ul className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-3" aria-label="Key numbers">
      {kpis.map((k) => {
        const gold = k.key === goldKey;
        const body = (
          <>
            <p className="text-small text-muted">{k.label}</p>
            <div className="mt-3 flex items-end justify-between gap-2">
              <span className={cn("font-serif text-display font-semibold leading-none tabular-nums lining-nums", loading && "opacity-60")}>{k.value.toLocaleString("en-KE")}</span>
              {k.change ? <Delta change={k.change} /> : null}
            </div>
            {k.note && k.change && (
              <p className="mt-2 text-caption text-muted" title="We don’t record when someone was verified, so the count for the period before is a minimum. The real change may be smaller than shown.">
                {k.note}
              </p>
            )}
          </>
        );
        const cls = cn(
          "block h-full rounded-[1.5rem] border p-4 shadow-resting transition-[transform,box-shadow] duration-200 motion-reduce:transition-none",
          gold ? "border-gold/25 bg-gold-fill" : "border-line bg-surface",
          k.href && "hover:-translate-y-0.5 hover:shadow-raised motion-reduce:hover:translate-y-0",
        );
        return (
          <li key={k.key}>
            {k.href ? <Link href={k.href} className={cn(cls, "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink")}>{body}</Link> : <div className={cls}>{body}</div>}
          </li>
        );
      })}
    </ul>
  );
}

/* ---- Member journey ------------------------------------------------------------------------------------------------ */

const hatch = "repeating-linear-gradient(135deg, transparent 0 5px, color-mix(in srgb, var(--ink) 28%, transparent) 5px 6px)";

export function PeriodToggle({ value, onChange }: { value: OverviewPeriod; onChange: (p: OverviewPeriod) => void }) {
  return (
    <div role="group" aria-label="Time period" className="inline-flex rounded-full bg-sunken p-1">
      {PERIODS.map((p) => (
        <button
          key={p.value}
          type="button"
          aria-pressed={value === p.value}
          onClick={() => onChange(p.value)}
          className={cn(
            "h-9 rounded-full px-4 text-small font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink",
            value === p.value ? "bg-ink text-white" : "text-muted hover:text-ink",
          )}
        >
          {p.label}
        </button>
      ))}
    </div>
  );
}

export function JourneyCard({ overview, period, onPeriod, fetching }: { overview: Overview; period: OverviewPeriod; onPeriod: (p: OverviewPeriod) => void; fetching: boolean }) {
  const steps = overview.funnel ?? [];
  const shares = funnelShares(steps);
  return (
    <section aria-labelledby="journey-title" className={card}>
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 id="journey-title" className="text-lead font-semibold leading-7">Member journey</h2>
          <p className="text-small text-muted">Everyone, as of today. The period changes the number tiles and the sign-ups chart.</p>
        </div>
        <PeriodToggle value={period} onChange={onPeriod} />
      </div>
      <ol className={cn("grid grid-cols-2 gap-3 transition-opacity md:grid-cols-3 xl:grid-cols-5", fetching && "opacity-60")} aria-busy={fetching}>
        {steps.map((s, i) => {
          const last = i === steps.length - 1;
          return (
            <li key={s.step} className="flex flex-col rounded-[1.5rem] bg-sunken p-3">
              <div className="flex items-center justify-between gap-2">
                <span className={cn("rounded-full px-2.5 py-0.5 text-caption font-medium", last ? "bg-ink text-white" : "bg-surface text-ink")}>{funnelLabel(s.step)}</span>
                {s.percent_of_previous !== null && (
                  <span className="text-caption tabular-nums text-muted">
                    {Math.round(s.percent_of_previous)}%<span className="sr-only"> of the step before</span>
                  </span>
                )}
              </div>
              <div className="relative mt-3 flex h-24 items-end" aria-hidden>
                <div
                  className={cn("w-full rounded-xl border transition-[height] duration-500 ease-out motion-reduce:transition-none", last ? "border-gold bg-gold-soft" : "border-ink/40")}
                  style={{ height: `${Math.round(shares[i] * 100)}%`, backgroundImage: last ? undefined : hatch }}
                />
              </div>
              <p className="mt-3 flex items-baseline gap-1.5">
                <span className="font-serif text-display font-semibold leading-none tabular-nums lining-nums">{s.count.toLocaleString("en-KE")}</span>
                <span className="text-small text-muted">{s.count === 1 ? "member" : "members"}</span>
              </p>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

/* ---- Three cards --------------------------------------------------------------------------------------------------- */

export function AttentionCard({ overview, scope }: { overview: Overview; scope: DashboardScope }) {
  const rows = attentionRows(overview.attention, scope);
  const open = rows.reduce((n, r) => n + r.count, 0);
  return (
    <section aria-label="Needs your attention" className={card}>
      <CardTitle
        icon={ShieldAlert}
        tone="ember"
        title="Needs your attention"
        hint={open === 0 ? "All clear for now" : `${open} ${open === 1 ? "thing" : "things"} waiting`}
      />
      <ul className="space-y-2">
        {rows.map((r) => (
          <li key={r.key}>
            <Link
              href={r.href}
              className="flex min-h-12 items-center gap-3 rounded-2xl bg-sunken px-4 py-2 transition-colors hover:bg-line focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
            >
              <span className="min-w-0 flex-1 text-small font-medium">{r.label}</span>
              <span className={cn("min-w-7 rounded-full px-2 text-center text-small font-semibold tabular-nums", r.count > 0 ? "bg-ink text-white" : "bg-surface text-muted")}>{r.count}</span>
              <ChevronRight className="size-4 shrink-0 text-muted" aria-hidden />
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function UpcomingCard({ events }: { events: NonNullable<Overview["upcoming_events"]> }) {
  return (
    <section aria-label="Upcoming events" className={card}>
      <CardTitle icon={CalendarDays} tone="gold" title="Upcoming events" hint="Seats taken so far" aside={<Link href="/events" className="inline-flex min-h-11 items-center text-small font-medium text-brand-ink hover:underline">All events</Link>} />
      {events.length === 0 ? (
        <EmptyState title="No events coming up" body="Published events with a date in the future will appear here." />
      ) : (
        <ul className="space-y-2">
          {events.map((e) => {
            const pct = e.capacity ? Math.min(100, Math.round((e.confirmed_seats / e.capacity) * 100)) : null;
            return (
              <li key={e.id}>
                <Link href={`/events/${e.id}`} className="block rounded-2xl bg-sunken px-4 py-3 transition-colors hover:bg-line focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink">
                  <p className="truncate text-small font-semibold">{e.title}</p>
                  <p className="text-caption text-muted">{formatDate(e.starts_at)}</p>
                  <div className="mt-2 flex items-center gap-3">
                    {pct !== null && (
                      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface" aria-hidden>
                        <div className="h-full rounded-full bg-ink" style={{ width: `${pct}%` }} />
                      </div>
                    )}
                    <span className="shrink-0 text-caption tabular-nums text-muted">
                      {e.capacity ? `${e.confirmed_seats} of ${e.capacity} seats` : `${e.confirmed_seats} booked, no limit`}
                    </span>
                  </div>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

export function ActivityCard({ items, nameOf, allHref }: { items: NonNullable<Overview["recent_audit"]>; nameOf: (userId: string | null) => string | null; allHref?: string }) {
  return (
    <section aria-label="Recent activity" className={card}>
      <CardTitle icon={ScrollText} tone="sky" title="Recent activity" hint="Latest changes, newest first" aside={allHref ? <Link href={allHref} className="inline-flex min-h-11 items-center text-small font-medium text-brand-ink hover:underline">Activity log</Link> : undefined} />
      {items.length === 0 ? (
        <EmptyState title="Nothing recorded yet" body="Admin actions will show up here." />
      ) : (
        <ul className="space-y-2">
          {items.map((a) => (
            <li key={a.id} className="rounded-2xl bg-sunken px-4 py-2.5">
              <p className="text-small">{auditSentence(a.action, nameOf(a.actor_user_id), a.target_type)}</p>
              <time dateTime={a.created_at} className="text-caption text-muted">{formatDate(a.created_at)}</time>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

/* ---- Sign-ups chart ------------------------------------------------------------------------------------------------ */

export function SignupsCard({ days, period }: { days: NonNullable<Overview["signups_per_day"]>; period: OverviewPeriod }) {
  const words = PERIODS.find((p) => p.value === period)?.words ?? "";
  const usable = chartableSignups(days);
  const bars = usable ? bucketSignups(usable) : [];
  const max = Math.max(1, ...bars.map((b) => b.count));
  const total = bars.reduce((n, b) => n + b.count, 0);
  const grouped = usable ? usable.length > bars.length : false;
  return (
    <section aria-label="Sign-ups" className={card}>
      <CardTitle icon={TrendingUp} tone="moss" title="Sign-ups" hint={usable ? `${total.toLocaleString("en-KE")} new ${total === 1 ? "member" : "members"} in ${words}${grouped ? ", grouped by week" : ", one bar a day"}` : words} />
      {!usable ? (
        <EmptyState title="Not enough days to draw a chart yet" body="Once people have signed up on at least three different days, the daily counts will show here." />
      ) : (
        <figure>
          <div className="flex h-40 items-end gap-[3px] border-b border-line" role="img" aria-label={`${total} sign-ups in ${words}. Busiest ${grouped ? "stretch" : "day"}: ${Math.max(...bars.map((b) => b.count))}.`}>
            {bars.map((b) => (
              <div
                key={b.from}
                title={`${b.from === b.to ? shortDay(b.from) : `${shortDay(b.from)} to ${shortDay(b.to)}`}: ${b.count}`}
                className={cn("min-w-0 flex-1 rounded-t-md", b.count === 0 ? "bg-line" : "bg-brand")}
                style={{ height: b.count === 0 ? "2px" : `${Math.max(4, (b.count / max) * 100)}%` }}
              />
            ))}
          </div>
          <figcaption className="mt-2 flex justify-between text-caption tabular-nums text-muted">
            <span>{shortDay(bars[0].from)}</span>
            <span>Tallest bar: {max}</span>
            <span>{shortDay(bars[bars.length - 1].to)}</span>
          </figcaption>
        </figure>
      )}
    </section>
  );
}

/* ---- Loading ------------------------------------------------------------------------------------------------------- */

export function DashboardSkeleton() {
  return (
    <div role="status" aria-label="Loading the dashboard" className="space-y-4">
      <ul className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-3">
        {Array.from({ length: 5 }, (_, i) => (
          <li key={i}><Skeleton className="h-[7.25rem] rounded-[1.5rem]" /></li>
        ))}
      </ul>
      <Skeleton className="h-72 rounded-[1.75rem]" />
      <div className="grid gap-4 lg:grid-cols-3">
        {Array.from({ length: 3 }, (_, i) => (
          <Skeleton key={i} className="h-72 rounded-[1.75rem]" />
        ))}
      </div>
      <Skeleton className="h-60 rounded-[1.75rem]" />
    </div>
  );
}

/* ---- The whole body, so the page and /design-check draw exactly the same thing --------------------------------------- */

export function DashboardBody({ overview: o, scope, period, onPeriod, fetching, nameOf, activityHref }: {
  overview: Overview;
  scope: DashboardScope;
  period: OverviewPeriod;
  onPeriod: (p: OverviewPeriod) => void;
  fetching: boolean;
  nameOf: (userId: string | null) => string | null;
  activityHref?: string;
}) {
  return (
    <>
      <KpiTiles kpis={kpisFrom(o)} goldKey={goldKeyFor(scope.kind)} loading={fetching} />
      {o.funnel && <JourneyCard overview={o} period={period} onPeriod={onPeriod} fetching={fetching} />}
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <AttentionCard overview={o} scope={scope} />
        {o.upcoming_events && <UpcomingCard events={o.upcoming_events} />}
        {o.recent_audit && <ActivityCard items={o.recent_audit} nameOf={nameOf} allHref={activityHref} />}
      </div>
      {o.signups_per_day && <SignupsCard days={o.signups_per_day} period={period} />}
    </>
  );
}
