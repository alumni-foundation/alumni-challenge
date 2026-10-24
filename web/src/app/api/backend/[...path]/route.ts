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
import { visitorHeaders } from "@/lib/server/visitor";

// Login, register, refresh and logout have their own routes. Only these auth paths may pass through.
const ALLOWED_AUTH = /^auth\/(me|me\/roles|email\/verify\/request|sessions|sessions\/[0-9a-fA-F-]{36})$/;

async function handler(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  if (path.some((s) => s === "." || s === ".." || s === "")) return jsonError(400, "bad_path", "Bad path.");
  const joined = path.join("/");
  if (joined.startsWith("auth/") && !ALLOWED_AUTH.test(joined)) {
    return jsonError(404, "not_found", "Not found.");
  }
  const unsafe = !["GET", "HEAD"].includes(req.method);
  if (unsafe && !isSameOrigin(req)) return jsonError(403, "bad_origin", "Cross-site request blocked.");

  const visitor = visitorHeaders(req.headers);
  const jar = await cookies();
  const refresh = jar.get(REFRESH_COOKIE)?.value;
  let access = jar.get(ACCESS_COOKIE)?.value;
  if (!refresh) return jsonError(401, "unauthorized", "Not signed in.");

  const expired = () => {
    const res = jsonError(401, "unauthorized", "Your session has expired.");
    clearAuthCookies(req, res);
    return res;
  };
  const unavailable = () => jsonError(503, "unavailable", "The service is unavailable. Try again.");

  let fresh: TokenPair | null = null;
  if (!access) {
    const r = await refreshTokens(refresh, visitor);
    if (!r.ok) return r.reason === "invalid" ? expired() : unavailable();
    fresh = r.tokens;
    access = fresh.access_token;
  }

  // Uploads are the one place a body is not JSON. Pass the file through with its multipart boundary.
  const contentType = req.headers.get("content-type") ?? "";
  const multipart = joined === "files" && contentType.startsWith("multipart/form-data");
  const body = !unsafe ? undefined : multipart ? await req.arrayBuffer() : await req.text();
  const url = `${apiBase()}/${joined}${req.nextUrl.search}`;
  // A booking is sent once however many times it is retried: the API needs the same key on every retry.
  const idempotencyKey = req.headers.get("idempotency-key")?.slice(0, 255);
  const call = (token: string) =>
    fetch(url, {
      method: req.method,
      headers: {
        ...visitor,
        authorization: `Bearer ${token}`,
        ...(idempotencyKey ? { "idempotency-key": idempotencyKey } : {}),
        ...(body ? { "content-type": multipart ? contentType : "application/json" } : {}),
      },
      body: body || undefined,
      cache: "no-store",
    }).catch(() => null);

  let upstream = await call(access);
  if (upstream && upstream.status === 401 && !fresh) {
    const r = await refreshTokens(refresh, visitor);
    if (!r.ok) return r.reason === "invalid" ? expired() : unavailable();
    fresh = r.tokens;
    upstream = await call(fresh.access_token);
  }
  if (!upstream) return unavailable();

  const text = await upstream.text();
  const headers: Record<string, string> = {
    "content-type": upstream.headers.get("content-type") ?? "application/json",
  };
  // The directory reports how many people match in this header.
  const total = upstream.headers.get("x-total-count");
  if (total) headers["x-total-count"] = total;
  const res = new NextResponse(upstream.status === 204 ? null : text, { status: upstream.status, headers });
  if (fresh) setAuthCookies(req, res, fresh);
  return res;
}

export { handler as GET, handler as POST, handler as PUT, handler as PATCH, handler as DELETE };
