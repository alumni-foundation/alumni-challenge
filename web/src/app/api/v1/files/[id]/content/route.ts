import type { NextRequest } from "next/server";
import { apiBase } from "@/lib/server/auth";

// The API gives out picture links relative to itself (/api/v1/files/<id>/content). A browser asks
// the web origin for them, so this forwards that one path. No login cookie is needed or sent:
// the API decides from the file's visibility and the `token` in the link.
const FILE_ID = /^[0-9a-fA-F-]{36}$/;
const PASS_HEADERS = ["content-type", "content-length", "content-disposition", "cache-control", "etag", "last-modified"];

function notFound() {
  return new Response("Not found", { status: 404, headers: { "cache-control": "no-store" } });
}

export async function GET(req: NextRequest, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  if (!FILE_ID.test(id)) return notFound();

  const query = new URLSearchParams();
  const token = req.nextUrl.searchParams.get("token");
  if (token) query.set("token", token);
  const qs = query.size ? `?${query}` : "";

  let upstream: Response;
  try {
    upstream = await fetch(`${apiBase()}/files/${id}/content${qs}`, {
      cache: "no-store",
      headers: req.headers.get("if-none-match") ? { "if-none-match": req.headers.get("if-none-match")! } : undefined,
    });
  } catch {
    return new Response("Unavailable", { status: 503, headers: { "cache-control": "no-store" } });
  }

  const headers = new Headers();
  for (const name of PASS_HEADERS) {
    const value = upstream.headers.get(name);
    if (value) headers.set(name, value);
  }
  headers.set("x-content-type-options", "nosniff");
  // A failure must never be cached as if it were the picture.
  if (!upstream.ok) headers.set("cache-control", "no-store");
  return new Response(upstream.body, { status: upstream.status, headers });
}
