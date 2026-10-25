/** Pages anyone can open, signed in or not. Everything else needs a session. */
const PUBLIC_EXACT = new Set([
  "/",
  "/login",
  "/register",
  "/forgot-password",
  "/reset-password",
  "/verify-email",
  "/terms",
  "/privacy",
  "/community-rules",
  "/contact",
  "/403",
  "/404",
  "/suspended",
]);
const PUBLIC_PREFIXES = ["/schools", "/partners", "/events"];

/** A ticket page is the link in the email and behind the QR, so it opens without a sign-in. (The list at /tickets does not.) */
const TICKET_PAGE = /^\/tickets\/[0-9a-f]{64}$/;

/**
 * Pages that make no sense once you are signed in; they send you on to your landing page.
 * Forgot-password is not here on purpose: Settings offers "Reset by email" to signed-in people.
 */
const SIGNED_OUT_ONLY = new Set(["/login", "/register"]);

/** The design-check page exists only in `next dev` (see next.config.ts), so opening it needs no sign-in there. */
const DEV_PAGES = process.env.NODE_ENV === "production" ? [] : ["/design-check"];

export const isPublicPath = (pathname: string) =>
  DEV_PAGES.includes(pathname) ||
  TICKET_PAGE.test(pathname) ||
  PUBLIC_EXACT.has(pathname) || PUBLIC_PREFIXES.some((p) => pathname === p || pathname.startsWith(`${p}/`));

export const isSignedOutOnly = (pathname: string) => SIGNED_OUT_ONLY.has(pathname);

/** The staff areas. Someone working here does not need a member (alumni) profile. */
export const isStaffArea = (pathname: string) =>
  ["/admin", "/school", "/partner", "/organizer"].some((p) => pathname === p || pathname.startsWith(`${p}/`));

/**
 * Pages that work without a member (alumni) profile: the staff areas, and Settings, which is about
 * the account (password, devices, data) and not the member profile.
 */
export const worksWithoutProfile = (pathname: string) =>
  isStaffArea(pathname) || pathname === "/settings" || pathname === "/messages" || isEventsArea(pathname);

/**
 * Events, bookings and tickets are about the account, not the alumni profile: staff, and people who have not
 * finished onboarding, can still open an emailed ticket link or look at events. (Booking only needs a name.)
 */
export const isEventsArea = (pathname: string) =>
  ["/events", "/bookings", "/tickets"].some((p) => pathname === p || pathname.startsWith(`${p}/`));
