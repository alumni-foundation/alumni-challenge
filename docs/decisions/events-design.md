# Events, booking, waitlist, tickets and payments: design

Status: **APPROVED by the owner, 24 Oct 2026, with the answers and two changes in section 15.**
Build order: 5.1, 5.2, 5.4, 5.5, 5.3, 5.6. Where this document and section 15 disagree,
section 15 wins.
Covers PLAN Phase 5 (events), the hooks Phase 6 (payments) needs, and the data Phase 7 (golf)
needs, so that the first two do not have to be redone for the third. Section 14 lists what
needs the owner's decision. Everything in sections 1 to 13 assumes the recommended answer.

## 0. The shape of it, in one page

* **Meeting people comes first.** An event is a reason for people to find each other. The
  smallest event is a free meetup with a one-tap "I'm going". "Who's going" is on every event
  and obeys each person's privacy tier. A paid golf day is the same thing with slots, a price,
  a group of up to four and a payment step.
* **One mechanism for all of it.** Every event has at least one *slot*; a slot holds a number
  of *seats*; a *booking* takes seats from a slot. A meetup has one slot with no label. A golf
  day has four slots (the four tee-off periods). Capacity code is therefore written and proven
  once.
* **The database is the last line of defence.** Seat counters live on the slot row, are changed
  only while that row is locked, and are guarded by a CHECK constraint, so even buggy code cannot
  oversell.
* **Booking needs an account. The booker pays for the whole group (up to 4).** The other
  players are named, not required to have accounts.
* **Payments are an interface, not a provider.** The booking code only knows "an attempt to pay
  `n` minor units for booking `b`". A fake provider and a manual-confirmation provider come
  first, then M-Pesa Daraja STK Push, then cards.
* **Build in slices that each ship alone** (section 12).

## 1. Vocabulary and states

| Word | Meaning |
|---|---|
| Event | A thing on a date, run by an organization (school, partner) or by the platform. |
| Series | A named group of events that are rounds of one competition (Duracoat: 12 rounds). |
| Slot | A bookable window of an event with its own capacity (tee-off period, or "the whole event"). |
| Seat | One person's place in a slot. A group of four takes four seats. |
| Booking | One booker's claim on seats in one slot, with a state. |
| Participant | A person in a booking. Participant 1 is the booker. Others have a name and optional contact details, and an account only if they claim their ticket. |
| Ticket | One per participant, with a QR code, valid only while its booking is `confirmed`. |
| Hold | The time a `pending_payment` booking keeps its seats. 15 minutes by default. |

**Booking states.** `pending_payment`, `confirmed`, `waitlisted`, `expired`, `cancelled`,
`refunded`. Only the first three occupy or queue for seats.

| From | To | Caused by | Seats |
|---|---|---|---|
| (new, paid event, seats free) | `pending_payment` | booker submits | taken, held until `hold_expires_at` |
| (new, free event, seats free) | `confirmed` | booker submits | taken, no hold needed |
| (new, no seats, waitlist on) | `waitlisted` | booker submits | none |
| (new, no seats, waitlist off) | refused with 409 `sold_out` | | none |
| `pending_payment` | `confirmed` | payment verified | held becomes confirmed |
| `pending_payment` | `expired` | hold ran out, no payment in flight | released, waitlist promoted |
| `pending_payment` | `cancelled` | booker or organizer cancels | released, waitlist promoted |
| `waitlisted` | `pending_payment` / `confirmed` | seats freed and this booking is next | taken (paid: held for the offer window) |
| `waitlisted` | `cancelled` | booker leaves, or offer window ran out | none |
| `confirmed` | `cancelled` | free event: booker cancels. Paid event: organizer cancels | released, promoted |
| `confirmed` (paid) | `refunded` | organizer refunds (Phase 6) | released, promoted |
| `expired` | `confirmed` | late payment arrives and the seats are still free (section 8) | re-taken |

`expired`, `cancelled` and `refunded` are final except for that one late-payment path. Every
transition is made by one function in one place, writes an audit row when an organizer did it,
and queues its email through the existing outbox.

## 2. Data model

Conventions (PLAN Phase 0): UUID primary keys, `created_at`/`updated_at` on every table,
`created_by`/`updated_by` on tables people edit, `status` only where there is a real
lifecycle. Every foreign key is named. Enum types are dropped in `downgrade()`. Times are
`timestamptz` in UTC; display is Africa/Nairobi (no daylight saving, so no edge cases). **Money
is `bigint` minor units plus a 3-letter currency, never a float.** KES only at launch; the
column exists so a second currency is not a migration.

### 2.1 Events (Phase 5.1)

**`event_series`**: `id`, `organization_id` (nullable = platform), `title`, `description`.

**`events`**

