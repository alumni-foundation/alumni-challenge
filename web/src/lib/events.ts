/** Small, pure helpers for the events screens: dates in Nairobi time, prices, seat text, booking and ticket status. */

const TZ = "Africa/Nairobi";
const fmt = (iso: string, opts: Intl.DateTimeFormatOptions) => new Intl.DateTimeFormat("en-KE", { timeZone: TZ, ...opts }).format(new Date(iso));

/** "Sat 7 Nov, 18:00" */
export const whenText = (iso: string) => fmt(iso, { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", hour12: false });
/** "Saturday 7 November 2026" */
export const dayText = (iso: string) => fmt(iso, { weekday: "long", day: "numeric", month: "long", year: "numeric" });
/** "18:00" */
export const timeText = (iso: string) => fmt(iso, { hour: "2-digit", minute: "2-digit", hour12: false });
export const monthShort = (iso: string) => fmt(iso, { month: "short" });
export const dayNumber = (iso: string) => fmt(iso, { day: "numeric" });
/** "18:00 to 21:00" (the end is left off when it is the same minute). */
export const rangeText = (start: string, end: string) => (start === end ? timeText(start) : `${timeText(start)} to ${timeText(end)}`);

/** Whole minor units (1/100 KES) to words: 0 is "Free", 350000 is "KES 3,500". */
export function priceText(minor: number, currency = "KES"): string {
  if (minor <= 0) return "Free";
  const major = minor / 100;
  const text = new Intl.NumberFormat("en-KE", { minimumFractionDigits: Number.isInteger(major) ? 0 : 2, maximumFractionDigits: 2 }).format(major);
  return `${currency} ${text}`;
}

/** "12 seats left", "Full", or null when there is no cap. */
export function seatsText(spotsLeft: number | null): string | null {
  if (spotsLeft === null) return null;
  if (spotsLeft <= 0) return "Full";
  return `${spotsLeft} ${spotsLeft === 1 ? "seat" : "seats"} left`;
}

export type Chip = { label: string; tone: "ok" | "warn" | "brand" | "neutral" | "gold" | "blue" };

/** How each booking status looks. "Pending payment" is the held state: the seats are kept until the hold runs out. */
export function bookingChip(status: string): Chip {
  switch (status) {
    case "confirmed": return { label: "Confirmed", tone: "ok" };
    case "pending_payment": return { label: "Held, pending payment", tone: "warn" };
    case "waitlisted": return { label: "Waitlisted", tone: "blue" };
    case "expired": return { label: "Expired", tone: "neutral" };
    case "cancelled": return { label: "Cancelled", tone: "neutral" };
    case "refunded": return { label: "Refunded", tone: "neutral" };
    default: return { label: status.replace(/_/g, " "), tone: "neutral" };
  }
}

export function ticketChip(status: string): Chip {
  switch (status) {
    case "valid": return { label: "Valid", tone: "ok" };
    case "checked_in": return { label: "Checked in", tone: "blue" };
    case "void": return { label: "Void", tone: "neutral" };
    default: return { label: status.replace(/_/g, " "), tone: "neutral" };
  }
}

/** The bookings that still hold or keep seats. */
export const isActiveBooking = (status: string) => status === "confirmed" || status === "pending_payment" || status === "waitlisted";

/** Minutes, seconds left until `iso`, or null once it has passed. */
export function timeLeft(iso: string, now = Date.now()): { minutes: number; seconds: number } | null {
  const ms = new Date(iso).getTime() - now;
  if (ms <= 0) return null;
  const total = Math.ceil(ms / 1000);
  return { minutes: Math.floor(total / 60), seconds: total % 60 };
}

/** One new key per booking intent. The same key is sent on every retry of that intent, so it can never book twice. */
export const newIdempotencyKey = () => globalThis.crypto.randomUUID();

/** A ticket code is 64 hex characters. */
export const isTicketCode = (value: string) => /^[0-9a-f]{64}$/.test(value);
