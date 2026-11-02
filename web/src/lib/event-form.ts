/** Pure helpers for the event editor: Nairobi time in and out, the form's rules, and the request bodies. */
import type { EventCategory, EventCreate, EventDetail, EventUpdate, EventVisibility, SlotUpdate } from "./api/types";

/** Kenya has no daylight saving, so Nairobi is always UTC+3. */
const OFFSET_HOURS = 3;
const OFFSET = "+03:00";

export const TITLE_MIN = 2;
export const TITLE_MAX = 255;
export const DESCRIPTION_MAX = 10_000;
export const VENUE_NAME_MAX = 255;
export const VENUE_ADDRESS_MAX = 500;
export const PHONE_MAX = 40;
export const CAPACITY_MAX = 100_000;
/** Mirrors the backend's MAX_PARTY_SIZE. */
export const PARTY_SIZE_MAX = 4;
export const CANCEL_REASON_MIN = 3;

export const CATEGORY_OPTIONS: { value: EventCategory; label: string }[] = [
  { value: "homecoming", label: "Homecoming" },
  { value: "golf_tournament", label: "Golf tournament" },
  { value: "sports", label: "Sports" },
  { value: "networking", label: "Networking" },
  { value: "forum", label: "Forum" },
  { value: "mentorship", label: "Mentorship" },
  { value: "leadership", label: "Leadership" },
  { value: "philanthropy", label: "Philanthropy" },
  { value: "other", label: "Other" },
];

export const VISIBILITY_OPTIONS: { value: EventVisibility; label: string; help: string }[] = [
  { value: "public", label: "Public", help: "Anyone can see it, signed in or not." },
  { value: "members_only", label: "Members only", help: "Only signed-in members can see it." },
];

export type EventFormValues = {
  title: string;
  description: string;
  category: EventCategory | "";
  visibility: EventVisibility;
  /** "" is the platform itself; otherwise an organization id. */
  organizationId: string;
  /** The date fields hold what a datetime-local input holds ("2026-11-07T18:00"), read as Nairobi time. */
  startsAt: string;
  endsAt: string;
  venueName: string;
  venueAddress: string;
  registrationOpensAt: string;
  registrationClosesAt: string;
  /** Whole number, or "" for no limit. */
  capacity: string;
  maxPartySize: string;
  contactEmail: string;
  contactPhone: string;
};

export const EMPTY_VALUES: EventFormValues = {
  title: "",
  description: "",
  category: "",
  visibility: "public",
  organizationId: "",
  startsAt: "",
  endsAt: "",
  venueName: "",
  venueAddress: "",
  registrationOpensAt: "",
  registrationClosesAt: "",
  capacity: "",
  maxPartySize: "1",
  contactEmail: "",
  contactPhone: "",
};

const LOCAL = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/;

/** An instant from the API as the text a datetime-local input holds, in Nairobi time. */
export function isoToNairobi(iso: string): string {
  return new Date(new Date(iso).getTime() + OFFSET_HOURS * 3_600_000).toISOString().slice(0, 16);
}

/** "2026-11-07T18:00" read as Nairobi time, as an instant. NaN when it is not a real date and time. */
export function nairobiMs(local: string): number {
  if (!LOCAL.test(local)) return NaN;
  const ms = Date.parse(`${local}:00${OFFSET}`);
  // Date.parse rolls "2026-02-31" over to March; a round trip catches it.
  return Number.isNaN(ms) || isoToNairobi(new Date(ms).toISOString()) !== local ? NaN : ms;
}

/** The timezone-aware value the API wants: "2026-11-07T18:00:00+03:00". */
export function nairobiToIso(local: string): string {
  return `${local}:00${OFFSET}`;
}

/** The form's values for an event that already exists. */
export function valuesFromEvent(e: EventDetail): EventFormValues {
  return {
    title: e.title,
    description: e.description ?? "",
    category: e.category,
    visibility: e.visibility,
    organizationId: e.organizer?.id ?? "",
    startsAt: isoToNairobi(e.starts_at),
    endsAt: isoToNairobi(e.ends_at),
    venueName: e.venue_name ?? "",
    venueAddress: e.venue_address ?? "",
    registrationOpensAt: e.registration.opens_at ? isoToNairobi(e.registration.opens_at) : "",
    registrationClosesAt: e.registration.closes_at ? isoToNairobi(e.registration.closes_at) : "",
    capacity: e.slots.length === 1 && e.slots[0].capacity !== null ? String(e.slots[0].capacity) : "",
    maxPartySize: String(e.max_party_size),
    contactEmail: e.contact_email ?? "",
    contactPhone: e.contact_phone ?? "",
  };
}

