// Liveness for the platform's health check. It does not call the API on purpose: the web
// container should not be restarted just because the API is briefly away.
export const dynamic = "force-dynamic";

export function GET() {
  return Response.json({ status: "ok" }, { headers: { "cache-control": "no-store" } });
}
