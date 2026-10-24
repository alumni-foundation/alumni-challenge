import { cookies, headers } from "next/headers";
import type { EventDetail, EventSummary, OrgType, Organization, Ticket } from "@/lib/api/types";
import { ACCESS_COOKIE, apiBase } from "./auth";
import { visitorHeaders } from "./visitor";

/** These pages render for a visitor, so the API should count that visitor, not this server. */
async function visitor(): Promise<Record<string, string>> {
  return visitorHeaders(await headers());
}

/** Organizations are public. These run on the server, so visitors download HTML, not a fetch waterfall. */
export async function fetchOrgs(type: OrgType): Promise<Organization[] | null> {
  try {
    const res = await fetch(`${apiBase()}/organizations?type=${type}&limit=100`, { cache: "no-store", headers: await visitor() });
    return res.ok ? ((await res.json()) as Organization[]) : null;
  } catch {
    return null;
  }
}

export type OrgLookup = { org: Organization } | { org: null; reason: "missing" | "unavailable" };

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function fetchOrg(id: string): Promise<OrgLookup> {
  if (!UUID.test(id)) return { org: null, reason: "missing" };
  try {
    const res = await fetch(`${apiBase()}/organizations/${id}`, { cache: "no-store", headers: await visitor() });
    if (res.status === 404 || res.status === 422) return { org: null, reason: "missing" };
    if (!res.ok) return { org: null, reason: "unavailable" };
    return { org: (await res.json()) as Organization };
  } catch {
    return { org: null, reason: "unavailable" };
  }
}

/**
 * Events and tickets are drawn on the server so a visitor with no account sees them too. If the person is
 * signed in their token is added, which is what lets members-only events show up. A stale token is not an
 * error: the call is simply repeated as a visitor.
 */
async function getWithOptionalSession(path: string): Promise<Response> {
  const token = (await cookies()).get(ACCESS_COOKIE)?.value;
  const base = { cache: "no-store" as const, headers: await visitor() };
  if (token) {
    const res = await fetch(`${apiBase()}/${path}`, { ...base, headers: { ...base.headers, authorization: `Bearer ${token}` } });
    if (res.status !== 401) return res;
  }
  return fetch(`${apiBase()}/${path}`, base);
}

/** Up to 100 upcoming (or, with `past`, finished) events. The API has no price filter, so free/paid is done by the page. */
export async function fetchEvents(opts: { past: boolean; q?: string }): Promise<EventSummary[] | null> {
  const qs = new URLSearchParams({ limit: "100" });
  if (opts.past) qs.set("past", "true");
  if (opts.q?.trim()) qs.set("q", opts.q.trim().slice(0, 100));
  try {
    const res = await getWithOptionalSession(`events?${qs}`);
    return res.ok ? ((await res.json()) as EventSummary[]) : null;
  } catch {
    return null;
  }
}

export type EventLookup = { event: EventDetail } | { event: null; reason: "missing" | "unavailable" };

export async function fetchEvent(id: string): Promise<EventLookup> {
  if (!UUID.test(id)) return { event: null, reason: "missing" };
  try {
    const res = await getWithOptionalSession(`events/${id}`);
    if (res.status === 404 || res.status === 422) return { event: null, reason: "missing" };
    if (!res.ok) return { event: null, reason: "unavailable" };
    return { event: (await res.json()) as EventDetail };
  } catch {
    return { event: null, reason: "unavailable" };
  }
}

export type TicketLookup = { ticket: Ticket } | { ticket: null; reason: "missing" | "unavailable" };

/** The public ticket page's data. The code is only ever sent to the API from here; it is not logged. */
export async function fetchTicket(code: string): Promise<TicketLookup> {
  if (!/^[0-9a-f]{64}$/.test(code)) return { ticket: null, reason: "missing" };
  try {
    const res = await fetch(`${apiBase()}/tickets/${code}`, { cache: "no-store", headers: await visitor() });
    if (res.status === 404) return { ticket: null, reason: "missing" };
    if (!res.ok) return { ticket: null, reason: "unavailable" };
    return { ticket: (await res.json()) as Ticket };
  } catch {
    return { ticket: null, reason: "unavailable" };
  }
}
