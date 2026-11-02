import type { Overview, OverviewPeriod } from "@/lib/admin-overview";

/*
 * Typed sample answers for GET /admin/overview. They are used by tests and by /design-check only, to show how the
 * dashboard looks; the real app never imports this file, so no sample number can reach a signed-in person.
 */

const day = (i: number) => new Date(Date.UTC(2026, 8, 25 + i)).toISOString().slice(0, 10);
const days = (n: number, f: (i: number) => number) => Array.from({ length: n }, (_, i) => ({ day: day(i), count: f(i) }));

export const PLATFORM_FIXTURE: Overview = {
  period: "30d",
  organization_id: null,
  totals: {
    members: { value: 412, previous: 380, change_percent: 8.4 },
    new_members: { value: 32, previous: 25, change_percent: 28 },
    verified_members: { value: 150, previous: 140, change_percent: 7.1 },
  },
  funnel: [
    { step: "signed_up", count: 412, percent_of_previous: 100 },
    { step: "profile_complete", count: 300, percent_of_previous: 72.8 },
    { step: "verified", count: 150, percent_of_previous: 50 },
    { step: "connected", count: 90, percent_of_previous: 60 },
    { step: "booked_an_event", count: 30, percent_of_previous: 33.3 },
  ],
  attention: { reports_open: 2, reports_reviewing: 1, verification_requests_waiting: 12, payments_waiting_confirmation: 4, refunds_due: 1, events_in_draft: 3 },
  upcoming_events: [
    { id: "e1", title: "Alumni Golf Day", starts_at: "2026-11-07T06:00:00Z", confirmed_seats: 40, capacity: 96 },
    { id: "e2", title: "Careers Evening", starts_at: "2026-11-12T16:00:00Z", confirmed_seats: 18, capacity: 60 },
    { id: "e3", title: "Open Networking Mixer", starts_at: "2026-11-20T15:00:00Z", confirmed_seats: 7, capacity: null },
  ],
  signups_per_day: days(30, (i) => (i * 7) % 5 + (i % 9 === 0 ? 4 : 0)),
  recent_audit: [
    { id: "a1", action: "alumni_profile.verify", target_type: "alumni_profile", target_id: null, actor_user_id: null, organization_id: null, created_at: "2026-10-24T08:10:00Z" },
    { id: "a2", action: "membership.assign", target_type: "membership", target_id: null, actor_user_id: null, organization_id: null, created_at: "2026-10-23T14:00:00Z" },
    { id: "a3", action: "event.publish", target_type: "event", target_id: null, actor_user_id: null, organization_id: null, created_at: "2026-10-22T09:30:00Z" },
  ],
};

/** A school's own view: no report counts (reports belong to no school). */
export const SCHOOL_FIXTURE: Overview = {
  ...PLATFORM_FIXTURE,
  organization_id: "s1",
  attention: { ...PLATFORM_FIXTURE.attention, reports_open: null, reports_reviewing: null },
};

/** A moderator sees the report counts only: every other section is null. */
export const MODERATOR_FIXTURE: Overview = {
  period: "30d",
  organization_id: null,
  totals: null,
  funnel: null,
  attention: { reports_open: 3, reports_reviewing: 1, verification_requests_waiting: null, payments_waiting_confirmation: null, refunds_due: null, events_in_draft: null },
  upcoming_events: null,
  signups_per_day: null,
  recent_audit: null,
};

/** A new platform: real zeros, no change figures, no events, too few sign-up days for a chart. */
export const EMPTY_FIXTURE: Overview = {
  period: "30d",
  organization_id: null,
  totals: {
    members: { value: 2, previous: 0, change_percent: null },
    new_members: { value: 2, previous: 0, change_percent: null },
    verified_members: { value: 0, previous: 0, change_percent: null },
  },
  funnel: [
    { step: "signed_up", count: 2, percent_of_previous: 100 },
    { step: "profile_complete", count: 0, percent_of_previous: 0 },
    { step: "verified", count: 0, percent_of_previous: null },
    { step: "connected", count: 0, percent_of_previous: null },
    { step: "booked_an_event", count: 0, percent_of_previous: null },
  ],
  attention: { reports_open: 0, reports_reviewing: 0, verification_requests_waiting: 0, payments_waiting_confirmation: 0, refunds_due: 0, events_in_draft: 0 },
  upcoming_events: [],
  signups_per_day: days(30, (i) => (i === 28 ? 2 : 0)),
  recent_audit: [],
};

export const withPeriod = (o: Overview, period: OverviewPeriod): Overview => ({ ...o, period });
