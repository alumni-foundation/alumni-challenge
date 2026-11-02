import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";

/*
 * GET /admin/overview. The backend has not published docs/admin-api.md or regenerated schema.d.ts yet, so these types
 * follow the backend's overview schemas by hand. Once the schema has them, replace this block with aliases in types.ts.
 * A section the caller may not see comes back as null; the dashboard hides the card instead of showing a zero.
 */
export type OverviewPeriod = "30d" | "90d" | "365d";
export const PERIODS: { value: OverviewPeriod; label: string; words: string }[] = [
  { value: "30d", label: "30 days", words: "the last 30 days" },
  { value: "90d", label: "90 days", words: "the last 90 days" },
  { value: "365d", label: "Year", words: "the last year" },
];

export type OverviewTotal = { value: number; previous: number; change_percent: number | null };
export type FunnelStepKey = "signed_up" | "profile_complete" | "verified" | "connected" | "booked_an_event";
export type OverviewFunnelStep = { step: FunnelStepKey | string; count: number; percent_of_previous: number | null };
export type OverviewAttention = {
  reports_open: number | null;
  reports_reviewing: number | null;
  verification_requests_waiting: number | null;
  payments_waiting_confirmation: number | null;
  refunds_due: number | null;
  events_in_draft: number | null;
};
export type OverviewEvent = { id: string; title: string; starts_at: string; confirmed_seats: number; capacity: number | null };
export type OverviewAudit = {
  id: string;
  action: string;
  target_type: string;
  target_id: string | null;
  actor_user_id: string | null;
  organization_id: string | null;
  created_at: string;
};
export type Overview = {
  period: OverviewPeriod;
  organization_id: string | null;
  totals: { members: OverviewTotal; new_members: OverviewTotal; verified_members: OverviewTotal } | null;
  funnel: OverviewFunnelStep[] | null;
  attention: OverviewAttention;
  upcoming_events: OverviewEvent[] | null;
  signups_per_day: { day: string; count: number }[] | null;
  recent_audit: OverviewAudit[] | null;
};

export const overviewPath = (period: OverviewPeriod, organizationId: string | null) => {
  const qs = new URLSearchParams({ period });
  if (organizationId) qs.set("organization_id", organizationId);
  return `admin/overview?${qs}`;
};

export const useAdminOverview = (period: OverviewPeriod, organizationId: string | null, enabled = true) =>
  useQuery({
    queryKey: ["admin-overview", period, organizationId],
    queryFn: () => api<Overview>(overviewPath(period, organizationId)),
    enabled,
    staleTime: 30_000,
    retry: false,
    placeholderData: (prev) => prev,
  });

/* ---- Wording and small calculations (pure, tested) ---------------------------------------------------------------- */

/** Morning before 12:00, afternoon before 17:00, otherwise evening, by the clock in Nairobi. */
export function greetingFor(now: Date): "Good morning" | "Good afternoon" | "Good evening" {
  const hour = Number(new Intl.DateTimeFormat("en-GB", { hour: "numeric", hourCycle: "h23", timeZone: "Africa/Nairobi" }).format(now));
  return hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";
}

/** First word of a full name, first letter capitalised ("jordan ellis" gives "Jordan"). Null when there is no name. */
export function firstNameOf(fullName: string | null | undefined): string | null {
  const first = fullName?.trim().split(/\s+/)[0];
  return first ? first.charAt(0).toUpperCase() + first.slice(1) : null;
}

export type Change = { text: string; direction: "up" | "down" | "flat"; label: string } | null;

/** "+12%" with a direction, or null when the API had nothing to compare with (never an invented zero). */
export function changeOf(total: OverviewTotal | undefined, periodWords: string): Change {
  if (!total || total.change_percent === null) return null;
  const pct = Math.round(total.change_percent);
  const direction = pct > 0 ? "up" : pct < 0 ? "down" : "flat";
  const text = `${pct > 0 ? "+" : pct < 0 ? "−" : ""}${Math.abs(pct)}%`;
  const label =
    pct === 0
      ? `No change from the period before ${periodWords}`
      : `${Math.abs(pct)}% ${pct > 0 ? "up" : "down"} from the period before ${periodWords}`;
  return { text, direction, label };
}

export const FUNNEL_LABELS: Record<string, string> = {
  signed_up: "Signed up",
  profile_complete: "Profile complete",
  verified: "Verified",
  connected: "Connected",
  booked_an_event: "Booked an event",
};
export const funnelLabel = (step: string) => FUNNEL_LABELS[step] ?? step.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());

/** Bar heights as a share of the first step, so the bars shrink exactly as the real counts do. Empty funnel: all zero. */
export function funnelShares(steps: OverviewFunnelStep[]): number[] {
  const top = Math.max(0, ...steps.map((s) => s.count));
  return steps.map((s) => (top === 0 || s.count === 0 ? 0 : Math.max(0.04, s.count / top)));
}

