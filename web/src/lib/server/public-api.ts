import type { OrgType, Organization } from "@/lib/api/types";
import { apiBase } from "./auth";

/** Organizations are public. These run on the server, so visitors download HTML, not a fetch waterfall. */
export async function fetchOrgs(type: OrgType): Promise<Organization[] | null> {
  try {
    const res = await fetch(`${apiBase()}/organizations?type=${type}&limit=100`, { cache: "no-store" });
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
    const res = await fetch(`${apiBase()}/organizations/${id}`, { cache: "no-store" });
    if (res.status === 404 || res.status === 422) return { org: null, reason: "missing" };
    if (!res.ok) return { org: null, reason: "unavailable" };
    return { org: (await res.json()) as Organization };
  } catch {
    return { org: null, reason: "unavailable" };
  }
}
