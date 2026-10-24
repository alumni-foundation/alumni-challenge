"use client";

import { useState } from "react";
import { Button, Card, EmptyState, ErrorState, Skeleton } from "@/components/ui";
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
  const log = useAuditLog(page);
  const entries = log.data ?? [];
  const members = useMemberIndex(entries.length > 0);
  const schools = useOrgs("school");
  const partners = useOrgs("partner");

  const orgName = (id: string) => [...(schools.data ?? []), ...(partners.data ?? [])].find((o) => o.id === id)?.name;
  const personName = (id: string) => members.byUser.get(id)?.full_name ?? `User ${id.slice(0, 8)}`;

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
      {entries.length === 0 ? (
        <EmptyState title={page === 0 ? "Nothing recorded yet" : "No more entries"} body={page === 0 ? "Admin actions will show up here." : undefined} />
      ) : (
        <Card className="py-0">
          <ul className="divide-y divide-line">
            {entries.map((e) => (
              <li key={e.id} className="py-4">
                <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
                  <p className="font-medium">{cap(ACTIONS[e.action] ?? auditWords(e.action, e.target_type))}</p>
                  <time dateTime={e.created_at} className="text-small text-muted">{formatDate(e.created_at)}</time>
                </div>
                <p className="mt-0.5 break-words text-small text-muted">
                  By {e.actor_user_id ? personName(e.actor_user_id) : "the system"}
                  {detail(e) && <> · {detail(e)}</>}
                </p>
              </li>
            ))}
          </ul>
        </Card>
      )}
      {(page > 0 || entries.length === AUDIT_PAGE_SIZE) && (
        <nav aria-label="Pages" className="flex items-center justify-between gap-3">
          <Button variant="secondary" disabled={page === 0 || log.isFetching} onClick={() => setPage((p) => p - 1)}>Newer</Button>
          <span className="text-small text-muted">Page {page + 1}</span>
          <Button variant="secondary" disabled={entries.length < AUDIT_PAGE_SIZE || log.isFetching} onClick={() => setPage((p) => p + 1)}>Older</Button>
        </nav>
      )}
    </div>
  );
}