| Column | Notes |
|---|---|
| `organization_id` | FK `organizations`, nullable = run by the platform itself |
| `series_id`, `round_number` | both null, or both set; unique `(series_id, round_number)` |
| `title`, `description`, `category` | category enum: homecoming, golf_tournament, sports, networking, forum, mentorship, leadership, philanthropy, other |
| `status` | draft, published, closed, cancelled, completed |
| `visibility` | `public` or `members_only` (anonymous visitors cannot see it) |
| `starts_at`, `ends_at` | CHECK `ends_at > starts_at` |
| `venue_name`, `venue_address` | text |
| `poster_file_id` | FK `files`, set null on delete. Reuses the existing `event_poster` upload purpose and the same roles that may already upload posters |
| `registration_opens_at`, `registration_closes_at` | both nullable; evaluated with the database clock |
| `price_minor`, `currency` | `price_minor >= 0` per participant; 0 means free |
| `max_party_size` | 1 to 4 (CHECK); 1 for a meetup |
| `hold_minutes` | default 15, CHECK between 5 and 2880 (more than 60 only for manual-payment events) |
| `waitlist_enabled` | bool |
| `show_attendee_list` | bool, default true. **The organizer's switch** |
| `payment_account_id` | FK `payment_accounts`, nullable; required to publish when `price_minor > 0` (Phase 6) |
| `contact_email`, `contact_phone`, `refund_policy_text` | text |
| `reminder_hours_before` | default 24 |

Publishing is refused unless the event has at least one slot, a future start, and (if paid) a
payee. `price_minor`, `currency`, `max_party_size` and `payment_account_id` cannot be changed
once a booking exists, so nobody pays a price they did not see.

**`event_slots`**: `event_id`, `label` (null for the single "whole event" slot), `starts_at`,
`ends_at`, `capacity` (null = unlimited, used only by free meetups), `seats_confirmed`,
`seats_held`, `position`.
`CHECK (seats_confirmed >= 0 AND seats_held >= 0)` and
`CHECK (capacity IS NULL OR seats_confirmed + seats_held <= capacity)`. The counters are the
fast path; section 9 explains how they are kept true and how a test proves it.

**`event_questions`** (configurable, not golf-specific): `event_id`, `key` (unique per event),
`label`, `kind` (text, long_text, number, choice, multi_choice, boolean), `options` (jsonb, for
choices), `required`, `asked_of` (`booker` or `each_participant`), `position`.
**`booking_answers`**: `booking_id`, `participant_id` (null = booker-level), `question_id`,
`value` (jsonb). Answers are validated in the service against the question definition (kind,
required, allowed options, length). Questions cannot change kind once answered.

**`event_consents`**: `event_id`, `key` (terms, filming_photography, no_refund_ack, ...),
`text`, `version`, `required`. **`booking_consents`**: `booking_id`, `consent_id`, `accepted_at`,
`text_sha256` (proof of exactly which words were accepted). A required consent that is not
accepted refuses the booking.

### 2.2 Bookings, participants, tickets (Phase 5.2 and 5.4)

**`bookings`**

| Column | Notes |
|---|---|
| `event_id`, `slot_id` | FKs; the slot must belong to the event (composite FK) |
| `booker_user_id` | FK `users`, **NOT NULL**, `RESTRICT` (accounts are anonymized on deletion, never removed, so financial history stays) |
| `party_size` | CHECK `1 <= party_size <= 4`; must be `<= events.max_party_size` (service) |
| `status` | the six states above |
| `unit_price_minor`, `amount_minor`, `currency` | **snapshotted at booking time**, computed on the server (`unit * party_size`). The client never sends a price |
| `hold_expires_at` | set only while `pending_payment`; CHECK ties it to the status |
| `waitlisted_at`, `offered_at` | queue order and offer window start |
| `from_waitlist` | bool, for the "a place came up" email and screen |
| `reference` | short human code (for example `AC-7K3Q9X`), unique. Printed on tickets and used as the M-Pesa account reference |
| `idempotency_key` | unique `(booker_user_id, idempotency_key)` plus `request_sha256` |
| `confirmed_at`, `cancelled_at`, `cancel_reason`, `cancelled_by` | |
| `reminder_sent_at` | makes reminders idempotent |

Indexes: `(slot_id, status)`, `(event_id, status)`, `(booker_user_id, created_at desc)`,
`(slot_id, waitlisted_at) WHERE status='waitlisted'`, `(hold_expires_at) WHERE
status='pending_payment'`. **Partial unique index**: one *active* (`pending_payment`,
`confirmed`, `waitlisted`) booking per `(event_id, booker_user_id)`: nobody can hoard holds on
one event (decision 3).

