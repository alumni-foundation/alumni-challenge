/**
 * Facts about the site that are set per deployment, not in code. Leave an env var unset and the
 * matching text simply doesn't appear; nothing is made up.
 */
export const site = {
  name: "Alumni Challenge",
  /** Where "contact support" points. Set NEXT_PUBLIC_CONTACT_EMAIL. */
  contactEmail: process.env.NEXT_PUBLIC_CONTACT_EMAIL ?? null,
};
