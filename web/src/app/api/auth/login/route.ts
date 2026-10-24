import { NextResponse, type NextRequest } from "next/server";
import { visitorHeaders } from "@/lib/server/visitor";
import { apiBase, isSameOrigin, jsonError, setAuthCookies, type TokenPair } from "@/lib/server/auth";

export async function POST(req: NextRequest) {
  if (!isSameOrigin(req)) return jsonError(403, "bad_origin", "Cross-site request blocked.");
  let upstream: Response;
  try {
    upstream = await fetch(`${apiBase()}/auth/login`, {
      method: "POST",
      headers: {
        ...visitorHeaders(req.headers),
        "content-type": "application/json",
        "user-agent": req.headers.get("user-agent") ?? "",
      },
      body: await req.text(),
      cache: "no-store",
    });
  } catch {
    return jsonError(503, "unavailable", "The service is unavailable. Try again.");
  }
  if (!upstream.ok) {
    return new NextResponse(await upstream.text(), {
      status: upstream.status,
      headers: { "content-type": "application/json" },
    });
  }
  const res = NextResponse.json({ ok: true });
  setAuthCookies(req, res, (await upstream.json()) as TokenPair);
  return res;
}