**`booking_participants`**: `booking_id`, `position` (1 to 4, unique per booking; 1 is the
booker), `full_name` (required), `email`, `phone` (both optional, lower-cased/normalized),
`user_id` (null until claimed, see below), `listed` (bool, default true: "show me in who's
going"), `consent_to_contact_confirmed` (the booker ticked that they may give these details).

**Named players are not looked up.** The booking form never searches accounts by the email or
phone it is given, because that would answer "does this person have an account?" for anyone.
`user_id` is set only when the player claims their ticket by following the emailed link while
signed in (a signed, single-purpose token, same pattern as password reset). Until then they are
a name on a ticket. They never appear in "who's going" (no profile, so no privacy tier to
honour), though they are counted.

**`tickets`**: one per participant, created when the booking becomes `confirmed`.
`booking_id`, `participant_id` (unique), `qr_version`, `status` (valid, checked_in, void),
`checked_in_at`, `checked_in_by`. The QR payload is `ticket_id` plus a 128-bit HMAC of
`(ticket_id, qr_version)` under a dedicated `TICKET_SIGNING_KEY` secret. Nothing secret is
stored, a lost QR can be re-drawn, and bumping `qr_version` invalidates a leaked one. Forging a
ticket needs the key; guessing one is a 2^-128 chance. A ticket whose booking is not
`confirmed` is void on scan.

### 2.3 Payments (Phase 6, designed now so bookings have the right hooks)

**`payment_accounts`** (the per-event payee): `organization_id` (null = platform), `label`,
`provider` (fake, manual_mpesa, mpesa_paybill, mpesa_till, card_*), `shortcode_or_till`
(public number, not secret), `credential_ref` (the *name* of a secret in the platform's secret
store, for example `MPESA_ACCT_YENGOLF`; the key and passkey themselves are environment
secrets, never in this table or in Git), `currency`, `active`.

**`orders`**: `kind` (`booking` now; donation, membership, merchandise later), `booking_id`
(null for other kinds), `amount_minor`, `currency`, `status` (open, paid, void).
**`payment_attempts`**: `order_id`, `provider`, `payment_account_id`, `status` (pending,
succeeded, failed, expired, cancelled), `amount_minor`, `currency`, `idempotency_key` (unique),
`provider_ref` (Daraja `CheckoutRequestID`), `receipt_number` (unique per provider: the
M-Pesa receipt, kept for reconciliation), `payer_msisdn_masked`, `callback_secret_hash`,
`started_at`, `settled_at`, `failure_reason`. At most 3 attempts per booking.
**`provider_events`** (the callback inbox): `provider`, `external_id`, `received_at`,
`payload` (jsonb, personal fields masked), `verified` (bool), `outcome`, `processed_at`;
unique `(provider, external_id)` so a replay is a no-op.
**`refunds`**: `payment_attempt_id`, `amount_minor`, `reason`, `status`, `provider_ref`,
`requested_by`, `approved_by`. Every organizer money action also writes the audit log.

### 2.4 Golf (Phase 7, modelled properly, not as free text)

**`golf_event_settings`** (one row per golf event): `has_handicap_field` (bool),
`handicap_required` (bool), `group_size` (4).
**`golf_teams`** (per event): `name` ("YENGOLF Alumni", "Alumni Challenge"), `identified_by`
(`school`, `cohort`, `none`). This is what makes the two teams in the Google Form work: one
team is identified by the school represented, the other by a cohort number.
**`golf_entries`** (one per participant who plays): `participant_id` (PK), `has_handicap`,
`cdh_number` (text; stored as given, validated only for length and character set until the
owner supplies the real format), `handicap_index` (numeric, may be negative for plus
handicaps), `team_id`, `represented_school_id` (FK `organizations`, type school),
`cohort_number`, `home_club`. CHECK ties the identity field to the team's `identified_by`.
Handicap data is personal data: organizers see it, "who's going" never does.
**Four-ball groups.** A booking of up to four *is* the default four-ball: the booker plus up to
three named players. Organizers can regroup on the tee sheet with **`tee_groups`** (`slot_id`,
`group_number`, `tee_time`) and **`tee_group_members`** (`participant_id`, unique per event), so
a "3 + 1" can be merged without touching bookings or money. Results, rounds, scores and the
leaderboard come after, in Phase 7 itself.
**Series of rounds** use `events.series_id`/`round_number`. A person entering several rounds
makes one booking per round. The Duracoat "pick up to three of twelve" is a *preference* more
than a booking and is parked (decision 12).

## 3. Who sees what

| Thing | Who |
|---|---|
| Published, `public` event | anyone, including signed-out visitors |
| Published, `members_only` event | signed-in members; others get 404 |
| Draft, or an event of an organization you do not run | 404 to everyone except that organization's event managers/admins and platform admins |
| A booking and its tickets | the booker; a participant who claimed their ticket sees only their own ticket; the event's organizers see the roster; nobody else (404, never 403) |
| Organizer tools | `event_manager`, `sports_manager`, `school_admin`, `partner_admin` of the event's organization, and platform `admin`/`super_admin`. Platform events: platform admins only |
| Publish / cancel event, refund, manual confirm | organization admins and platform admins; managers create and edit drafts and run check-in (decision 14) |

Permissions go through `get_user_roles(db, user_id, organization_id)`, as everywhere else.
Prices, status, amounts, `booker_user_id`, `hold_expires_at` and ticket state are never accepted
from a request body.

## 4. API (all under `/api/v1`)

Errors use the usual `{"error": {"code", "message"}}`; lists take `limit`/`offset` and return
`X-Total-Count`. Money and booking POSTs require an `Idempotency-Key`.

**Discover and read**
* `GET /events`: filters `category`, `organization_id`, `series_id`, `from`, `to`, `mine`
  (events I booked). Only what the caller may see. Summary with going count and availability.
* `GET /events/{id}`: detail with slots and their availability, questions, consents, price,
  organizer, `my_booking`, `going_count`. Availability is `open`, `few_left` or `full`, plus
  exact seats left per slot.
* `GET /events/{id}/attendees`: **who's going** (section 5).
* `GET /event-series/{id}`: the rounds of a series.

**Book**
* `POST /events/{id}/bookings`: `{slot_id, participants[], answers[], consents[]}`. Returns
  201 with the booking in whichever state it landed in. 409 `sold_out`, 409
  `already_booked`, 409 `registration_closed`, 422 on validation. Rate limited per account.
* `GET /bookings` (mine), `GET /bookings/{id}`.
* `PATCH /bookings/{id}/participants/{position}`: fix a name or contact until the event
  starts. Never changes party size or price.
* `POST /bookings/{id}/cancel`: allowed for `pending_payment`, `waitlisted`, and `confirmed`
  *free* bookings. A confirmed *paid* booking is cancelled by the organizer (decision 6).
* `POST /bookings/{id}/pay`: Phase 6. `{phone}` starts an attempt and returns `pending`.
* `POST /bookings/{id}/payment-reference`: manual mode only, the booker enters the M-Pesa
  receipt code they paid with.
* `GET /bookings/{id}/tickets`, `GET /tickets/{code}`: the ticket page behind a QR. The code is
  the credential, so a named player without an account can open it from their email.
* `POST /tickets/claim`: a signed-in player attaches the ticket from their emailed link to
  their account.

**Organize**
* `POST /events`, `PATCH /events/{id}`, `POST /events/{id}/publish|close|cancel|complete`.
* `POST|PATCH|DELETE /events/{id}/slots[/{slot_id}]`: capacity cannot go below what is taken;
  a slot with bookings cannot be deleted.
* `PUT|DELETE /events/{id}/poster`: same attach pattern as logos.
* `POST|PATCH|DELETE /events/{id}/questions`, `.../consents`: kind and text of used ones are
  frozen; a changed consent text is a new `version`.
* `GET /events/{id}/registrations`: filter by status, slot, search; payment status included.
  `GET /events/{id}/registrations.csv`: audited, 5 an hour, cells that start with `= + - @`
  are defused, `Cache-Control: no-store`.
* `GET /events/{id}/tee-sheet`: bookings and participants grouped by slot.
* `POST /events/{id}/check-in`: `{code}`. Idempotent: scanning twice says "already checked in
  at 08:12 by ...", not an error. Void or wrong-event tickets are named as such.
* `POST /events/{id}/messages`: email every confirmed booker (or one slot) through the queue.
  Organizers never receive the addresses back; rate limited; audited.
* `POST /bookings/{id}/organizer-cancel` `{reason, refund}`, `POST /bookings/{id}/confirm-manual`
  (marks a manual payment received), `POST /bookings/{id}/refund` (Phase 6).

**Payments (Phase 6)**
* `POST /payments/callbacks/{provider}/{secret}`: public, no login, verified as in section 7.

## 5. "Who's going" and Connect

Meeting people is the point, so this is a first-class endpoint, not a report.

**A person is listed to a viewer only if all of these hold**, checked in one place by one
function built on the same visibility rules as `get_profile_for_viewer` and the directory:
1. The event's `show_attendee_list` is on, and the viewer is signed in (decision 2).
2. Their booking is `confirmed` (not pending, waitlisted or expired) and they have an account
   that is `active` (suspended and deleted people vanish).
3. Their participant row has `listed = true`.
4. Their profile exists and its visibility admits this viewer: `public` and `members_only`
   admit any signed-in member; **`connections_only` admits only an accepted connection;
   `private` admits nobody** except themselves. Strangers never see connections-only or
   private people.
5. There is no block between the two, **in either direction**. A blocked pair never appear in
   each other's lists, and nothing marks the gap.

The viewer's own entry is always shown to them. Named players without accounts are never listed.

**Counts.** `going_count` is the same for everyone (confirmed seats, everyone included). It is
an event fact, like "12 spots left", not a viewer fact, so it cannot reveal who is hidden or
who blocked whom. The list may be shorter than the count; the screen says "and 7 others".

**Each item** carries `user_id`, `profile_id`, `full_name`, the fields the directory already
shows to this viewer (school, graduation year, profession, country, company rules unchanged),
a short-lived avatar link only for people the viewer may see, and `connection`:
`none`, `pending_sent`, `pending_received`, `connected`. The **Connect button** is the
existing `POST /connections`. It already refuses yourself, and since the block fix a blocked
person gets the same 404 as a missing one. Sorted by name; paginated.

**Organizer switch.** With `show_attendee_list = false` the endpoint returns the count and the
viewer's own entry only. Organizers still see the full roster (including private people and
named players) in the organizer tools, because they need it to run the day. The booking form
tells attendees this, and the roster export is audited. This is the same rule as the school
roster.

