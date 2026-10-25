import { ApiError } from "@/lib/api/client";
import { friendlyError } from "@/lib/api/messages";

/** Why a booking was refused, in plain words, and which part of the form it belongs to (if any). */
export type BookingProblem = { message: string; field?: string; keepKey?: boolean; refresh?: boolean; link?: { href: string; label: string } };

export function bookingProblem(err: unknown): BookingProblem {
  if (!(err instanceof ApiError)) return { message: "Something went wrong. Please try again.", keepKey: true };
  switch (err.code) {
    case "registration_not_open_yet": return { message: "Registration for this event hasn’t opened yet.", refresh: true };
    case "registration_closed": return { message: "Registration for this event has closed.", refresh: true };
    case "registration_ended": return { message: "This event has already finished.", refresh: true };
    case "registration_cancelled": return { message: "This event was cancelled.", refresh: true };
    case "already_booked": return { message: "You already have a booking for this event.", link: { href: "/bookings", label: "See my bookings" }, refresh: true };
    case "sold_out": return { message: "That session doesn’t have enough places left for your group. Choose another session, or fewer players.", field: "slot", refresh: true };
    case "too_many_holds": return { message: "You already have 3 unpaid bookings. Pay for one, or cancel one, before you book another.", link: { href: "/bookings", label: "See my bookings" } };
    case "party_too_large": return { message: "That is more people than this event allows in one booking.", field: "party" };
    case "others_consent_required": return { message: "Please confirm you may share the other players’ details.", field: "others" };
    case "invalid_slot": return { message: "That session isn’t available any more. Please choose another.", field: "slot", refresh: true };
    case "consent_required": return { message: "Please tick every required box.", field: "consents" };
    case "answer_required": return { message: err.message || "Please answer every required question." };
    case "invalid_answer": return { message: err.message || "One of your answers isn’t valid. Please check them." };
    case "unknown_question":
    case "unknown_consent": return { message: "This event changed while you were filling it in. Please reload the page and try again.", refresh: true };
    case "idempotency_key_reused": return { message: "Something changed since your last try. Please press the button again." };
    case "busy": return { message: "We’re busy for a moment. Please try again in a few seconds.", keepKey: true };
    default:
      if (err.status === 429) return { message: friendlyError(err), keepKey: true };
      if (err.status >= 500 || err.status === 0) return { message: err.status === 0 ? err.message : "The service is busy. Please try again in a moment.", keepKey: true };
      return { message: err.message };
  }
}
