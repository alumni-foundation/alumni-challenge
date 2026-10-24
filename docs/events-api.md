# Events and bookings API (for the frontend)

Base path `/api/v1`. Errors are `{"error": {"code", "message"}}`. Money is whole minor units
(1/100 KES): `150000` = KES 1,500. Times are UTC ISO-8601; show them in Africa/Nairobi.
This file grows slice by slice; each section says which slice added it.

## Slice 5.1: events (organizers and discovery)

| Method and path | Who | Notes |
|---|---|---|
| `GET /events` | anyone | Upcoming published events you may see. Filters: `category`, `organization_id`, `series_id`, `starts_after`, `starts_before`, `q`, `past=true`, `manage=true` (needs sign-in: the events you run, drafts included), `limit`, `offset`. Total in `X-Total-Count`. |
| `GET /events/{id}` | anyone (drafts: managers only, else 404; `members_only`: signed-in only, else 404) | `EventDetail`: slots with `spots_left` and `availability` (`open`, `few_left`, `full`), `questions`, `consents`, `registration.state` (`draft`, `cancelled`, `ended`, `closed`, `not_open_yet`, `open`), `can_manage`, and (5.2) `my_booking`. |
| `POST /events`, `PATCH /events/{id}`, `DELETE /events/{id}` (draft only) | managers | |
| `POST /events/{id}/publish`, `/cancel` (`{reason}`) | admins | Cancelling also cancels every booking. |
| `POST /events/{id}/close`, `/reopen`, `/complete` | managers | |
| `PUT` / `DELETE /events/{id}/poster` | managers | Upload first with `POST /files`, purpose `event_poster`, `organization_id`. |
| `POST` / `PATCH` / `DELETE /events/{id}/slots[/{slot_id}]` | managers | Delete refused (`slot_has_bookings`) once anyone booked it. |
| `POST` / `PATCH` / `DELETE /events/{id}/questions[/{qid}]` | managers | Delete refused (`question_answered`) once answered. |
| `POST` / `PATCH` / `DELETE /events/{id}/consents[/{cid}]` | managers | Delete refused (`consent_accepted`) once accepted. |
| `POST /event-series`, `GET /event-series`, `GET /event-series/{id}` | managers | |

Once a booking exists, `price_minor`, `currency` and `max_party_size` can no longer change
(`409 event_has_bookings`).

## Slice 5.2: booking places (free RSVP works end to end)

All need sign-in.

### `POST /events/{event_id}/bookings`
Header **`Idempotency-Key`** (required, any unique string up to 255 characters; make a new one for
each user intent, re-send the same one when retrying a timed-out request: you get the same
booking back, never a second).

```json
{
  "slot_id": "uuid",
  "participants": [
    {"full_name": "Ann Alum", "listed": true},
    {"full_name": "Ben Friend", "email": "ben@example.com", "phone": "+254700000000"}
  ],
  "answers": [{"question_key": "handicap", "position": 1, "value": 12.5}],
  "accepted_consents": ["photos"],
  "others_consent_confirmed": true
}
```

