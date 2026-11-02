"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import {
  Avatar, Button, ConfirmDialog, EmptyState, ErrorState, PageHeader, Skeleton, Tabs, useToast,
} from "@/components/ui";
import { Row as BarRow, RowList } from "@/components/staff/rows";
import { api } from "@/lib/api/client";
import { friendlyError } from "@/lib/api/messages";
import { useBlocked, useConnections, useMe, useWrite } from "@/lib/api/hooks";
import type { Connection } from "@/lib/api/types";

type Tab = "connected" | "received" | "sent" | "blocked";

const EMPTY: Record<Tab, { title: string; body: string }> = {
  connected: { title: "No connections yet", body: "Find alumni in the directory and send your first request." },
  received: { title: "No requests waiting", body: "When someone asks to connect, it will show up here." },
  sent: { title: "No requests sent", body: "Requests you send stay here until the other person replies." },
  blocked: { title: "You haven’t blocked anyone", body: "People you block can’t find you or contact you." },
};

function Row({ c, actions }: { c: Connection; actions: React.ReactNode }) {
  const name = c.other_full_name ?? "Alumni member";
  return (
    <BarRow stack>
      <div className="flex min-w-0 flex-1 items-center gap-3">
        <Avatar name={name} id={c.other_user_id} size={44} />
        {c.other_profile_id ? (
          <Link href={`/alumni/${c.other_profile_id}`} className="inline-flex min-h-11 min-w-0 items-center truncate font-medium hover:underline">{name}</Link>
        ) : (
          <span className="min-w-0 truncate font-medium">{name}</span>
        )}
      </div>
      <div className="flex gap-2 sm:shrink-0">{actions}</div>
    </BarRow>
  );
}

function ConnectionsView() {
  const params = useSearchParams();
  const toast = useToast();
  const me = useMe();
  const connections = useConnections();
  const blocked = useBlocked();
  const [tab, setTab] = useState<Tab>(() => {
    const t = params.get("tab");
    return t === "blocked" || t === "received" || t === "sent" ? t : "connected";
  });
  const [removing, setRemoving] = useState<Connection | null>(null);

  const refresh = [["connections"], ["blocked"], ["directory"]];
  const accept = useWrite((id: string) => api(`connections/${id}/accept`, { method: "PATCH" }), refresh);
  const decline = useWrite((id: string) => api(`connections/${id}/decline`, { method: "PATCH" }), refresh);
  const cancel = useWrite((id: string) => api(`connections/${id}`, { method: "DELETE" }), refresh);
  const unblock = useWrite((id: string) => api(`connections/${id}/unblock`, { method: "POST" }), refresh);

  async function act(fn: () => Promise<unknown>, done: string) {
    try {
      await fn();
      toast(done);
    } catch (e) {
      toast(friendlyError(e), "info");
    }
  }

  const myId = me.data?.id;
  const all = connections.data ?? [];
  const lists: Record<Tab, Connection[]> = {
    connected: all.filter((c) => c.status === "accepted"),
    received: all.filter((c) => c.status === "pending" && c.addressee_id === myId),
    sent: all.filter((c) => c.status === "pending" && c.requester_id === myId),
    blocked: blocked.data ?? [],
  };
  // Declined and removed rows are history and are never shown.

  const loading = connections.isLoading || me.isLoading || (tab === "blocked" && blocked.isLoading);
  const failed = connections.isError || me.isError || (tab === "blocked" && blocked.isError);
  const rows = lists[tab];

  const actionsFor = (c: Connection): React.ReactNode => {
    switch (tab) {
      case "connected":
        return <Button variant="secondary" size="sm" onClick={() => setRemoving(c)}>Remove</Button>;
      case "received":
        return (
          <>
            <Button variant="dark" size="sm" loading={accept.isPending && accept.variables === c.id} onClick={() => act(() => accept.mutateAsync(c.id), "You are now connected.")}>Accept</Button>
            <Button variant="secondary" size="sm" loading={decline.isPending && decline.variables === c.id} onClick={() => act(() => decline.mutateAsync(c.id), "Request declined.")}>Decline</Button>
          </>
        );
      case "sent":
        return <Button variant="secondary" size="sm" loading={cancel.isPending && cancel.variables === c.id} onClick={() => act(() => cancel.mutateAsync(c.id), "Request cancelled.")}>Cancel</Button>;
      case "blocked":
        return <Button variant="secondary" size="sm" loading={unblock.isPending && unblock.variables === c.id} onClick={() => act(() => unblock.mutateAsync(c.id), "Unblocked.")}>Unblock</Button>;
    }
  };

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader title="Connections" subtitle="The people in your network." />
      <Tabs<Tab>
        pills
        label="Connections"
        value={tab}
        onChange={setTab}
        tabs={[
          { value: "connected", label: "Connected" },
          { value: "received", label: "Requests received", count: lists.received.length },
          { value: "sent", label: "Requests sent" },
          { value: "blocked", label: "Blocked" },
        ]}
      />
      <div role="tabpanel" id={`${tab}-panel`} aria-labelledby={`${tab}-tab`} className="mt-4">
        {failed ? (
          <ErrorState onRetry={() => { void connections.refetch(); void blocked.refetch(); }} />
        ) : loading ? (
          <div className="space-y-3" role="status" aria-label="Loading">
            {[0, 1, 2].map((i) => <Skeleton key={i} className="h-16 rounded-card" />)}
          </div>
        ) : rows.length === 0 ? (
          <EmptyState {...EMPTY[tab]} />
        ) : (
          <>
            {tab === "blocked" && (
              <p className="mb-3 text-small text-muted">
                Unblocking someone does not bring back an old connection. You would need to connect again.
              </p>
            )}
            <RowList label="Connections">
              {rows.map((c) => <Row key={c.id} c={c} actions={actionsFor(c)} />)}
            </RowList>
          </>
        )}
      </div>

      <ConfirmDialog
        open={removing !== null}
        title="Remove this connection?"
        body={<>You and {removing?.other_full_name ?? "this person"} will no longer be connected. You can send a new request later.</>}
        confirmLabel="Remove connection"
        danger
        onClose={() => setRemoving(null)}
        onConfirm={async () => {
          if (!removing) return;
          await cancel.mutateAsync(removing.id);
          toast("Connection removed.");
        }}
      />
    </div>
  );
}

export default function ConnectionsPage() {
  return <Suspense><ConnectionsView /></Suspense>;
}