**Free RSVP meetups** are bookings with `price_minor = 0`: one tap creates a `confirmed`
booking for one person, no hold, no payment, no questions required. Cancelling is one tap and
frees the seat.

**Tests for this are a matrix**, not a few cases: viewer (anonymous, member, connection,
blocked, organizer) × attendee profile visibility (four) × attendee state (confirmed, pending,
waitlisted, suspended, deleted, `listed=false`) × list switch. Mutation-checked.

## 6. Payments: the interface

```
class PaymentProvider(Protocol):
    name: str
    async def start(self, req: PaymentRequest) -> StartResult
    async def verify_callback(self, headers, raw_body: bytes) -> ProviderOutcome   # raises if not authentic
    async def query(self, provider_ref: str) -> ProviderOutcome                    # for lost callbacks
    async def refund(self, req: RefundRequest) -> RefundResult                     # optional per provider
```
`PaymentRequest` is `{attempt_id, amount_minor, currency, reference, payer_phone,
callback_url, idempotency_key}`. `ProviderOutcome` is `{status: succeeded|failed|pending,
provider_ref, receipt_number, amount_minor, currency, shortcode, payer_msisdn}`. The booking
code never imports a provider.

1. **Fake provider.** Succeeds, fails or hangs depending on the phone number used, so every
   branch can be driven from a test and by hand. It delivers its result by calling *our own
   callback URL* with a signature, so the real callback code runs in every test. It refuses to
   load unless `ENVIRONMENT=development` (tested, like `seed-demo`).
