"use client";

import { Ban, RotateCcw, Search } from "lucide-react";
import { useState } from "react";
import { Row, RowList } from "@/components/staff/rows";
import { Alert, Avatar, Badge, Button, EmptyState, ErrorState, Input, PageHeader, ReasonDialog, Skeleton, Tabs, useToast } from "@/components/ui";
import { api } from "@/lib/api/client";
import { isMissingEndpoint, useMe, useRoles, useUsers, useWrite, USERS_PAGE_SIZE, type UserStatusFilter } from "@/lib/api/hooks";
import type { Role, UserListItem } from "@/lib/api/types";
import { isPlatformAdmin, roleLabel } from "@/lib/roles";
import { useDebounced } from "@/lib/use-debounced";
import { formatDate } from "@/lib/utils";

type Filter = UserStatusFilter | "all";
const FILTERS: { value: Filter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "active", label: "Active" },
  { value: "suspended", label: "Suspended" },
];

const roleNames = (u: UserListItem): Role[] => [...new Set(u.roles.map((r) => (typeof r === "string" ? r : r.role)))];

type Pending = { user: UserListItem; action: "suspend" | "reactivate" } | null;

export default function UsersPage() {
  const roles = useRoles();
  const me = useMe();
  const toast = useToast();
  const [text, setText] = useState("");
  const [status, setStatus] = useState<Filter>("all");
  const [page, setPage] = useState(0);
  const [pending, setPending] = useState<Pending>(null);
  const q = useDebounced(text, 300);
  const platform = isPlatformAdmin(roles.data);
  const users = useUsers(q, status === "all" ? "" : status, page, platform);

  // The same calls the alumni profile page makes, by user id.
  const refresh = [["users"], ["audit"]];
  const suspend = useWrite(({ id, reason }: { id: string; reason: string }) => api(`users/${id}/suspend`, { method: "POST", body: { reason } }), refresh);
  const reactivate = useWrite(({ id, reason }: { id: string; reason: string }) => api(`users/${id}/reactivate`, { method: "POST", body: { reason } }), refresh);

  if (roles.isLoading) return <Skeleton className="h-40 rounded-card" />;
  if (!platform) return <EmptyState title="Users are for administrators" body="Your account doesn’t hold an admin role." />;

  const items = users.data?.items ?? [];
  const total = users.data?.total ?? null;
  const hasNext = total !== null ? (page + 1) * USERS_PAGE_SIZE < total : items.length === USERS_PAGE_SIZE;
  const unavailable = users.isError && isMissingEndpoint(users.error);
  const filtered = q.trim() !== "" || status !== "all";
  const label = pending?.user.full_name ?? pending?.user.email ?? "this account";

  return (
    <div className="max-w-3xl">
      <PageHeader title="Users" subtitle="Everyone with an account. Suspend or reactivate an account here." />

      <div className="space-y-3">
        <div className="relative">
          <Search className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-muted" aria-hidden />
          <Input type="search" aria-label="Search users" placeholder="Search by name or email" value={text} onChange={(e) => { setText(e.target.value); setPage(0); }} className="pl-10" />
        </div>
        <Tabs<Filter> pills label="Account status" tabs={FILTERS} value={status} onChange={(v) => { setStatus(v); setPage(0); }} />
      </div>

      <div role="tabpanel" id={`${status}-panel`} aria-labelledby={`${status}-tab`} className="mt-4 space-y-3" aria-busy={users.isFetching}>
        {unavailable ? (
          <Alert tone="warn">The list of users isn’t available yet, so there is nothing to show. Nothing has been changed.</Alert>
        ) : users.isError ? (
          <ErrorState message={users.error.message} onRetry={() => void users.refetch()} />
        ) : users.isLoading ? (
          <div role="status" aria-label="Loading users" className="space-y-2">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-16 rounded-2xl" />)}</div>
        ) : items.length === 0 ? (
          <EmptyState title={filtered ? "No one matches." : "No users yet."} body={filtered ? "Try a different spelling or another status." : undefined} />
        ) : (
          <>
            <p className="text-small text-muted">
              {total !== null ? `${page * USERS_PAGE_SIZE + 1}–${page * USERS_PAGE_SIZE + items.length} of ${total.toLocaleString("en-KE")}` : `${items.length} shown`}
            </p>
            <RowList label="Users">
              {items.map((u) => {
                const suspended = u.status === "suspended";
                return (
                  <Row key={u.id} stack>
                    <div className="flex min-w-0 flex-1 items-center gap-3">
                      <Avatar name={u.full_name ?? u.email} id={u.id} size={44} />
                      <div className="min-w-0">
                        <p className="break-words font-medium">{u.full_name ?? u.email}</p>
                        {u.full_name && <p className="break-all text-small text-muted">{u.email}</p>}
                        <p className="mt-0.5 flex flex-wrap items-center gap-2 text-caption text-muted">
                          <Badge tone={suspended ? "warn" : u.status === "active" ? "ok" : "neutral"}>{u.status === "active" ? "Active" : suspended ? "Suspended" : "Deleted"}</Badge>
                          {roleNames(u).filter((r) => r !== "alumni").map((r) => <Badge key={r} tone="blue">{roleLabel(r)}</Badge>)}
                          joined {formatDate(u.created_at)}
                        </p>
                      </div>
                    </div>
                    {u.id !== me.data?.id && u.status !== "deleted" && (
                      suspended ? (
                        <Button variant="secondary" size="sm" onClick={() => setPending({ user: u, action: "reactivate" })}><RotateCcw className="size-4" aria-hidden /> Reactivate</Button>
                      ) : (
                        <Button variant="danger" size="sm" onClick={() => setPending({ user: u, action: "suspend" })}><Ban className="size-4" aria-hidden /> Suspend</Button>
                      )
                    )}
                  </Row>
                );
              })}
            </RowList>
            {(page > 0 || hasNext) && (
              <nav aria-label="Pages" className="flex items-center justify-between gap-3 pt-2">
                <Button variant="secondary" onClick={() => setPage((p) => p - 1)} disabled={page === 0}>Previous</Button>
                <span className="text-small text-muted">Page {page + 1}</span>
                <Button variant="secondary" onClick={() => setPage((p) => p + 1)} disabled={!hasNext}>Next</Button>
              </nav>
            )}
          </>
        )}
      </div>

      <ReasonDialog
        open={pending?.action === "suspend"}
        title={`Suspend ${label}?`}
        body="They will be signed out and their profile hidden. Say why, so the activity log explains it."
        confirmLabel="Suspend account"
        danger
        onClose={() => setPending(null)}
        onSubmit={async (reason) => {
          if (!pending) return;
          await suspend.mutateAsync({ id: pending.user.id, reason });
          toast("Account suspended.");
        }}
      />
      <ReasonDialog
        open={pending?.action === "reactivate"}
        title={`Reactivate ${label}?`}
        body="They will be able to sign in again. Say why, so the activity log explains it."
        confirmLabel="Reactivate account"
        onClose={() => setPending(null)}
        onSubmit={async (reason) => {
          if (!pending) return;
          await reactivate.mutateAsync({ id: pending.user.id, reason });
          toast("Account reactivated.");
        }}
      />
    </div>
  );
}
