# Admin API

## `GET /api/v1/admin/overview`

Numbers for the admin dashboard. Read-only. **Counts only: no names, no emails, no profile
details.** Query: `organization_id` (optional), `period` = `30d` (default), `90d` or `365d`
(anything else is `422`).

### Who sees what
| Caller | No `organization_id` | With `organization_id` |
|---|---|---|
| Platform admin (`admin`, `super_admin`) | Everything, the whole platform | That organization only (`404` if it does not exist) |
| School admin, partner admin, event manager | All the organizations they hold that role in (usually one) | That organization if it is theirs, otherwise `404` (the same answer as for an organization that does not exist) |
| Moderator | Only the report counts; every other section is `null` | `404` |
| Moderator who also holds an organization role | Both parts | as above |
| Anyone else signed in (including sports managers and plain members) | `403` | `403` |
| Not signed in | `401` | `401` |

A role that has been revoked gives nothing. Reports belong to no school, so in one organization's
view (also a platform admin's) `reports_open` and `reports_reviewing` are `null`.

### Answer
A section the caller may not see is `null`.

```
{
  "period": "30d",
  "organization_id": null,                 // the organization asked about, if any
  "totals": {
    "members":          {"value": 412, "previous": 380, "change_percent": 8.4},
    "new_members":      {"value": 32,  "previous": 25,  "change_percent": 28.0},
    "verified_members": {"value": 150, "previous": 140, "change_percent": 7.1}
  },
  "funnel": [
    {"step": "signed_up",        "count": 412, "percent_of_previous": 100.0},
    {"step": "profile_complete", "count": 300, "percent_of_previous": 72.8},
    {"step": "verified",         "count": 150, "percent_of_previous": 50.0},
    {"step": "connected",        "count": 90,  "percent_of_previous": 60.0},
    {"step": "booked_an_event",  "count": 30,  "percent_of_previous": 33.3}
  ],
  "attention": {
    "reports_open": 2, "reports_reviewing": 1,
    "verification_requests_waiting": 12,
    "payments_waiting_confirmation": 4, "refunds_due": 1,
    "events_in_draft": 3
  },
  "upcoming_events": [
    {"id": "...", "title": "Demo Golf Day", "starts_at": "...", "confirmed_seats": 40, "capacity": 96}
  ],
  "signups_per_day": [{"day": "2026-09-25", "count": 3}, ...],
  "recent_audit": [
    {"id": "...", "action": "booking.payment_confirmed", "target_type": "booking",
     "target_id": "...", "actor_user_id": "...", "organization_id": "...", "created_at": "..."}
  ]
}
```

* **Member** = an active user (not suspended or deleted). For one organization: an active user
  whose profile names that school. For the whole platform: every active user.
* `previous` is the same measure one period earlier. `change_percent` is `null` when `previous`
  is `0`. For `members`, `previous` is the count at the start of the period. For
  `verified_members` it is a **lower bound**: the database does not record when someone was
  verified, so it counts people verified now whose profile has not changed since the period began.
* **Funnel:** each step counts only people who passed the steps before it, so the counts never
  grow and the percentages are of the previous step (the first is `100.0`; `null` if the step
  before is `0`). `profile_complete` = school and graduation year set. `verified` = verified
  profile. `connected` = at least one accepted connection. `booked_an_event` = at least one
  confirmed booking. The funnel is for everyone now, not only for the period.
* `verification_requests_waiting`: unverified people who have set a school and a graduation year
  (there is no separate request record). `payments_waiting_confirmation`: bookings whose M-Pesa
  code awaits an organizer. `refunds_due`: payments in `needs_refund`. `events_in_draft`: drafts.
  The money and draft counts are for events of the organization (all events for the platform).
* `upcoming_events`: the next 5 published events that have not started, soonest first.
  `confirmed_seats` and `capacity` add up the slots; `capacity` is `null` if a slot is unlimited.
* `signups_per_day`: one entry for every day of the period, oldest first, today last (UTC days),
  zeros included, so it can be charted as it is.
* `recent_audit`: the last 8 entries the caller may see (a platform admin sees all; an
  organization role only entries tagged with its organizations). Only what happened and to what:
  **the details of an entry are never included**, because they can hold names and emails.

### Cache and limits
* The answer is kept for **60 seconds**, per organization set and period, never shared between
  callers who may see different things (the key includes what the caller may see). Expect numbers up
  to a minute old.
* **30 requests a minute per account** (`429` after that).

### Speed
Measured on the test database with 50,000 members, 25,000 accepted connections and 10 schools,
one year as the period: the whole answer takes about 1.1 s for the platform and 0.5 s for one
school, and is then served from the cache for a minute. The slowest part is the funnel (0.4 s),
which reads every member once. No new index was needed: the counts use the indexes that exist
(`users` by status and creation date, profiles by user, connections by user, bookings by payment
state, events by organization). Add one if a second measurement on real data says otherwise.