export type FormErrors = Partial<Record<keyof EventFormValues, string>>;

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const WHOLE = /^\d+$/;

/**
 * The form's rules, in the same words as the server where it has them. `checkPast` is on for a new event (and for
 * a start the person has changed): the start cannot already have passed. Empty means the form may be sent.
 */
export function validateEventForm(v: EventFormValues, opts: { now?: number; checkPast: boolean; editableCapacity?: boolean; organizationRequired?: boolean }): FormErrors {
  const err: FormErrors = {};
  const now = opts.now ?? Date.now();
  const title = v.title.trim();
  if (title.length < TITLE_MIN) err.title = `Give the event a title of at least ${TITLE_MIN} characters.`;
  else if (title.length > TITLE_MAX) err.title = `The title can be ${TITLE_MAX} characters at most.`;
  if (v.description.length > DESCRIPTION_MAX) err.description = `The description can be ${DESCRIPTION_MAX.toLocaleString("en-KE")} characters at most.`;
  if (!v.category) err.category = "Choose a category.";
  if (opts.organizationRequired && !v.organizationId) err.organizationId = "Choose who runs this event.";

  const start = nairobiMs(v.startsAt);
  const end = nairobiMs(v.endsAt);
  const opens = v.registrationOpensAt ? nairobiMs(v.registrationOpensAt) : null;
  const closes = v.registrationClosesAt ? nairobiMs(v.registrationClosesAt) : null;

  if (!v.startsAt) err.startsAt = "Choose when the event starts.";
  else if (Number.isNaN(start)) err.startsAt = "Enter a real date and time.";
  else if (opts.checkPast && start <= now) err.startsAt = "The start can’t be in the past.";

  if (!v.endsAt) err.endsAt = "Choose when the event ends.";
  else if (Number.isNaN(end)) err.endsAt = "Enter a real date and time.";
  else if (!Number.isNaN(start) && end <= start) err.endsAt = "The event must end after it starts.";
  else if (opts.checkPast && end <= now) err.endsAt = "The end can’t be in the past.";

  if (opens !== null && Number.isNaN(opens)) err.registrationOpensAt = "Enter a real date and time.";
  if (closes !== null && Number.isNaN(closes)) err.registrationClosesAt = "Enter a real date and time.";
  else if (closes !== null && opens !== null && !Number.isNaN(opens) && closes <= opens) {
    err.registrationClosesAt = "Registration must close after it opens.";
  } else if (closes !== null && !Number.isNaN(end) && closes > end) {
    err.registrationClosesAt = "Registration must close before the event ends.";
  }

  if (v.venueName.length > VENUE_NAME_MAX) err.venueName = `The venue name can be ${VENUE_NAME_MAX} characters at most.`;
  if (v.venueAddress.length > VENUE_ADDRESS_MAX) err.venueAddress = `The address can be ${VENUE_ADDRESS_MAX} characters at most.`;

  if (opts.editableCapacity !== false && v.capacity.trim() !== "") {
    const n = Number(v.capacity);
    if (!WHOLE.test(v.capacity.trim()) || n < 1 || n > CAPACITY_MAX) {
      err.capacity = `Enter a whole number from 1 to ${CAPACITY_MAX.toLocaleString("en-KE")}, or leave it empty for no limit.`;
    }
  }
  const party = Number(v.maxPartySize);
  if (!WHOLE.test(v.maxPartySize.trim()) || party < 1 || party > PARTY_SIZE_MAX) err.maxPartySize = `Enter a whole number from 1 to ${PARTY_SIZE_MAX}.`;

  if (v.contactEmail.trim() && !EMAIL.test(v.contactEmail.trim())) err.contactEmail = "Enter a valid email address.";
  if (v.contactPhone.length > PHONE_MAX) err.contactPhone = `The phone number can be ${PHONE_MAX} characters at most.`;
  return err;
}

const orNull = (s: string) => (s.trim() === "" ? null : s.trim());

