import { ApiError } from "./client";

export const TOO_MANY_ATTEMPTS = "Too many attempts, try again later.";
export const SUSPENDED = "Your account is suspended. Contact support.";
export const SESSION_EXPIRED = "Your session expired.";
const GENERIC = "Something went wrong. Please try again.";

/** The API's error code for a correct password on a suspended account. */
const ACCOUNT_SUSPENDED = "account_suspended";

/** Plain wording for anything that can go wrong in a request. */
export function friendlyError(err: unknown): string {
  if (!(err instanceof ApiError)) return GENERIC;
  if (err.status === 429) return TOO_MANY_ATTEMPTS;
  return err.message;
}

export function loginErrorMessage(err: unknown): string {
  if (err instanceof ApiError && err.status === 401 && err.code === ACCOUNT_SUSPENDED) return SUSPENDED;
  return friendlyError(err);
}
