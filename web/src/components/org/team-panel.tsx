"use client";

import { Search, UserMinus, UserPlus } from "lucide-react";
import { useState } from "react";
import {
  Alert, Avatar, Badge, Button, Card, ConfirmDialog, EmptyState, ErrorState, Field, Input, Select, Skeleton, useToast,
} from "@/components/ui";
import { api } from "@/lib/api/client";
import { friendlyError } from "@/lib/api/messages";
import { TEAM_PAGE_SIZE, useMe, useOrgMembers, useRoles, useWrite } from "@/lib/api/hooks";
import type { MemberListItem, Organization, Role, UserLookupMatch } from "@/lib/api/types";
import { assignableRoles, isPlatformAdmin, roleLabel } from "@/lib/roles";
import { formatDate } from "@/lib/utils";

const ORG_ADMIN_ROLES: Role[] = ["school_admin", "partner_admin"];

/** The email lookup: it can only ever find people who already belong to THIS organization. */
function Lookup({ org, allowed }: { org: Organization; allowed: Role[] }) {
  const toast = useToast();
  const [email, setEmail] = useState("");
  const [checked, setChecked] = useState<string | null>(null);
  const [match, setMatch] = useState<UserLookupMatch | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [role, setRole] = useState<Role>(allowed[0]);
  const grant = useWrite(
    (body: { user_id: string; role: Role }) => api(`organizations/${org.id}/memberships`, { method: "POST", body }),
    [["org-members", org.id], ["audit"], ["roles"]],
  );

  async function find(e: React.FormEvent) {
    e.preventDefault();
    const value = email.trim();
    if (!value.includes("@")) return setError("Enter the person’s full email address.");
    setError(null);
    setBusy(true);
    try {
      const res = await api<{ match: UserLookupMatch | null }>(`organizations/${org.id}/user-lookup`, { method: "POST", body: { email: value } });
      setMatch(res.match);
      setChecked(value);
    } catch (err) {
      setMatch(null);
      setChecked(null);
      setError(friendlyError(err));
    } finally {
      setBusy(false);
    }
  }

  const held = new Set(match?.roles_in_organization ?? []);
  const offered = allowed.filter((r) => !held.has(r));
  const chosen = offered.includes(role) ? role : offered[0];

  return (
    <Card className="space-y-4">
      <div>
        <h2 className="text-heading">Find someone by email</h2>
        <p className="mt-1 text-small text-muted">To give someone a role, look them up by email. You can only find people who already belong to {org.name}.</p>
      </div>
      <form onSubmit={find} className="flex flex-col gap-3 sm:flex-row sm:items-start" noValidate>
        <div className="flex-1">
          <Field label="Email address" htmlFor="lookup-email" error={error ?? undefined}>
            <Input id="lookup-email" type="email" autoComplete="off" inputMode="email" value={email} onChange={(e) => { setEmail(e.target.value); setChecked(null); setMatch(null); }} />
          </Field>
        </div>
        <Button type="submit" loading={busy} disabled={!email.trim()} className="sm:mt-[26px]"><Search className="size-4" aria-hidden /> Look up</Button>
      </form>

      {checked !== null && match === null && (
        // The same words for everyone who isn't a member here, so this can't reveal who has an account elsewhere.
        <Alert tone="info">No one in your organization with that email.</Alert>
      )}
      {match && (
        <div className="space-y-3 rounded-control border border-line p-4">
          <div className="flex items-center gap-3">
            <Avatar name={match.full_name ?? "Member"} id={match.user_id} size={44} />
            <div className="min-w-0">
              <p className="truncate font-semibold">{match.full_name ?? "Member"}</p>
              <p className="text-small text-muted">
                {match.roles_in_organization.length > 0 ? `Already: ${match.roles_in_organization.map(roleLabel).join(", ")}` : "No role here yet"}
              </p>
            </div>
          </div>
          {offered.length === 0 ? (
            <p className="text-small text-muted">There is no other role you can give this person.</p>
          ) : (
            <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
              <div className="sm:w-56">
                <Field label="Role" htmlFor="lookup-role">
                  <Select id="lookup-role" value={chosen} onChange={(e) => setRole(e.target.value as Role)}>
                    {offered.map((r) => <option key={r} value={r}>{roleLabel(r)}</option>)}
                  </Select>
                </Field>
              </div>
              <Button
                loading={grant.isPending}
                onClick={async () => {
                  try {
                    await grant.mutateAsync({ user_id: match.user_id, role: chosen });
                    toast(`${match.full_name ?? "They"} is now ${roleLabel(chosen).toLowerCase()}.`);
                    setMatch(null);
                    setChecked(null);
                    setEmail("");
                  } catch (err) {
                    toast(friendlyError(err), "info");
                  }
                }}
              >
                <UserPlus className="size-4" aria-hidden /> Give role
              </Button>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}

/** Who holds a role in this organization, with a way to give and to take away roles. */
export function TeamPanel({ org }: { org: Organization }) {
  const toast = useToast();
  const me = useMe();
  const roles = useRoles();
  const [page, setPage] = useState(0);
  const members = useOrgMembers(org.id, page);
  const [removing, setRemoving] = useState<MemberListItem | null>(null);
  const revoke = useWrite(
    (m: MemberListItem) => api(`organizations/${org.id}/memberships/${m.membership_id}`, { method: "DELETE" }),
    [["org-members", org.id], ["audit"], ["roles"]],
  );

  const allowed = assignableRoles(roles.data, org);
  const platform = isPlatformAdmin(roles.data);
  // The server decides; this only avoids offering buttons it will refuse. Organization admins
  // are removed by platform admins only, and nobody removes their own role.
  const canRemove = (m: MemberListItem) => m.user_id !== me.data?.id && (platform || !ORG_ADMIN_ROLES.includes(m.role));

  const items = members.data?.items ?? [];
  const total = members.data?.total ?? null;
  const hasNext = total !== null ? (page + 1) * TEAM_PAGE_SIZE < total : items.length === TEAM_PAGE_SIZE;

  return (
    <div className="space-y-6">
      {allowed.length > 0 && <Lookup org={org} allowed={allowed} />}

      <Card className="space-y-3">
        <h2 className="text-heading">People with a role{total !== null ? ` (${total})` : ""}</h2>
        {members.isError ? (
          <ErrorState message={members.error.message} onRetry={() => void members.refetch()} />
        ) : members.isLoading ? (
          <Skeleton className="h-32" />
        ) : items.length === 0 ? (
          <EmptyState title="No one has a role here yet" />
        ) : (
          <ul className="divide-y divide-line">
            {items.map((m) => (
              <li key={m.membership_id} className="flex flex-col gap-3 py-3 sm:flex-row sm:items-center">
                <div className="flex min-w-0 flex-1 items-center gap-3">
                  <Avatar name={m.full_name ?? m.email} id={m.user_id} size={44} />
                  <div className="min-w-0">
                    <p className="break-words font-medium">{m.full_name ?? m.email}</p>
                    {m.full_name && <p className="break-all text-small text-muted">{m.email}</p>}
                    <p className="mt-0.5 flex flex-wrap items-center gap-2 text-caption text-muted">
                      <Badge tone="blue">{roleLabel(m.role)}</Badge>
                      since {formatDate(m.since)}
                      {m.account_status !== "active" && <Badge tone="warn">Account {m.account_status}</Badge>}
                    </p>
                  </div>
                </div>
                {canRemove(m) && (
                  <Button variant="secondary" size="sm" onClick={() => setRemoving(m)}>
                    <UserMinus className="size-4" aria-hidden /> Take role away
                  </Button>
                )}
              </li>
            ))}
          </ul>
        )}
        {(page > 0 || hasNext) && (
          <nav aria-label="Pages" className="flex items-center justify-between gap-3 pt-2">
            <Button variant="secondary" onClick={() => setPage((p) => p - 1)} disabled={page === 0}>Previous</Button>
            <span className="text-small text-muted">Page {page + 1}</span>
            <Button variant="secondary" onClick={() => setPage((p) => p + 1)} disabled={!hasNext}>Next</Button>
          </nav>
        )}
      </Card>

      <ConfirmDialog
        open={removing !== null}
        title={`Take the ${removing ? roleLabel(removing.role).toLowerCase() : ""} role from ${removing?.full_name ?? removing?.email ?? "this person"}?`}
        body="They lose this role straight away. You can give it back later."
        confirmLabel="Take role away"
        danger
        onClose={() => setRemoving(null)}
        onConfirm={async () => {
          if (!removing) return;
          await revoke.mutateAsync(removing);
          toast("Role removed.");
        }}
      />
    </div>
  );
}

