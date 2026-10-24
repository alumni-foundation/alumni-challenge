import { describe, expect, it } from "vitest";
import { ApiError } from "./api/client";
import { bookingProblem } from "./booking-problem";
import { bookingChip, isActiveBooking, isTicketCode, newIdempotencyKey, priceText, rangeText, seatsText, ticketChip, timeLeft, whenText } from "./events";

describe("priceText", () => {
  it("says Free for nothing, and writes whole KES without decimals", () => {
    expect(priceText(0)).toBe("Free");
    expect(priceText(350000)).toBe("KES 3,500");
    expect(priceText(150050)).toBe("KES 1,500.50");
  });
});

describe("seatsText", () => {
  it("handles capped, full and uncapped events", () => {
    expect(seatsText(60)).toBe("60 seats left");
    expect(seatsText(1)).toBe("1 seat left");
    expect(seatsText(0)).toBe("Full");
    expect(seatsText(null)).toBeNull();
  });
});

describe("Nairobi times", () => {
  it("shows UTC times in Africa/Nairobi (UTC+3)", () => {
    expect(rangeText("2026-11-23T03:30:00Z", "2026-11-23T04:30:00Z")).toBe("06:30 to 07:30");
    expect(whenText("2026-11-07T15:00:00Z")).toContain("18:00");
  });
});

describe("chips", () => {
  it("covers every booking status", () => {
    for (const s of ["confirmed", "pending_payment", "waitlisted", "expired", "cancelled", "refunded"]) expect(bookingChip(s).label.length).toBeGreaterThan(3);
    expect(bookingChip("pending_payment").label).toMatch(/Held/);
    expect(["valid", "checked_in", "void"].map((s) => ticketChip(s).label)).toEqual(["Valid", "Checked in", "Void"]);
  });
  it("counts only confirmed, held and waitlisted as active", () => {
    expect(["confirmed", "pending_payment", "waitlisted"].every(isActiveBooking)).toBe(true);
    expect(["expired", "cancelled", "refunded"].some(isActiveBooking)).toBe(false);
  });
});

describe("timeLeft", () => {
  it("counts down and ends", () => {
    const now = Date.parse("2026-01-01T10:00:00Z");
    expect(timeLeft("2026-01-01T10:12:05Z", now)).toEqual({ minutes: 12, seconds: 5 });
    expect(timeLeft("2026-01-01T09:59:59Z", now)).toBeNull();
  });
});

describe("idempotency keys and ticket codes", () => {
  it("makes a new key each time", () => {
    expect(newIdempotencyKey()).not.toBe(newIdempotencyKey());
    expect(newIdempotencyKey().length).toBeGreaterThan(20);
  });
  it("accepts only 64 lowercase hex characters", () => {
    expect(isTicketCode("a".repeat(64))).toBe(true);
    expect(isTicketCode("a".repeat(63))).toBe(false);
    expect(isTicketCode("A".repeat(64))).toBe(false);
  });
});

describe("bookingProblem", () => {
  const err = (status: number, code: string, message = "msg") => new ApiError(status, code, message);
  it("explains the conflicts plainly and points at the right field", () => {
    expect(bookingProblem(err(409, "sold_out"))).toMatchObject({ field: "slot", refresh: true });
    expect(bookingProblem(err(409, "already_booked")).link?.href).toBe("/bookings");
    expect(bookingProblem(err(409, "too_many_holds")).message).toMatch(/3 unpaid/);
    expect(bookingProblem(err(422, "others_consent_required")).field).toBe("others");
    expect(bookingProblem(err(422, "consent_required")).field).toBe("consents");
    expect(bookingProblem(err(422, "party_too_large")).field).toBe("party");
  });
  it("keeps the key only where a retry is the same intent", () => {
    expect(bookingProblem(err(503, "busy")).keepKey).toBe(true);
    expect(bookingProblem(err(0, "network", "Can't reach the server.")).keepKey).toBe(true);
    expect(bookingProblem(err(429, "rate_limited")).keepKey).toBe(true);
    expect(bookingProblem(err(409, "sold_out")).keepKey).toBeUndefined();
  });
});