* The first participant is the person booking; their email comes from their account.
* One to `max_party_size` (at most 4) participants. With more than one, `others_consent_confirmed`
  must be `true` (the booker confirms they may share the others' details).
* `answers`: `position` is the participant (1 = booker). Questions with `asked_of: "each_participant"`
  need an answer for every position; `"booker"` questions use position 1. Values by kind:
  `text`/`long_text` string, `number` number, `boolean` true/false, `choice` one option value,
  `multi_choice` list of option values, `school` a school organization id.
* `accepted_consents`: keys of the consents (all `required` ones must be listed).
* The price is never sent: it is worked out on the server.

Response `201` is a `BookingOut`. `status` is `confirmed` for a free event and `pending_payment`
for a paid one (with `hold_expires_at`: show a countdown; payment arrives in a later slice).

Errors: `401`; `404` event not visible; `409` `registration_not_open_yet` / `registration_closed` /
`registration_ended` / `registration_cancelled`, `already_booked` (one active booking per person per
event), `sold_out` (not enough places in that slot for the whole group), `too_many_holds` (3 unpaid
bookings at once); `422` `party_too_large`, `others_consent_required`, `invalid_slot`,
`answer_required`, `invalid_answer`, `unknown_question`, `consent_required`, `unknown_consent`,
`idempotency_key_reused`; `429` too many attempts (20 per hour); `503` `busy` (try again in a moment).

### Other booking endpoints

| Method and path | Notes |
|---|---|
| `GET /bookings?status=&limit=&offset=` | My bookings, newest first. `X-Total-Count`. |
| `GET /bookings/{id}` | The booker or an organizer of the event; anyone else gets `404`. |
| `POST /bookings/{id}/cancel` `{reason?}` | Frees the places. Repeating it is harmless. Booker can cancel until the event starts, except a paid confirmed booking (`403`: contact the organizer). `can_cancel` on the booking says whether to show the button. |
| `PATCH /bookings/{id}/participants/{position}` | Fix `full_name`, `email`, `phone` or `listed` (hide me from "who's going") while the booking is active. Participant 1's email cannot be changed. |

`BookingOut` has `reference` (like `AC-7K3M9QXD`, to show and quote), `event`, `slot`,
`party_size`, `unit_price_minor`, `amount_minor`, `currency`, `hold_expires_at`, `can_cancel`,
`participants` (`claimed` is for tickets, slice 5.4), `answers`, `consents`.

### Emails (queued, sent by the worker)
`booking.confirmed`, `booking.cancelled`, `booking.expired` (hold ran out), and when an organizer
cancels an event, one cancellation email per booking.

### Account deletion
`POST /auth/me/delete` is refused (`409 paid_booking_open`) while the person has a paid, confirmed
booking for an event that has not ended. Other open bookings are cancelled. The data export
(`GET /auth/me/export`) includes `event_bookings`.

## Slice 5.4: tickets and the organizer's day

### Tickets (one per person in a confirmed booking)
A booking gets its tickets the moment it is `confirmed` (free events: at booking time). Unpaid
bookings have none yet. `code` is 64 hex characters (a 128-bit ticket id followed by a 128-bit
signature, 256 bits in all): **draw the QR from it in the app**; the QR holds only the code. The code is also the credential for the ticket page.

| Method and path | Who | Notes |
|---|---|---|
| `GET /tickets/{code}` | **anyone, no sign-in** | The ticket page behind the QR/email link: `holder_name`, `status` (`valid`, `checked_in`, `void`), event, slot, `booking_reference`. No email or phone. Wrong or revoked code: `404`. `Cache-Control: no-store`. Limited to 600 requests per 15 minutes per IP. |
| `POST /tickets/claim` `{code}` | signed in | Attach the ticket from the emailed link to my account (`409 already_claimed` if someone else has it; repeating is fine). |
| `GET /tickets/mine` | signed in | Tickets for events that have not ended: all in bookings I made, plus ones I claimed. |
| `GET /bookings/{id}/tickets` | booker, organizers | All tickets of a booking. |
| `POST /bookings/{id}/tickets/{position}/reissue` | booker, organizers | New code for one person; the old QR stops working. Refused once checked in. |

A ticket is `void` whenever its booking is not `confirmed` (cancelled, refunded).

Emails: the booker's confirmation lists every ticket link; a named player whose email the booker
gave also gets their own link, as a separate queued email (a failed send retries only that one).

### Organizer tools (event managers and above; others get `403`, signed-out `401`)

| Method and path | Notes |
|---|---|
| `GET /events/{id}/registrations?status=&slot_id=&q=&limit=&offset=` | Everyone booked, with contact details, answers, and each person's ticket status. `X-Total-Count`. |
| `GET /events/{id}/registrations.csv` | One row per person plus a column per question. Audited, **5 an hour**, `no-store`. |
| `GET /events/{id}/tee-sheet` | Active bookings grouped by slot (capacity, taken, people, answers). |
| `POST /events/{id}/check-in` `{code}` | Scan a ticket. `result` is `checked_in` or `already_checked_in` (not an error; same `checked_in_at`). `404` not one of ours; `409 wrong_event` / `void`. |
| `POST /events/{id}/messages` `{subject, body, slot_id?}` | Emails everyone with a confirmed booking (or one slot). Returns `recipient_count`, never addresses. **5 an hour.** One-line subject. |

## Slice 5.5: paying by hand (manual M-Pesa)

For paid events paid straight to the organizer's paybill or till, before any payment provider is
connected. The person pays in M-Pesa, pastes the confirmation code from the message into the
booking, and an organization admin matches it to a payment and confirms.

### Payee: where the money goes
| Method and path | Who | Notes |
|---|---|---|
| `POST /payment-accounts` `{organization_id, label, mpesa_kind: paybill\|till, shortcode_or_till}` | admin of that organization (platform admins for `organization_id: null`) | Number is 4 to 10 digits. `403` for event managers and others. 30 writes an hour. |
| `GET /payment-accounts` | signed in | Only accounts of organizations I administer (all of them for platform admins). |
| `PATCH /payment-accounts/{id}` `{label?, shortcode_or_till?, active?}` | admin of that organization | `404` for anyone else. The number cannot change once someone booked an event paid to it (`409 payment_account_in_use`); switch the account off and make a new one. |

Events take `payment_account_id` on create and update (same organization, switched on; `422
invalid_payee` / `payee_inactive`). It cannot change once anyone has booked
(`409 event_has_bookings`). The event detail then has `payment: {method, kind, number,
payee_name, currency}`: show it on the event page. **A paid event cannot be published without
an active payee (`422 payee_required`).** `hold_minutes` above 60 (up to 2880, 48
hours) is allowed only when the event has a payee (`422 hold_too_long` otherwise).

### On every booking: `payment`
`null` for a free event or one with no payee. Otherwise:
`{payee: {kind, number, payee_name, ...}, account_reference, state, code, submitted_at,
decided_at, rejection_reason, marked_paid_by_hand, can_submit_code}`.
* **Paybill:** tell the person to type `account_reference` (the booking reference) as the account
  number. **Till:** there is no account number (`account_reference` is `null`); the code they send
  is how the payment is matched.
* `state` is `null` (no code yet), `awaiting_confirmation`, `confirmed`, `rejected`,
  `needs_refund` or `refunded`. `rejection_reason` is set only while `rejected`.
* `can_submit_code` tells the app whether to show the code box. A code can also be sent after the
  hold ran out or the booking was cancelled (the person may have paid anyway).

### The booker
`POST /bookings/{id}/payment-reference` `{code}`: trims and upper-cases; 8 to 12 letters and
numbers (`422` otherwise). Returns the booking. Sending the same code again is harmless. `409`:
`payment_code_used` (a code can belong to one booking, ever, across events; the message never says
whose), `payment_already_submitted` (a different code is already waiting), `payment_not_accepted`
(booking confirmed, refunded, waitlisted or event over), `not_manual_payment`. Only the booker:
everyone else, organizers included, gets `404`. Limits: 10 an hour per account, 5 an hour per
booking, 30 an hour per address (`429`). The booking **stays held**; sending a code does not
confirm anything.

### The organizer (organization admins; event managers get `403`, strangers `404`)
| Method and path | Notes |
|---|---|
| `POST /bookings/{id}/confirm-manual` | Payment received. Held places become confirmed, tickets are made and the booker emailed. Repeating changes and sends nothing. **If the hold had run out:** places still free means it is confirmed again ("late payment accepted"); places gone, or the booking was cancelled, means the booking stays as it is and `payment.state` becomes `needs_refund`. Read `status` and `payment.state` in the answer. |
| `POST /bookings/{id}/mark-paid` `{reason}` | The money arrived with no M-Pesa code (cash, a transfer). **A written reason, 3 to 500 characters, is required** and goes in the audit row. Settles exactly like a confirmed code, late-payment rules included. Afterwards `payment.marked_paid_by_hand` is `true` and `payment.code` is `null`. Repeating it changes nothing. `409 not_a_paid_booking` for a free booking; `409 payment_already_settled` once the payment is owed back or refunded. |
| `POST /bookings/{id}/reject-manual` `{reason}` | The code matches no payment. Booking and hold stay as they are, the code is released, the booker is emailed the reason and may send another. |
| `POST /bookings/{id}/mark-refunded` `{note?}` | The organizer sent the money back. Only from `needs_refund`. A cancelled booking that had been confirmed becomes `refunded`. |
| `POST /bookings/{id}/organizer-cancel` `{reason, refund}` | Cancels and frees the places. `refund: true` on a confirmed payment moves it to `needs_refund`. |
| `GET /events/{id}/payments?state=awaiting_confirmation\|needs_refund` | The money queue (default both), oldest first, same rows as registrations. `X-Total-Count`. |
| `GET /events/{id}/registrations?payment_state=` | Rows now carry `payment: {state, code, submitted_at, decided_at, rejection_reason, marked_paid_by_hand, note}`; `q` also matches the M-Pesa code. |

Cancelling an event moves every confirmed payment to `needs_refund`. Every confirm, reject,
refund and late-payment decision writes an audit row for the organization.

### Emails to the booker (only the booker, never other players)
Code received; booking confirmed with tickets (the existing email; it says so when the payment came after the hold ended but the places were still free); code not matched (with the
organizer's reason); payment arrived too late and a refund is coming; cancelled with a refund
coming; refund sent.
