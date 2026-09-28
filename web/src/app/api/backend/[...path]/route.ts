import { cookies } from "next/headers";
import { NextResponse, type NextRequest } from "next/server";
import {
  ACCESS_COOKIE,
  REFRESH_COOKIE,
  apiBase,
  clearAuthCookies,
  isSameOrigin,
  jsonError,
  refreshTokens,
  setAuthCookies,
  type TokenPair,
} from "@/lib/server/auth";

// Login, register, refresh and logout have their own routes. Only these auth paths may pass through.
const ALLOWED_AUTH = /^auth\/(me|me\/roles|sessions|sessions\/[0-9a-fA-F-]{36})$/;

async function handler(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  if (path.some((s) => s === "." || s === ".." || s === "")) return jsonError(400, "bad_path", "Bad path.");
  const joined = path.join("/");
  if (joined.startsWith("auth/") && !ALLOWED_AUTH.test(joined)) {
    return jsonError(404, "not_found", "Not found.");
  }
  const unsafe = !["GET", "HEAD"].includes(req.method);
  if (unsafe && !isSameOrigin(req)) return jsonError(403, "bad_origin", "Cross-site request blocked.");

  const jar = await cookies();
  const refresh = jar.get(REFRESH_COOKIE)?.value;
  let access = jar.get(ACCESS_COOKIE)?.value;
  if (!refresh) return jsonError(401, "unauthorized", "Not signed in.");

  const expired = () => {
    const res = jsonError(401, "unauthorized", "Your session has expired.");
    clearAuthCookies(res);
    return res;
  };
  const unavailable = () => jsonError(503, "unavailable", "The service is unavailable. Try again.");

  let fresh: TokenPair | null = null;
  if (!access) {
    const r = await refreshTokens(refresh);
    if (!r.ok) return r.reason === "invalid" ? expired() : unavailable();
    fresh = r.tokens;
    access = fresh.access_token;
  }

  const body = unsafe ? await req.text() : undefined;
  const url = `${apiBase()}/${joined}${req.nextUrl.search}`;
  const call = (token: string) =>
    fetch(url, {
      method: req.method,
      headers: { authorization: `Bearer ${token}`, ...(body ? { "content-type": "application/json" } : {}) },
      body: body || undefined,
      cache: "no-store",
    }).catch(() => null);

  let upstream = await call(access);
  if (upstream && upstream.status === 401 && !fresh) {
    const r = await refreshTokens(refresh);
    if (!r.ok) return r.reason === "invalid" ? expired() : unavailable();
    fresh = r.tokens;
    upstream = await call(fresh.access_token);
  }
  if (!upstream) return unavailable();

  const text = await upstream.text();
  const res = new NextResponse(upstream.status === 204 ? null : text, {
    status: upstream.status,
    headers: { "content-type": upstream.headers.get("content-type") ?? "application/json" },
  });
  if (fresh) setAuthCookies(res, fresh);
  return res;
}

export { handler as GET, handler as POST, handler as PUT, handler as PATCH, handler as DELETE };