2. **Manual M-Pesa confirmation** (interim, decision 1). The booker pays by paybill or till
   using the booking `reference` as the account number, then enters the M-Pesa code on the
   booking. The organizer sees code and amount beside each booking and confirms it (audited).
   It uses the same states and the same hold machinery, with a long `hold_minutes`.
3. **M-Pesa Daraja STK Push.** The phone gets a PIN prompt; Safaricom calls our callback with
   the result. Daraja details (endpoints, callback shape, IP ranges, whether the paybill/till
   and passkey flows differ, status-query rules) **must be read from the current Safaricom
   documentation before this is built**, and the real thing can only be tried from a public
   HTTPS URL once credentials and go-live approval exist.
4. **Cards**: a gateway chosen later with the owner (Pesapal, Flutterwave, DPO, Paystack have
   not been compared).

Amounts are whole minor units end to end. M-Pesa takes whole shillings, so for M-Pesa events
`price_minor` must be a multiple of 100, checked when the event is published (decision 11).

## 7. Payments: making callbacks safe

* **The callback is a hint, never proof.** Provider callbacks (Daraja's are not signed) can be
  forged or repeated, and the browser's "I paid" is worthless. So the handler (1) writes the raw
  event to `provider_events` first (a replay hits the unique key and does nothing), (2) checks
  the secret path segment, which is 192 bits and unique per attempt (stored hashed), (3) asks the
  provider `query(provider_ref)` and trusts *that* answer, (4) compares amount, currency,
  shortcode and attempt id against what we stored, and only then (5) settles in one transaction
  that locks the attempt, the booking and the slot, in that order.
* **Terminal states are sticky.** A second success for an attempt does nothing. A success for a
  *second* attempt on an already-paid booking is an overpayment: recorded, flagged
  `needs_refund`, and put in the organizer's queue. An amount that does not match is recorded
  as `amount_mismatch` and never confirms anything.
* **Exactly one confirmation email and one set of tickets**, however many callbacks arrive.
  Tests fire 50 identical callbacks in parallel and expect one of everything.
* **Unavailable provider = pending, not failed.** If `start` cannot reach the provider the
  attempt stays `pending`/`unknown` and the sweeper asks the provider later; the booker is not
  told they failed to pay when we do not know.
* **Lost callbacks.** The sweeper (worker, every minute) calls `query` for attempts older than
  90 seconds that are still pending.
* **Logging.** Phone numbers are masked, receipts and callback bodies never go to logs or
  Sentry (the existing scrubber is extended to cover them), tokens never appear in URLs that
  are logged.

## 8. When a payment arrives after the hold expired

A hold is a promise to the *next* person, so it must end on time; but a person who has paid
must not lose their money. Rules, in order:

1. **No expiry while a payment is in flight.** The sweeper does not expire a booking that has a
   `pending` attempt started less than 3 minutes ago; it first calls `query`. This removes the
   common case (an STK prompt answered in the last seconds of the hold).
2. **Payment succeeded, booking `expired`, seats still free** (nobody took them):
   re-take the seats with the same locked, checked update and set `confirmed`. Audit row
   "late payment accepted". Tickets and email as normal.
3. **Payment succeeded, seats gone**: the booking stays `expired`; the payment is recorded as
   `succeeded` and flagged `unallocated`. The booker is emailed immediately: "your payment
   arrived after your reservation ended and the places were taken". The organizer sees it in a
   *Payments needing action* queue and either refunds (Phase 6 refund, audited) or moves the
   money to a waitlist place or another slot. **Money is never silently kept and never silently
   returned.** (Automatic refunds are decision 5.)
4. **Payment succeeded, booking `cancelled`** by the booker or organizer: same as 3.
5. **Payment failed**: the attempt is `failed`; the booking stays `pending_payment` until the
   hold ends, so the booker can try again (up to 3 attempts).

## 9. Capacity safety

**Rule.** All seat changes happen inside one function, `change_seats(slot_id, ...)`, in a
transaction that starts with `SELECT ... FROM event_slots WHERE id = :id FOR UPDATE`. The
second person to want the last seat waits for the first to finish and then sees the truth.
Lock order everywhere is **slot, then bookings by id ascending**, so two operations cannot
deadlock. `lock_timeout` is 3 seconds; a timeout is a retryable 503, never a wrong answer.

Inside the lock, in this order:
1. **Release expired holds** for this slot (`pending_payment` with `hold_expires_at < now()`
   and no payment in flight): mark `expired`, subtract their seats. *Capacity is correct
   without the worker.* The worker's sweep only makes it timely and sends emails.
2. Check `capacity - confirmed - held >= party_size`.
3. Insert the booking and add to the counter, or insert it as `waitlisted`.
4. After any release (cancel, expire, refund), **promote the waitlist** in the same
   transaction: the earliest `waitlisted` booking whose party fits, strict arrival order, a
   party that does not fit keeps its place (decision 4). Paid events: the promoted booking gets
   an offer window (default 2 hours) as a `pending_payment` hold; free events: straight to
   `confirmed`.

**Idempotency, two layers.** The Idempotency-Key middleware replays an identical retry. Behind
it, `UNIQUE (booker_user_id, idempotency_key)` plus the stored `request_sha256` guarantees that
a retry which got past Redis (Redis restarted, key evicted) returns the *same booking* instead
of making a second one, and a reused key with different content is a 422.

**Counters can never drift silently.** (a) CHECK constraints refuse impossible values.
(b) `seats_held`/`seats_confirmed` are changed in exactly one function. (c) A test asserts, after
every concurrency scenario, that each slot's counters equal the sums recomputed from `bookings`.
(d) The worker runs the same recomputation nightly and logs a Sentry error on any mismatch.

## 10. Proving it: the concurrency tests

All run against real Postgres with separate connections (like production); none mock the lock.

1. **Last seat, two people.** Capacity 1, two accounts book at the same instant. Exactly one
   wins; the other is `sold_out` or `waitlisted`. A hook in the capacity function (a no-op in
   production) lets the test hold both transactions between "check" and "write" with a barrier,
   so the race happens *every* run instead of occasionally.
2. **Many against few.** 200 concurrent bookings, mixed party sizes 1 to 4, capacity 10, repeated
   20 times with fresh data. After each round: seats confirmed + held `<=` capacity; counters
   equal recomputed truth; seats are *fully* used when demand exceeded capacity (no
   under-booking from the lock being too coarse); waitlist is in arrival order.
3. **Same person, double-click.** The same Idempotency-Key sent 10 times at once, and 10
   different keys at once: one booking each time.
4. **Races between operations.** Cancel vs new booking vs hold expiry vs waitlist promotion on
   the same slot; payment callback vs expiry sweep (rule 2 vs rule 3 of section 8 must come out
   consistent however the interleaving falls); 50 identical callbacks.
5. **The database refuses on its own.** A raw `UPDATE` that would oversell fails on the CHECK,
   with the application code bypassed.
6. **Mutation checks, mandatory.** Remove the `FOR UPDATE`, remove the post-expiry re-check,
   remove the CHECK, remove the unique idempotency index, make promotion non-atomic: each must
   turn a named test red. The barrier test in (1) is what makes the lock-removal mutation fail
   reliably.
7. **Load run (the PLAN gate).** `scripts/load_bookings.py` fires 3,000 bookings at one event
   through the real API on the compose stack (several accounts, several slots, one hot slot).
   Run 10 times in a row; every run must end with zero overbooking and counters equal to
   truth. The CI version is the 200-task test; the 3,000 run is manual and its numbers are
   written into the PLAN gate line.

## 11. Everything else that has to be right

* **Security.** Booking and ticket reads are 404 to everyone but the booker, the claimed
  player and organizers (IDOR tests per endpoint). Price and amounts are server-computed. Hold
  hoarding is limited by one active booking per event per person plus a per-account booking
  rate limit. QR forging needs the HMAC key. CSV is defused against formula injection. Named
  players' details are only visible to the booker and organizers. No endpoint answers "does
  this email/phone have an account".
* **Notifications** go through the existing outbox/worker, ids only in the payload:
  `booking.confirmed` (with tickets), `booking.expired`, `booking.waitlisted`,
  `booking.waitlist_offer`, `booking.cancelled`, `event.cancelled`, `event.message`, and
  reminders (an hourly worker job sends those due, once, using `reminder_sent_at`). Email only
  until an Africa's Talking account exists; SMS reuses the same events later.
* **Account deletion and export.** Deleting an account cancels its pending and waitlisted
  bookings and its free bookings (seats released, waitlist promoted) and removes it from every
  "who's going". If it has a confirmed *paid* booking for a future event, deletion is refused
  with a plain message until the event has passed or the organizer has refunded (decision 10).
  Past bookings stay for accounting with the person's name replaced, as audit rows already do.
  The export includes the person's bookings and the names they gave for other players.
* **Audit.** Publish, cancel, refund, manual confirm, check-in override, CSV export, message
  sent and every late-payment decision write an audit row tagged with the organization, so an
  organization's admins can read their own trail.
* **Time.** Registration windows and holds use the database clock. All stored in UTC.
* **Seed data.** `seed-demo` gains a free meetup, a paid event, and a golf-style event with
  four slots, so the frontend has something real on day one.

## 12. Migration plan and what ships without what

Each slice is its own Alembic revision(s), its own commits, and ends with the full gate.
Down-migrations drop their enum types; `alembic check` stays clean; upgrade/downgrade/upgrade
runs in CI.

| Slice | Contents | Needs | Can go live without the next? |
|---|---|---|---|
| **5.1 Events core** | `event_series`, `events`, `event_slots`, questions, consents, organizer CRUD, publish, public list/detail, poster, audit | nothing | **Yes.** Events are published and discoverable; "Book" is simply absent. |
| **5.2 Seats and free RSVP** | `bookings`, `booking_participants`, `booking_answers`, `booking_consents`, `change_seats`, holds and expiry, my bookings, cancel, **concurrency tests 1 to 6** | 5.1 | **Yes.** Free meetups work end to end (RSVP, cancel). The concurrency gate is passed here, before any money exists. |
| **5.3 Who's going and Connect** | attendee endpoint, privacy matrix, organizer switch, `listed`, connect state | 5.2 | **Yes.** This is the "meet people" slice and can ship the moment RSVP does. |
| **5.4 Tickets and organizer day** | `tickets`, QR, claim, roster, CSV, tee sheet (by slot), check-in, messages | 5.2 | **Yes**, for free events. |
| **5.5 Manual-payment events** | `manual_mpesa` provider, payment reference, organizer confirm, payee display | 5.2, 5.4 | **Yes.** Replaces the Google Form (decision 1) without any provider. |
| **5.6 Waitlist and reminders** | waitlist states, promotion, offer windows, reminder job, nightly counter check | 5.2 | **Yes.** Until it ships, full events simply say sold out. |
| **6 Payments** | payment tables, interface, fake provider, callback inbox, settle/late/overpay logic, reconciliation report, refunds, then Daraja, then cards | 5.2 | Yes; 5.5 keeps working beside it. Real M-Pesa also waits on Safaricom credentials and approval. |
| **7 Golf** | `golf_*`, `tee_groups`, results, leaderboard | 5.4, 6 for paid | Golf can *launch* on 5.x using ordinary questions for handicap and team, then be migrated onto the structured tables, but the brief wants structured data from the start, so 7's tables should land before the first golf booking (decision 1). |

Nothing in 5.x is a data migration of existing rows: all new tables. The only existing tables
touched are additions to `seed-demo`, the account export/deletion code, and the audit
organization tagging.

## 13. Risks I am naming now

* **The 7 Nov 2026 tournament is 14 days away.** Slices 5.1, 5.2, 5.4, 5.5 and the golf fields
  are the minimum to run it in the system, and they have to be built, tested and mutation-checked
  properly in that window. If that is too tight, the Google Form carries that one event and the
  system's first event is the next one. Either is acceptable; a rushed capacity layer is not.
* Daraja approval and credentials have a lead time I do not control.
* Opening-minute traffic on one popular slot is serialized by the slot lock. At the sizes
  involved (thousands, each transaction a few milliseconds) that is fine, and the load run
  measures it; if it is not, the fix is more slots, not a different lock.
* A bot flood on a launch. Cloudflare Turnstile on the booking POST is the standard answer and
  needs a frontend change (decision 13).

## 14. Decisions I need from you

Recommended answer first in each.

1. **How does the 7 Nov golf day take money?** (a) Build slices 5.1, 5.2, 5.4, 5.5 and golf
   fields first and run it with *manual M-Pesa confirmation* (people pay the paybill/till with
   their booking reference, enter the code, the organizer confirms in one click). (b) Keep the
   Google Form for 7 Nov and launch the system with the next event. (c) Wait for Daraja.
   Recommend (a) if the date is firm, with the golf fields done as structured tables.
2. **Who's going for signed-out visitors?** Recommend: signed-out visitors see the count only;
   names need an account. And keep the extra per-person "don't list me" switch (`listed`).
3. **One active booking per person per event?** Recommend yes. It stops hoarding. The catch: a
   person who wants two separate fourballs cannot; they book a party of four.
4. **Waitlist rules.** Recommend: strict arrival order but a party that does not fit keeps its
   place and the next that fits gets the seats; paid offers last 2 hours; nobody pays to join
   the waitlist.
5. **Late payments with no seats left (section 8, rule 3).** Recommend: no automatic refund at
   first; organizer queue plus immediate email to the booker; M-Pesa refunds need a separate
   Daraja product and approval. Confirm you accept "manual, same working day".
6. **Can attendees cancel a paid, confirmed booking themselves?** Recommend no: organizer
   cancels or refunds, as the brief says. Optional later: a per-event "cancel until" date.
7. **Event visibility default.** Recommend `public` by default, `members_only` as a per-event
   option, as the brief says.
8. **Details of named players.** They are optional (name only is enough), the booker must tick
   that they may share them, and tickets go to a player's email only if the booker gave one.
   Confirm that is acceptable under the privacy text.
9. **QR tickets.** Recommend: the ticket page opens from the QR link with no login (the code
   is the credential, so a player without an account can use it), and the app draws the QR from
   the code. Say if you want the server to produce QR images instead (adds the small `segno`
   library).
10. **Deleting an account that has a paid, future booking.** Recommend refusing until the event
    has passed or been refunded. Also needed: how long financial records must be kept.
11. **Money precision.** Recommend minor units of 1/100 KES (so a second currency or cents
    never needs a migration) and, for M-Pesa events, prices in whole shillings.
12. **Series entry (Duracoat: pick up to 3 of 12 rounds).** Recommend deferring to Phase 7 and
    treating it as one booking per round; it needs the organizer's rules (is it first-come, a
    draw, a ballot?).
