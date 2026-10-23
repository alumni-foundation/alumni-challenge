"use client";

import { useState } from "react";
import { Alert, Button, EmptyState, PageHeader, Spinner } from "@/components/ui";
import { ApiError } from "@/lib/api/client";
import { AUDIT_PAGE_SIZE, useAuditLog, useMemberIndex, useOrgs, useRoles } from "@/lib/api/hooks";
import type { AuditLogEntry, Role } from "@/lib/api/types";
import { canViewAuditLog, roleLabel } from "@/lib/roles";
import { formatDate } from "@/lib/utils";

const ACTIONS: Record<string, string> = {
  "organization.create": "Created an organization",
  "organization.email_domain.add": "Added a school email domain",
  "membership.assign": "Gave someone a role",
  "alumni_profile.verify": "Verified an alumni profile",
  "alumni_profile.unverify": "Removed an alumni verification",
  "user.password_reset": "Reset a password",
};

const humanize = (s: string) => {
  const t = s.replace(/[._]/g, " ").trim();
  return t.charAt(0).toUpperCase() + t.slice(1);
};
const str = (v: unknown) => (typeof v === "string" ? v : v == null ? "" : String(v));

export default function AuditLogPage() {
  const roles = useRoles();
  const [page, setPage] = useState(0);
  const log = useAuditLog(page);
  const entries = log.data ?? [];
  const members = useMemberIndex(entries.length > 0);
  const schools = useOrgs("school");
  const partners = useOrgs("partner");

  if (roles.isLoading) return <Spinner label="Checking access" />;
  if (!canViewAuditLog(roles.data)) {
    return <EmptyState title="You can’t view the activity log" body="It’s open to platform administrators and school or partner admins." />;
  }

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
        return e.target_id ? `${humanize(e.target_type)} ${e.target_id.slice(0, 8)}` : humanize(e.target_type);
    }
  }

  const denied = log.error instanceof ApiError && log.error.status === 403;

  return (
    <div>
      <PageHeader
        title="Activity log"
        subtitle={roles.data && canViewAuditLog(roles.data) ? "Newest first." : undefined}
      />
      {log.isLoading && <Spinner label="Loading the log" />}
      {denied && <Alert>You don’t have permission to view the activity log.</Alert>}
      {log.isError && !denied && <Alert>{log.error.message}</Alert>}
      {log.data && entries.length === 0 && (
        <EmptyState title={page === 0 ? "Nothing recorded yet" : "No more entries"} body={page === 0 ? "Admin actions will show up here." : undefined} />
      )}
      {entries.length > 0 && (
        <ul className="divide-y divide-line overflow-hidden rounded-2xl border border-line bg-surface">
          {entries.map((e) => (
            <li key={e.id} className="px-5 py-3.5">
              <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
                <p className="font-medium">{ACTIONS[e.action] ?? humanize(e.action)}</p>
                <time dateTime={e.created_at} className="text-sm text-muted">{formatDate(e.created_at)}</time>
              </div>
              <p className="mt-0.5 text-sm text-muted">
                By {e.actor_user_id ? personName(e.actor_user_id) : "the system"}
                {detail(e) && <> · {detail(e)}</>}
              </p>
              <details className="mt-1 text-sm">
                <summary className="cursor-pointer text-muted hover:text-ink">Full record</summary>
                <pre className="mt-2 overflow-x-auto rounded-lg bg-canvas p-3 text-xs">{JSON.stringify(e, null, 2)}</pre>
              </details>
            </li>
          ))}
        </ul>
      )}
      {(page > 0 || entries.length === AUDIT_PAGE_SIZE) && (
        <div className="mt-4 flex items-center justify-between">
          <Button variant="secondary" disabled={page === 0 || log.isFetching} onClick={() => setPage((p) => p - 1)}>Newer</Button>
          <span className="text-sm text-muted">Page {page + 1}</span>
          <Button variant="secondary" disabled={entries.length < AUDIT_PAGE_SIZE || log.isFetching} onClick={() => setPage((p) => p + 1)}>Older</Button>
        </div>
      )}
    </div>
  );
}
