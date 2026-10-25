"use client";

import { useState } from "react";
import { Pager } from "@/components/staff/page";
import { Row, RowList } from "@/components/staff/rows";
import { EmptyState, ErrorState, Field, Select, Skeleton } from "@/components/ui";
import { ApiError } from "@/lib/api/client";
import { AUDIT_PAGE_SIZE, useAuditLog, useMemberIndex, useOrgs } from "@/lib/api/hooks";
import type { AuditLogEntry, Role } from "@/lib/api/types";
import { auditWords } from "@/lib/admin-overview";
import { roleLabel } from "@/lib/roles";
import { formatDate } from "@/lib/utils";

const ACTIONS: Record<string, string> = {
  "organization.create": "Created an organization",
  "organization.update": "Edited an organization",
  "organization.email_domain.add": "Added a school email domain",
  "membership.assign": "Gave someone a role",
  "membership.revoke": "Took a role away",
  "alumni_profile.verify": "Verified an alumni profile",
  "alumni_profile.unverify": "Removed an alumni verification",
  "user.password_reset": "Reset a password",
};

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
const str = (v: unknown) => (typeof v === "string" ? v : v == null ? "" : String(v));

/**
 * The activity log, newest first. The API decides what each person may see: platform admins see
 * everything, school and partner admins only entries for organizations they run.
 */
export function ActivityPanel() {
  const [page, setPage] = useState(0);
  const [kind, setKind] = useState("all");
  const log = useAuditLog(page);
  const loaded = log.data ?? [];
  // The API has no filters, so this narrows the entries on the page you are looking at.
  const entries = loaded.filter((e) => kind === "all" || e.action === kind);
  const kinds = [...new Set(loaded.map((e) => e.action))].sort();
  const members = useMemberIndex(loaded.length > 0);
  const schools = useOrgs("school");
  const partners = useOrgs("partner");

  const orgName = (id: string) => [...(schools.data ?? []), ...(partners.data ?? [])].find((o) => o.id === id)?.name;
  const personName = (id: string) => members.byUser.get(id)?.full_name ?? "a staff member";

  function detail(e: AuditLogEntry): string {
    const c = e.context;
    const org = typeof c.organization_id === "string" ? orgName(c.organization_id) : undefined;
    switch (e.action) {
      case "organization.create":
        return [str(c.name), str(c.type)].filter(Boolean).join(", ");
      case "organization.email_domain.add":
        return [str(c.domain), org && `for ${org}`].filter(Boolean).join(" ");
      case "membership.assign":
        return [
          c.role ? roleLabel(c.role as Role) : "",
          typeof c.target_user_id === "string" ? `to ${personName(c.target_user_id)}` : "",
          org && `at ${org}`,
        ].filter(Boolean).join(" ");
      default:
        return str(c.reason);
    }
  }

  const denied = log.error instanceof ApiError && log.error.status === 403;
  if (denied) return <EmptyState title="You can’t view the activity log" body="It’s open to platform administrators and school or partner admins." />;
  if (log.isError) return <ErrorState message={log.error.message} onRetry={() => void log.refetch()} />;
  if (log.isLoading) return <Skeleton className="h-48 rounded-card" />;

  return (
    <div className="space-y-4">
      {kinds.length > 1 && (
        <div className="w-full sm:w-72">
          <Field label="Show" htmlFor="audit-kind">
            <Select id="audit-kind" value={kind} onChange={(e) => setKind(e.target.value)}>
              <option value="all">Everything on this page</option>
              {kinds.map((k) => <option key={k} value={k}>{cap(ACTIONS[k] ?? auditWords(k, "")).trim()}</option>)}
            </Select>
          </Field>
        </div>
      )}
      {entries.length === 0 ? (
        <EmptyState title={loaded.length > 0 ? "Nothing of that kind on this page" : page === 0 ? "Nothing recorded yet" : "No more entries"} body={page === 0 ? "Admin actions will show up here." : undefined} />
      ) : (
        <RowList label="Activity">
          {entries.map((e) => (
            <Row key={e.id} stack className="items-start sm:items-center">
              <div className="min-w-0 flex-1">
                <p className="font-medium">{cap(ACTIONS[e.action] ?? auditWords(e.action, e.target_type))}</p>
                <p className="mt-0.5 break-words text-small text-muted">
                  By {e.actor_user_id ? personName(e.actor_user_id) : "the system"}
                  {detail(e) && <> · {detail(e)}</>}
                </p>
              </div>
              <time dateTime={e.created_at} className="shrink-0 text-small text-muted">{formatDate(e.created_at)}</time>
            </Row>
          ))}
        </RowList>
      )}
      <Pager page={page} hasNext={loaded.length === AUDIT_PAGE_SIZE} onPage={(p) => { setPage(p); setKind("all"); }} busy={log.isFetching} prevLabel="Newer" nextLabel="Older" />
    </div>
  );
}
