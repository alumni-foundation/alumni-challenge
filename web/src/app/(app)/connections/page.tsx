"use client";

import { Check, X } from "lucide-react";
import Link from "next/link";
import { Avatar, Badge, Button, Card, EmptyState, PageHeader, Spinner } from "@/components/ui";
import { api } from "@/lib/api/client";
import { useConnections, useMe, useWrite } from "@/lib/api/hooks";

export default function ConnectionsPage() {
  const me = useMe();
  const connections = useConnections();
  const accept = useWrite((id: string) => api(`connections/${id}/accept`, { method: "PATCH" }), [["connections"]]);
  const decline = useWrite((id: string) => api(`connections/${id}/decline`, { method: "PATCH" }), [["connections"]]);
  const remove = useWrite((id: string) => api(`connections/${id}`, { method: "DELETE" }), [["connections"]]);

  if (connections.isLoading || me.isLoading) return <Spinner label="Loading connections" />;
  const all = connections.data ?? [];
  const incoming = all.filter((c) => c.status === "pending" && c.addressee_id === me.data?.id);
  const outgoing = all.filter((c) => c.status === "pending" && c.requester_id === me.data?.id);
  const accepted = all.filter((c) => c.status === "accepted");

  return (
    <div>
      <PageHeader title="Connections" subtitle="Requests and people in your network." />

      {incoming.length > 0 && (
        <Card className="mb-6">
          <h2 className="mb-3 font-semibold">Requests for you ({incoming.length})</h2>
          <ul className="divide-y divide-line">
            {incoming.map((c) => (
              <li key={c.id} className="flex items-center gap-3 py-3">
                <Avatar name={c.other_full_name ?? "Alumni member"} id={c.other_user_id} />
                <Link href={c.other_profile_id ? `/alumni/${c.other_profile_id}` : "#"} className="flex-1 truncate text-sm font-medium hover:underline">
                  {c.other_full_name ?? "Alumni member"}
                </Link>
                <Button size="sm" loading={accept.isPending} onClick={() => accept.mutate(c.id)}><Check className="size-4" /> Accept</Button>
                <Button size="sm" variant="secondary" loading={decline.isPending} onClick={() => decline.mutate(c.id)}><X className="size-4" /> Decline</Button>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <Card className="mb-6">
        <h2 className="mb-3 font-semibold">Your connections ({accepted.length})</h2>
        {accepted.length === 0 && <p className="text-sm text-muted">No connections yet. Visit the directory to find alumni.</p>}
        <ul className="divide-y divide-line">
          {accepted.map((c) => (
            <li key={c.id} className="flex items-center gap-3 py-3">
              <Avatar name={c.other_full_name ?? "Alumni member"} id={c.other_user_id} />
              <Link href={c.other_profile_id ? `/alumni/${c.other_profile_id}` : "#"} className="flex-1 truncate text-sm font-medium hover:underline">
                {c.other_full_name ?? "Alumni member"}
              </Link>
              <Button size="sm" variant="ghost" loading={remove.isPending} onClick={() => remove.mutate(c.id)}>Remove</Button>
            </li>
          ))}
        </ul>
      </Card>

      {outgoing.length > 0 && (
        <Card>
          <h2 className="mb-3 font-semibold">Sent, awaiting reply ({outgoing.length})</h2>
          <ul className="divide-y divide-line">
            {outgoing.map((c) => (
              <li key={c.id} className="flex items-center gap-3 py-3">
                <Avatar name={c.other_full_name ?? "Alumni member"} id={c.other_user_id} />
                <span className="flex-1 truncate text-sm">{c.other_full_name ?? "Alumni member"}</span>
                <Badge>Pending</Badge>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {all.length === 0 && <EmptyState title="No connections yet" body="Visit the alumni directory to send your first request." />}
    </div>
  );
}
