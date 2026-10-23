import { describe, expect, it } from "vitest";
import { isPublicPath, isSignedOutOnly } from "./routes";

describe("isPublicPath", () => {
  it.each(["/", "/schools", "/schools/abc", "/partners", "/partners/abc", "/terms", "/privacy", "/community-rules", "/contact", "/login", "/register", "/forgot-password", "/reset-password", "/verify-email", "/403", "/404", "/suspended"])(
    "lets anyone open %s",
    (p) => expect(isPublicPath(p)).toBe(true),
  );

  it.each(["/home", "/directory", "/alumni/abc", "/connections", "/profile", "/settings", "/onboarding", "/admin", "/admin/reports", "/school/abc", "/partner/abc", "/start"])(
    "asks for a sign-in before %s",
    (p) => expect(isPublicPath(p)).toBe(false),
  );

  it("does not treat the staff /school and /partner areas as the public /schools and /partners", () => {
    expect(isPublicPath("/school/abc")).toBe(false);
    expect(isPublicPath("/schoolsfoo")).toBe(false);
  });
});

describe("isSignedOutOnly", () => {
  it("covers the pages a signed-in person should be moved on from", () => {
    expect(["/login", "/register", "/forgot-password"].every(isSignedOutOnly)).toBe(true);
    expect(isSignedOutOnly("/verify-email")).toBe(false);
    expect(isSignedOutOnly("/reset-password")).toBe(false);
  });
});
