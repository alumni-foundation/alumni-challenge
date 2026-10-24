import { isIP } from "node:net";

/** The header the API reads the visitor's address from (its TRUSTED_CLIENT_IP_HEADER setting). */
export const VISITOR_IP_HEADER = "x-visitor-ip";

/**
 * The real visitor's address, for the API's per-IP rate limits. Every call the API receives comes
 * from this server, so without it all visitors would share one bucket.
 *
 * In production only Cloudflare's CF-Connecting-IP is believed, and only because the web origin
 * accepts traffic from Cloudflare alone (see docs/DEPLOYMENT.md). With no such header there is no
 * address to give, and the API falls back to the connection address. In development there is no
 * Cloudflare, so the address Next.js records for the connection (x-forwarded-for) is used.
 * An X-Visitor-IP sent by a browser is never read.
 */
export function visitorIp(incoming: Headers): string | null {
  const production = process.env.NODE_ENV === "production";
  const raw = production ? incoming.get("cf-connecting-ip") : incoming.get("x-forwarded-for")?.split(",")[0];
  const ip = raw?.trim();
  return ip && isIP(ip) ? ip : null;
}

/** Headers to add to a server-side call to the API. Always built fresh, never copied from the browser. */
export function visitorHeaders(incoming: Headers): Record<string, string> {
  const ip = visitorIp(incoming);
  return ip ? { [VISITOR_IP_HEADER]: ip } : {};
}
