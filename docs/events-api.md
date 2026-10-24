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
