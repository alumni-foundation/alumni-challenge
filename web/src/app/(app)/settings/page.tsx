"use client";

import { useQueryClient } from "@tanstack/react-query";
import { Ban, KeyRound, LogOut, Monitor } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { Alert, Badge, Button, Card, ConfirmDialog, ErrorState, LinkButton, PageHeader, Skeleton, useToast } from "@/components/ui";
import { api, authCall } from "@/lib/api/client";
import { friendlyError } from "@/lib/api/messages";
import { useMe, useSessions, useWrite } from "@/lib/api/hooks";
import type { Session } from "@/lib/api/types";
import { formatDate } from "@/lib/utils";

function Section({ icon: Icon, title, children }: { icon: React.ElementType; title: string; children: React.ReactNode }) {
  return (
    <Card className="space-y-3">
      <h2 className="flex items-center gap-2 text-heading"><Icon className="size-5 text-muted" aria-hidden /> {title}</h2>
      {children}
    </Card>
  );
}

export default function SettingsPage() {
  const qc = useQueryClient();
  const toast = useToast();
  const me = useMe();
  const sessions = useSessions();
  const [ending, setEnding] = useState<Session | null>(null);
  const [resending, setResending] = useState(false);
  const revoke = useWrite((id: string) => api(`auth/sessions/${id}`, { method: "DELETE" }), [["sessions"]]);

  async function resend() {
    setResending(true);
    try {
      await api("auth/email/verify/request", { method: "POST" });
      toast("We sent you a new link.");
    } catch (e) {
      toast(friendlyError(e), "info");
    } finally {
      setResending(false);
    }
  }

  async function logOut() {
    try {
      await authCall("logout");
    } finally {
      qc.clear();
      window.location.replace("/login");
    }
  }

  const verified = Boolean(me.data?.email_verified_at);

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <PageHeader title="Settings" subtitle="Your account, your devices and your privacy." />

      <Section icon={KeyRound} title="Account">
        {me.isLoading ? (
          <Skeleton className="h-12" />
        ) : (
          <>
            <div>
              <p className="text-caption text-muted">Email</p>
              <p className="break-all font-medium">{me.data?.email}</p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <Badge tone={verified ? "ok" : "warn"}>{verified ? "Email verified" : "Email not verified"}</Badge>
              {!verified && <Button variant="secondary" size="sm" loading={resending} onClick={resend}>Resend verification</Button>}
            </div>
          </>
        )}
        <div className="border-t border-line pt-3">
          <p className="text-small text-muted">To change your password, we will email you a link to choose a new one.</p>
          <LinkButton href="/forgot-password" variant="secondary" className="mt-2">Reset by email</LinkButton>
        </div>
      </Section>

      <Section icon={Monitor} title="Devices">
        <p className="text-small text-muted">These are the devices signed in to your account. If you don’t recognise one, log it out.</p>
        {sessions.isError ? (
          <ErrorState onRetry={() => void sessions.refetch()} />
        ) : sessions.isLoading ? (
          <Skeleton className="h-20" />
        ) : (
          <ul className="divide-y divide-line">
            {sessions.data?.map((s) => (
              <li key={s.id} className="flex flex-col gap-2 py-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="min-w-0">
                  <p className="truncate font-medium">{s.device_label || "Unknown device"}</p>
                  <p className="text-caption text-muted">{s.ip_address ?? "Unknown address"} · Last used {formatDate(s.last_used_at)}</p>
                </div>
                <Button variant="secondary" size="sm" onClick={() => setEnding(s)}>Log out this device</Button>
              </li>
            ))}
          </ul>
        )}
        <div className="border-t border-line pt-3">
          <Button variant="danger" onClick={logOut}><LogOut className="size-4" aria-hidden /> Log out</Button>
          <p className="mt-2 text-caption text-muted">Ends your session on this device.</p>
        </div>
      </Section>

      <Section icon={Ban} title="Blocked people">
        <p className="text-small text-muted">People you block can’t find you or contact you.</p>
        <Link href="/connections?tab=blocked" className="inline-flex min-h-11 items-center font-medium text-brand-ink hover:underline">See blocked people</Link>
      </Section>

      <Alert tone="info">Notification choices, data export and deleting your account aren’t available yet.</Alert>

      <ConfirmDialog
        open={ending !== null}
        title="Log out this device?"
        body={<>{ending?.device_label || "This device"} will be signed out. If it is the one you are using now, you will be signed out here too.</>}
        confirmLabel="Log out this device"
        danger
        onClose={() => setEnding(null)}
        onConfirm={async () => {
          if (!ending) return;
          await revoke.mutateAsync(ending.id);
          toast("Device logged out.");
        }}
      />
    </div>
  );
}
