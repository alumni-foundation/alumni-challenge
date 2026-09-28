"use client";

import { LogOut, Monitor } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { Button, Card, PageHeader, Spinner } from "@/components/ui";
import { authCall } from "@/lib/api/client";
import { useSessions, useWrite } from "@/lib/api/hooks";
import { api } from "@/lib/api/client";
import { formatDate } from "@/lib/utils";

export default function SettingsPage() {
  const sessions = useSessions();
  const qc = useQueryClient();
  const revoke = useWrite((id: string) => api(`auth/sessions/${id}`, { method: "DELETE" }), [["sessions"]]);

  async function signOutEverywhere() {
    try {
      await authCall("logout");
    } finally {
      qc.clear();
      window.location.assign("/login");
    }
  }

  return (
    <div className="mx-auto max-w-2xl">
      <PageHeader title="Settings" subtitle="Manage your account and active sessions." />
      <Card>
        <h2 className="mb-3 flex items-center gap-2 font-semibold"><Monitor className="size-4" /> Active sessions</h2>
        {sessions.isLoading && <Spinner label="Loading sessions" />}
        <ul className="divide-y divide-line">
          {sessions.data?.map((s) => (
            <li key={s.id} className="flex items-center justify-between gap-3 py-3">
              <div>
                <p className="text-sm font-medium">{s.device_label || "Unknown device"}</p>
                <p className="text-xs text-muted">{s.ip_address ?? "Unknown IP"} · Last used {formatDate(s.last_used_at)}</p>
              </div>
              <Button size="sm" variant="secondary" loading={revoke.isPending} onClick={() => revoke.mutate(s.id)}>Revoke</Button>
            </li>
          ))}
        </ul>
        {sessions.data?.length === 0 && <p className="text-sm text-muted">No other sessions.</p>}
      </Card>
      <Card className="mt-6">
        <h2 className="mb-2 font-semibold">Sign out</h2>
        <p className="mb-3 text-sm text-muted">End your session on this device.</p>
        <Button variant="danger" onClick={signOutEverywhere}><LogOut className="size-4" /> Sign out</Button>
      </Card>
    </div>
  );
}
