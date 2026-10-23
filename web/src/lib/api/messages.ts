import { ApiError } from "./client";

export const TOO_MANY_ATTEMPTS = "Too many attempts, try again later.";
export const SUSPENDED = "Your account is suspended. Contact support.";
export const SESSION_EXPIRED = "Your session expired.";
const GENERIC = "Something went wrong. Please try again.";

/**
 * The API answers 401 both for a wrong password and for a suspended account, and tells them
 * apart only by this sentence. If the API ever gives suspension its own error code, match on
 * that instead.
 */
const INACTIVE_ACCOUNT = "This account is not active.";

/** Plain wording for anything that can go wrong in a request. */
export function friendlyError(err: unknown): string {
  if (!(err instanceof ApiError)) return GENERIC;
  if (err.status === 429) return TOO_MANY_ATTEMPTS;
  return err.message;
}

export function loginErrorMessage(err: unknown): string {
  if (err instanceof ApiError && err.status === 401 && err.message === INACTIVE_ACCOUNT) return SUSPENDED;
  return friendlyError(err);
}
