import { describe, expect, it } from "vitest";
import { ApiError } from "./client";
import { friendlyError, loginErrorMessage, SUSPENDED, TOO_MANY_ATTEMPTS } from "./messages";

describe("loginErrorMessage", () => {
  it("explains a suspended account from the error code, whatever the message says", () => {
    expect(loginErrorMessage(new ApiError(401, "account_suspended", "Any wording at all."))).toBe(SUSPENDED);
  });

  it("does not guess from the message text", () => {
    expect(loginErrorMessage(new ApiError(401, "unauthorized", "This account is not active."))).toBe(
      "This account is not active.",
    );
  });

  it("keeps the server's wording for a wrong password", () => {
    expect(loginErrorMessage(new ApiError(401, "unauthorized", "Invalid email or password."))).toBe(
      "Invalid email or password.",
    );
  });

  it("says too many attempts on a 429, whatever the server wrote", () => {
    expect(loginErrorMessage(new ApiError(429, "rate_limited", "Slow down."))).toBe(TOO_MANY_ATTEMPTS);
  });
});

describe("friendlyError", () => {
  it("passes the server's message through", () => {
    expect(friendlyError(new ApiError(409, "conflict", "You already reported this."))).toBe("You already reported this.");
  });

  it("falls back to a calm generic message for unknown errors", () => {
    expect(friendlyError(new Error("boom"))).toBe("Something went wrong. Please try again.");
  });
});