/**
 * The API sends every day of the period, zeros included, so "days of data" means days that had a sign-up. Fewer than 3
 * cannot make a trend: the card shows an empty state instead of a lonely bar.
 */
export const MIN_CHART_DAYS = 3;
export function chartableSignups(days: { day: string; count: number }[] | null | undefined) {
  if (!days) return null;
  return days.filter((d) => d.count > 0).length >= MIN_CHART_DAYS ? days : null;
}

export type SignupBar = { from: string; to: string; count: number };
/** Groups consecutive days so a year still reads as at most `maxBars` bars (weeks, roughly). Counts are summed, never averaged. */
export function bucketSignups(days: { day: string; count: number }[], maxBars = 52): SignupBar[] {
  const size = Math.max(1, Math.ceil(days.length / maxBars));
  const out: SignupBar[] = [];
  for (let i = 0; i < days.length; i += size) {
    const chunk = days.slice(i, i + size);
    out.push({ from: chunk[0].day, to: chunk[chunk.length - 1].day, count: chunk.reduce((n, d) => n + d.count, 0) });
  }
  return out;
}

const ACTION_WORDS: Record<string, string> = {
  "organization.create": "created an organization",
  "organization.update": "edited an organization",
  "organization.email_domain.add": "added a school email domain",
  "membership.assign": "gave someone a role",
  "membership.revoke": "took a role away",
  "alumni_profile.verify": "verified an alumni profile",
  "alumni_profile.unverify": "removed a verification",
  "report.review": "reviewed a report",
  "user.suspend": "suspended an account",
  "user.reactivate": "reactivated an account",
  "user.password_reset": "reset a password",
  "event.create": "created an event",
  "event.update": "edited an event",
  "event.publish": "published an event",
  "event.cancel": "cancelled an event",
  "event.close": "closed bookings for an event",
  "event.complete": "marked an event as finished",
  "event.reopen": "reopened an event",
  "booking.create": "made a booking",
  "booking.cancel": "cancelled a booking",
  "ticket.check_in": "checked someone in",
  "ticket.reissue": "reissued a ticket",
  "event.export_registrations": "exported a registration list",
};
const NOUNS: Record<string, string> = {
  event_question: "an event question",
  event_slot: "an event time slot",
  event_consent: "an event consent",
  event_series: "an event series",
  event: "an event",
  booking: "a booking",
  ticket: "a ticket",
  user: "an account",
  alumni_profile: "an alumni profile",
  organization: "an organization",
  membership: "a role",
  report: "a report",
};
const VERBS: Record<string, string> = {
  create: "added", update: "changed", delete: "removed", publish: "published", cancel: "cancelled",
  verify: "verified", assign: "gave", revoke: "took away", payment_confirmed: "confirmed a payment for",
};
/**
 * "Amina verified an alumni profile". The API sends the action name and the kind of thing only (details can hold names),
 * so unknown actions get a plain "changed <thing>" instead of the raw code.
 */
export function auditWords(action: string, targetType?: string): string {
  const known = ACTION_WORDS[action];
  if (known) return known;
  const [kind, verb = ""] = [action.slice(0, action.indexOf(".")), action.slice(action.indexOf(".") + 1)];
  const noun = NOUNS[kind] ?? NOUNS[targetType ?? ""];
  if (noun && VERBS[verb]) return `${VERBS[verb]} ${noun}`;
  return `made a change${noun ? ` to ${noun}` : ""}`;
}
export function auditSentence(action: string, actorName?: string | null, targetType?: string): string {
  return `${actorName ?? "Someone"} ${auditWords(action, targetType)}`;
}

export type AttentionRow = { key: string; label: string; count: number; href: string };
export type DashboardScope = { kind: "platform" | "moderator" | "school" | "partner" | "organizer"; organizationId: string | null };

/**
 * What needs a person, one row per kind, only for numbers the API gave (null means this role cannot see it).
 * Each row links to the page that handles it; payments, refunds and drafts have no staff page yet, so they open Events.
 */
export function attentionRows(a: OverviewAttention, scope: DashboardScope): AttentionRow[] {
  const rows: (AttentionRow | null)[] = [
    a.reports_open === null ? null : { key: "reports", label: "Reports to review", count: a.reports_open, href: "/admin/reports" },
    a.verification_requests_waiting === null || scope.kind === "organizer"
      ? null
      : {
          key: "verification",
          label: "Awaiting verification",
          count: a.verification_requests_waiting,
          href: scope.kind === "school" ? `/school/${scope.organizationId}/roster` : "/admin/organizations",
        },
    a.payments_waiting_confirmation === null ? null : { key: "payments", label: "Payments to confirm", count: a.payments_waiting_confirmation, href: "/events" },
    a.refunds_due === null ? null : { key: "refunds", label: "Refunds due", count: a.refunds_due, href: "/events" },
    a.events_in_draft === null ? null : { key: "drafts", label: "Events still in draft", count: a.events_in_draft, href: "/events" },
  ];
  return rows.filter((r): r is AttentionRow => r !== null);
}