/** The body for POST /events. Free events only: the price is always 0 and no payment account is sent. */
export function toCreate(v: EventFormValues): EventCreate {
  return {
    organization_id: v.organizationId || null,
    title: v.title.trim(),
    description: orNull(v.description),
    category: v.category as EventCategory,
    visibility: v.visibility,
    starts_at: nairobiToIso(v.startsAt),
    ends_at: nairobiToIso(v.endsAt),
    venue_name: orNull(v.venueName),
    venue_address: orNull(v.venueAddress),
    registration_opens_at: v.registrationOpensAt ? nairobiToIso(v.registrationOpensAt) : null,
    registration_closes_at: v.registrationClosesAt ? nairobiToIso(v.registrationClosesAt) : null,
    price_minor: 0,
    currency: "KES",
    max_party_size: Number(v.maxPartySize),
    // The server's own defaults, spelled out because the generated type makes them required.
    hold_minutes: 15,
    waitlist_enabled: false,
    show_attendee_list: true,
    reminder_hours_before: 24,
    contact_email: orNull(v.contactEmail),
    contact_phone: orNull(v.contactPhone),
    capacity: v.capacity.trim() === "" ? null : Number(v.capacity),
  };
}

/**
 * The body for PATCH /events/{id}: only what the person changed, so an edit never touches fields it did not mean to
 * (the server refuses to change the group size once people have booked, for example). Price is never sent.
 */
export function toUpdate(v: EventFormValues, before: EventFormValues): EventUpdate {
  const out: EventUpdate = {};
  if (v.title.trim() !== before.title.trim()) out.title = v.title.trim();
  if (v.description.trim() !== before.description.trim()) out.description = orNull(v.description);
  if (v.category !== before.category && v.category) out.category = v.category;
  if (v.visibility !== before.visibility) out.visibility = v.visibility;
  if (v.startsAt !== before.startsAt) out.starts_at = nairobiToIso(v.startsAt);
  if (v.endsAt !== before.endsAt) out.ends_at = nairobiToIso(v.endsAt);
  if (v.venueName.trim() !== before.venueName.trim()) out.venue_name = orNull(v.venueName);
  if (v.venueAddress.trim() !== before.venueAddress.trim()) out.venue_address = orNull(v.venueAddress);
  if (v.registrationOpensAt !== before.registrationOpensAt) out.registration_opens_at = v.registrationOpensAt ? nairobiToIso(v.registrationOpensAt) : null;
  if (v.registrationClosesAt !== before.registrationClosesAt) out.registration_closes_at = v.registrationClosesAt ? nairobiToIso(v.registrationClosesAt) : null;
  if (v.maxPartySize.trim() !== before.maxPartySize.trim()) out.max_party_size = Number(v.maxPartySize);
  if (v.contactEmail.trim() !== before.contactEmail.trim()) out.contact_email = orNull(v.contactEmail);
  if (v.contactPhone.trim() !== before.contactPhone.trim()) out.contact_phone = orNull(v.contactPhone);
  return out;
}

/**
 * Capacity lives on the slot, not the event. For an event with exactly one slot, the slot change to send after the
 * event itself is saved: the new capacity, and (when the slot covered the whole event) the new start and end.
 */
export function slotChanges(
  v: EventFormValues,
  before: EventFormValues,
  event: Pick<EventDetail, "starts_at" | "ends_at" | "slots">,
): { slotId: string; body: SlotUpdate } | null {
  if (event.slots.length !== 1) return null;
  const slot = event.slots[0];
  const body: SlotUpdate = {};
  if (v.capacity.trim() !== before.capacity.trim()) body.capacity = v.capacity.trim() === "" ? null : Number(v.capacity);
  const coversEvent = slot.starts_at === event.starts_at && slot.ends_at === event.ends_at;
  if (coversEvent && (v.startsAt !== before.startsAt || v.endsAt !== before.endsAt)) {
    body.starts_at = nairobiToIso(v.startsAt);
    body.ends_at = nairobiToIso(v.endsAt);
  }
  return Object.keys(body).length ? { slotId: slot.id, body } : null;
}

export type EventActions = { save: boolean; publish: boolean; close: boolean; reopen: boolean; cancel: boolean; remove: boolean };

/** Which buttons an event in this state offers. */
export function actionsFor(status: string): EventActions {
  return {
    save: status === "draft" || status === "published" || status === "closed",
    publish: status === "draft",
    close: status === "published",
    reopen: status === "closed",
    cancel: status === "published" || status === "closed",
    remove: status === "draft",
  };
}
