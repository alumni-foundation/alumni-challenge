"use client";

import { Mail } from "lucide-react";
import { useState } from "react";
import { PeopleCard, ProfileCard, RequestsCard, VerificationCard } from "@/components/home/cards";
import { HomeHero } from "@/components/home/hero";
import { Alert, Button, useToast } from "@/components/ui";
import { api } from "@/lib/api/client";
import { friendlyError } from "@/lib/api/messages";
import { useConnections, useMe, useMyProfile } from "@/lib/api/hooks";

export default function HomePage() {
  const toast = useToast();
  const me = useMe();
  const profile = useMyProfile();
  const connections = useConnections();
  const [resending, setResending] = useState(false);

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

  const p = profile.isLoading ? undefined : (profile.data ?? null);
  const emailVerified = Boolean(me.data?.email_verified_at);
  const all = connections.data ?? [];
  const myId = me.data?.id;
  const ready = !connections.isLoading && !me.isLoading;
  const accepted = all.filter((c) => c.status === "accepted");
  const requests = all.filter((c) => c.status === "pending" && c.addressee_id === myId);
  const firstName = p?.full_name.split(" ")[0];

  return (
    <div className="page-enter mx-auto max-w-6xl space-y-5">
      {me.data && !emailVerified && (
        <Alert tone="warn">
          <p className="font-semibold">Verify your email</p>
          <p className="mt-0.5">We sent a link to {me.data.email}. Open it to confirm your address.</p>
          <Button variant="secondary" size="sm" className="mt-3" loading={resending} onClick={resend}>
            <Mail className="size-4" aria-hidden /> Resend link
          </Button>
        </Alert>
      )}

      <HomeHero
        name={firstName}
        connections={ready ? accepted.length : null}
        waiting={ready ? requests.length : null}
        verified={p === undefined ? null : p?.verification_status === "verified"}
      />

      <div className="grid gap-5 lg:grid-cols-2">
        <RequestsCard requests={requests} loading={!ready} />
        <VerificationCard profile={p} />
        <ProfileCard profile={p} />
        <PeopleCard profile={p} connections={all} />
      </div>
    </div>
  );
}
