import { describe, expect, it } from "vitest";
import {
  actionsFor, EMPTY_VALUES, isoToNairobi, nairobiMs, nairobiToIso, slotChanges, toCreate, toUpdate, validateEventForm,
  type EventFormValues,
} from "./event-form";

// 2026-11-01 12:00 in Nairobi.
const NOW = Date.parse("2026-11-01T12:00:00+03:00");
const good: EventFormValues = {
  ...EMPTY_VALUES,
  title: "Homecoming 2026",
  category: "homecoming",
  startsAt: "2026-12-05T10:00",
  endsAt: "2026-12-05T16:00",
};
const check = (patch: Partial<EventFormValues>, checkPast = true) => validateEventForm({ ...good, ...patch }, { now: NOW, checkPast });

describe("Nairobi time", () => {
  it("reads and writes UTC+3", () => {
    expect(nairobiToIso("2026-11-07T18:00")).toBe("2026-11-07T18:00:00+03:00");
    expect(new Date(nairobiToIso("2026-11-07T18:00")).toISOString()).toBe("2026-11-07T15:00:00.000Z");
    expect(isoToNairobi("2026-11-07T15:00:00Z")).toBe("2026-11-07T18:00");
    expect(isoToNairobi("2026-11-07T22:30:00+00:00")).toBe("2026-11-08T01:30");
  });

  it("rejects dates that are not real", () => {
    expect(nairobiMs("2026-02-31T10:00")).toBeNaN();
    expect(nairobiMs("2026-11-07")).toBeNaN();
    expect(nairobiMs("2026-11-07T18:00")).not.toBeNaN();
  });
});

describe("validateEventForm", () => {
  it("accepts a complete free event", () => {
    expect(check({})).toEqual({});
  });

  it("applies the server's limits to the title and description", () => {
    expect(check({ title: "A" }).title).toBeDefined();
    expect(check({ title: "  A  " }).title).toBeDefined();
    expect(check({ title: "A".repeat(255) }).title).toBeUndefined();
    expect(check({ title: "A".repeat(256) }).title).toBeDefined();
    expect(check({ description: "x".repeat(10_000) }).description).toBeUndefined();
    expect(check({ description: "x".repeat(10_001) }).description).toBeDefined();
  });

  it("needs a category", () => {
    expect(check({ category: "" }).category).toBeDefined();
  });

  it("needs the end to come after the start", () => {
    expect(check({ endsAt: "2026-12-05T10:00" }).endsAt).toMatch(/after it starts/);
    expect(check({ endsAt: "2026-12-04T10:00" }).endsAt).toMatch(/after it starts/);
  });

  it("keeps a new event out of the past, but lets an old draft be edited", () => {
    expect(check({ startsAt: "2026-10-01T10:00", endsAt: "2026-10-01T12:00" }).startsAt).toMatch(/past/);
    expect(check({ startsAt: "2026-10-01T10:00", endsAt: "2026-10-01T12:00" }, false)).toEqual({});
  });

  it("needs registration to close after it opens and before the event ends", () => {
    expect(check({ registrationOpensAt: "2026-11-10T09:00", registrationClosesAt: "2026-11-10T09:00" }).registrationClosesAt).toMatch(/after it opens/);
    expect(check({ registrationClosesAt: "2026-12-05T16:01" }).registrationClosesAt).toMatch(/before the event ends/);
    expect(check({ registrationClosesAt: "2026-12-05T16:00" }).registrationClosesAt).toBeUndefined();
    expect(check({ registrationOpensAt: "2026-11-10T09:00", registrationClosesAt: "2026-12-01T09:00" })).toEqual({});
  });

  it("checks capacity, group size and contact details", () => {
    expect(check({ capacity: "0" }).capacity).toBeDefined();
    expect(check({ capacity: "12.5" }).capacity).toBeDefined();
    expect(check({ capacity: "100001" }).capacity).toBeDefined();
    expect(check({ capacity: "150" }).capacity).toBeUndefined();
    expect(check({ maxPartySize: "5" }).maxPartySize).toBeDefined();
    expect(check({ maxPartySize: "4" }).maxPartySize).toBeUndefined();
    expect(check({ contactEmail: "nope" }).contactEmail).toBeDefined();
    expect(check({ contactEmail: "events@example.com" }).contactEmail).toBeUndefined();
    expect(check({ contactPhone: "0".repeat(41) }).contactPhone).toBeDefined();
  });
});