13. **Bot protection for launches.** Recommend adding Cloudflare Turnstile to the booking
    request before a high-demand event. It needs a small frontend change.
14. **Who may publish, cancel and refund?** Recommend: event managers and sports managers
    create and edit drafts and run check-in; school/partner admins (and platform admins)
    publish, cancel and refund for their own organization.
15. **Payee credentials.** Recommend per-payee secrets in the platform's secret store (as the
    brief requires), referenced by name from `payment_accounts`. The cost: adding a *new* payee
    means someone adds a secret and restarts. Fine for two or three payees; say if you expect
    many.
16. **SMS.** Blocked on an Africa's Talking account. Email only until then; the brief's "email
    and SMS confirmation" is half-met at launch.

## 15. Approved answers and changes (24 Oct 2026)

Decisions 1(a), 2 (count only for signed-out visitors, plus `listed`), 3 yes, 4 as written,
5 (manual refund queue, same working day), 6 no self-cancel of paid bookings, 7 public by
default, 8 yes (the owner updates the privacy text), 9 (ticket link with no login, QR drawn by
the app), 10 (refuse deletion until the event has passed or been refunded; retention length is
being confirmed with the accountant), 11 as written, 12 deferred, 13 yes but not a blocker,
14 as written, 15 as written, 16 email only. Requests to private-profile users are **not**
made 404.

