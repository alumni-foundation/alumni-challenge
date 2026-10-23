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
const PUBLIC_PREFIXES = ["/schools", "/partners"];

/** Pages that make no sense once you are signed in; they send you on to your landing page. */
const SIGNED_OUT_ONLY = new Set(["/login", "/register", "/forgot-password"]);

export const isPublicPath = (pathname: string) =>
  PUBLIC_EXACT.has(pathname) || PUBLIC_PREFIXES.some((p) => pathname === p || pathname.startsWith(`${p}/`));

export const isSignedOutOnly = (pathname: string) => SIGNED_OUT_ONLY.has(pathname);
