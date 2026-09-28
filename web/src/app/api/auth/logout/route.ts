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
} from "@/lib/server/auth";

export async function POST(req: NextRequest) {
  if (!isSameOrigin(req)) return jsonError(403, "bad_origin", "Cross-site request blocked.");
  const jar = await cookies();
  let refresh = jar.get(REFRESH_COOKIE)?.value;
  let access = jar.get(ACCESS_COOKIE)?.value;
  try {
    if (refresh && !access) {
      const r = await refreshTokens(refresh);
      if (r.ok) {
        access = r.tokens.access_token;
        refresh = r.tokens.refresh_token;
      }
    }
    if (refresh && access) {
      await fetch(`${apiBase()}/auth/logout`, {
        method: "POST",
        headers: { authorization: `Bearer ${access}`, "content-type": "application/json" },
        body: JSON.stringify({ refresh_token: refresh }),
        cache: "no-store",
      });
    }
  } catch {
    // The browser is signed out either way; the backend session expires on its own.
  }
  const res = new NextResponse(null, { status: 204 });
  clearAuthCookies(res);
  return res;
}