**Change (a): golf details for 7 November are event questions, not the golf tables.**
Handicap, CDH number, team, school or cohort are configured as ordinary `each_participant`
questions with these reserved keys, so they can be moved without guessing:

| key | kind | meaning |
|---|---|---|
| `golf_has_handicap` | boolean | has a handicap |
| `golf_cdh_number` | text | CDH number, as typed |
| `golf_handicap_index` | number | optional |
| `golf_team` | choice | the team (option values are stable slugs, for example `yengolf_alumni`, `alumni_challenge`) |
| `golf_school` | school | school represented (a new question kind whose answer is an organization id of type school, validated) |
| `golf_cohort_number` | number | cohort number |

*Later migration into `golf_entries` (Phase 7):* a one-off, re-runnable script reads
`booking_answers` for these keys per participant and writes one `golf_entries` row each (a
`golf_teams` row is created per distinct `golf_team` option; `golf_school` becomes
`represented_school_id`). It runs in a transaction, reports counts (participants with answers,
rows written, rows skipped with the reason), refuses to overwrite an existing entry, and
leaves the answers in place until a person has checked the report. After it, the structured
tables are the source of truth and the questions are retired for that event type.

**Change (b): manual M-Pesa mode.** The M-Pesa receipt code a booker enters is stored on the
booking (`payment_reference_code`, normalized to upper case and trimmed) and a **database
unique index** (`bookings(payment_reference_code) WHERE payment_reference_code IS NOT NULL`)
means one code can belong to one booking only, ever, even across events. A code entered twice
is a 409. Manual holds are capped at **48 hours**: `events.hold_minutes` is CHECK between 5 and
2880 (not 4320), and an event may only use more than 60 minutes if its payee account is a
manual one.
