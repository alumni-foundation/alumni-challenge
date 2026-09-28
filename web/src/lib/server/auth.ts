import { NextResponse, type NextRequest } from "next/server";

export const ACCESS_COOKIE = "ac_access";
export const REFRESH_COOKIE = "ac_refresh";

export type TokenPair = { access_token: string; refresh_token: string; token_type: string };

const secure = process.env.NODE_ENV === "production";
const REFRESH_MAX_AGE = 60 * 60 * 24 * 30; // matches backend refresh_token_expire_days

export function apiBase(): string {
  const url = process.env.API_URL ?? (secure ? undefined : "http://localhost:8000");
  if (!url) throw new Error("API_URL is not set");
  return `${url.replace(/\/$/, "")}/api/v1`;
}

function jwtExp(token: string): number | undefined {
  try {
    const payload = JSON.parse(Buffer.from(token.split(".")[1], "base64url").toString());
    return typeof payload.exp === "number" ? payload.exp : undefined;
  } catch {
    return undefined;
  }
}

export function setAuthCookies(res: NextResponse, tokens: TokenPair): void {
  const exp = jwtExp(tokens.access_token);
  // Access cookie expires 30s before the token does, so we refresh instead of sending a dead token.
  const maxAge = exp ? Math.max(exp - Math.floor(Date.now() / 1000) - 30, 1) : 600;
  const base = { httpOnly: true, secure, sameSite: "lax" as const, path: "/" };
  res.cookies.set(ACCESS_COOKIE, tokens.access_token, { ...base, maxAge });
  res.cookies.set(REFRESH_COOKIE, tokens.refresh_token, { ...base, maxAge: REFRESH_MAX_AGE });
}

export function clearAuthCookies(res: NextResponse): void {
  for (const name of [ACCESS_COOKIE, REFRESH_COOKIE]) {
    res.cookies.set(name, "", { httpOnly: true, secure, sameSite: "lax", path: "/", maxAge: 0 });
  }
}

/** State-changing requests must come from our own origin (CSRF defence on top of SameSite=Lax). */
export function isSameOrigin(req: NextRequest): boolean {
  const origin = req.headers.get("origin");
  if (!origin) return false;
  const host = req.headers.get("x-forwarded-host") ?? req.headers.get("host");
  try {
    return new URL(origin).host === host;
  } catch {
    return false;
  }
}

export type RefreshResult =
  | { ok: true; tokens: TokenPair }
  | { ok: false; reason: "invalid" | "unavailable" };

/**
 * Refresh tokens rotate, and the backend treats reuse of an old one as theft and revokes
 * every session. Several parallel requests can all find the access token expired, so all of
 * them must share ONE refresh call. Results are kept for 30s so a request that was already
 * in flight with the old cookie gets the same new pair instead of replaying the old token.
 * In-process only: with more than one web instance this needs a shared lock (Redis).
 */
const TTL_MS = 30_000;
const inflight = new Map<string, { promise: Promise<RefreshResult>; at: number }>();

export function refreshTokens(refreshToken: string): Promise<RefreshResult> {
  const now = Date.now();
  for (const [key, entry] of inflight) if (now - entry.at > TTL_MS) inflight.delete(key);
  const existing = inflight.get(refreshToken);
  if (existing) return existing.promise;

  const promise = (async (): Promise<RefreshResult> => {
    try {
      const res = await fetch(`${apiBase()}/auth/refresh`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
        cache: "no-store",
      });
      if (res.ok) return { ok: true, tokens: (await res.json()) as TokenPair };
      return { ok: false, reason: res.status >= 500 ? "unavailable" : "invalid" };
    } catch {
      return { ok: false, reason: "unavailable" };
    }
  })();
  inflight.set(refreshToken, { promise, at: now });
  void promise.then((r) => {
    if (!r.ok && r.reason === "unavailable") inflight.delete(refreshToken);
  });
  return promise;
}

export const jsonError = (status: number, code: string, message: string) =>
  NextResponse.json({ error: { code, message } }, { status });
