import { NextResponse, type NextRequest } from "next/server";
import { apiBase, isSameOrigin, jsonError } from "@/lib/server/auth";
import { visitorHeaders } from "@/lib/server/visitor";

export async function POST(req: NextRequest) {
  if (!isSameOrigin(req)) return jsonError(403, "bad_origin", "Cross-site request blocked.");
  try {
    const upstream = await fetch(`${apiBase()}/auth/register`, {
      method: "POST",
      headers: { "content-type": "application/json", ...visitorHeaders(req.headers) },
      body: await req.text(),
      cache: "no-store",
    });
    return new NextResponse(await upstream.text(), {
      status: upstream.status,
      headers: { "content-type": "application/json" },
    });
  } catch {
    return jsonError(503, "unavailable", "The service is unavailable. Try again.");
  }
}