describe("request bodies", () => {
  it("creates a free event with Nairobi-aware times", () => {
    const body = toCreate({ ...good, organizationId: "org-1", capacity: "150", maxPartySize: "2", registrationClosesAt: "2026-12-01T09:00", contactEmail: " events@example.com " });
    expect(body).toMatchObject({
      organization_id: "org-1",
      title: "Homecoming 2026",
      price_minor: 0,
      currency: "KES",
      starts_at: "2026-12-05T10:00:00+03:00",
      ends_at: "2026-12-05T16:00:00+03:00",
      registration_opens_at: null,
      registration_closes_at: "2026-12-01T09:00:00+03:00",
      capacity: 150,
      max_party_size: 2,
      contact_email: "events@example.com",
      description: null,
    });
    expect(body).not.toHaveProperty("payment_account_id");
  });

  it("runs the event itself when no organizer is chosen, and leaves capacity open when empty", () => {
    const body = toCreate(good);
    expect(body.organization_id).toBeNull();
    expect(body.capacity).toBeNull();
  });

  it("sends only what changed on an edit, and clears a field with null", () => {
    const before = { ...good, venueName: "Main hall", contactPhone: "0700" };
    expect(toUpdate(before, before)).toEqual({});
    expect(toUpdate({ ...before, title: "New title", venueName: "", endsAt: "2026-12-05T17:00" }, before)).toEqual({
      title: "New title",
      venue_name: null,
      ends_at: "2026-12-05T17:00:00+03:00",
    });
  });
});

describe("slotChanges", () => {
  const slot = (over = {}) => ({ id: "s1", label: null, starts_at: "2026-12-05T07:00:00Z", ends_at: "2026-12-05T13:00:00Z", capacity: 100, seats_confirmed: 0, seats_held: 0, position: 0, spots_left: 100, availability: "open", ...over });
  const event = { starts_at: "2026-12-05T07:00:00Z", ends_at: "2026-12-05T13:00:00Z", slots: [slot()] };
  const before = { ...good, capacity: "100" };

  it("changes nothing when capacity and times are the same", () => {
    expect(slotChanges(before, before, event)).toBeNull();
  });

  it("updates capacity, and empties it for no limit", () => {
    expect(slotChanges({ ...before, capacity: "80" }, before, event)).toEqual({ slotId: "s1", body: { capacity: 80 } });
    expect(slotChanges({ ...before, capacity: "" }, before, event)?.body.capacity).toBeNull();
  });

  it("moves a whole-event slot with the event, but not a custom one", () => {
    const moved = { ...before, endsAt: "2026-12-05T17:00" };
    expect(slotChanges(moved, before, event)?.body).toEqual({ starts_at: "2026-12-05T10:00:00+03:00", ends_at: "2026-12-05T17:00:00+03:00" });
    expect(slotChanges(moved, before, { ...event, slots: [slot({ ends_at: "2026-12-05T10:00:00Z" })] })).toBeNull();
  });

  it("leaves events with several slots alone", () => {
    expect(slotChanges({ ...before, capacity: "5" }, before, { ...event, slots: [slot(), slot({ id: "s2" })] })).toBeNull();
  });
});

describe("actionsFor", () => {
  it("offers the right buttons for each status", () => {
    expect(actionsFor("draft")).toMatchObject({ save: true, publish: true, remove: true, close: false, cancel: false });
    expect(actionsFor("published")).toMatchObject({ save: true, close: true, cancel: true, publish: false, remove: false });
    expect(actionsFor("closed")).toMatchObject({ reopen: true, cancel: true, close: false });
    expect(actionsFor("cancelled")).toEqual({ save: false, publish: false, close: false, reopen: false, cancel: false, remove: false });
    expect(actionsFor("completed").save).toBe(false);
  });
});
