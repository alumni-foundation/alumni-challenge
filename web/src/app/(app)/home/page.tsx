"use client";

import { Mail } from "lucide-react";
import { useState } from "react";
import { NextEventCard, PeopleBars, ProfileRingCard, RequestBars, UpcomingEvents, VerificationCard } from "@/components/home/cards";
import { HomeHero } from "@/components/home/hero";
import { Alert, Button, useToast } from "@/components/ui";
import { api } from "@/lib/api/client";
import { friendlyError } from "@/lib/api/messages";
import { useConnections, useMe, useMyProfile, useUpcomingEvents } from "@/lib/api/hooks";

export default function HomePage() {
  const toast = useToast();
  const me = useMe();
  const profile = useMyProfile();
  const connections = useConnections();
  const events = useUpcomingEvents(4);
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
  // Shown with a capital first letter; the stored name is not changed.
  const first = p?.full_name.trim().split(/\s+/)[0];
  const firstName = first ? first.charAt(0).toUpperCase() + first.slice(1) : undefined;

  return (
    <div className="page-enter mx-auto max-w-[1280px] space-y-6">
      {me.data && !emailVerified && (
        <Alert tone="warn">
          <p className="font-semibold">Verify your email</p>
          <p className="mt-0.5">We sent a link to {me.data.email}. Open it to confirm your address.</p>
          <Button variant="secondary" size="sm" className="mt-3" loading={resending} onClick={resend}>
            <Mail className="size-4" aria-hidden /> Resend link
          </Button>
        </Alert>
      )}

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.7fr)_minmax(0,1fr)]">
        <HomeHero
          name={firstName}
          connections={ready ? accepted.length : null}
          waiting={ready ? requests.length : null}
          verified={p === undefined ? null : p?.verification_status === "verified"}
        />
        <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-1">
          <ProfileRingCard profile={p} />
          <NextEventCard events={events.data ?? []} loading={events.isLoading} failed={events.isError} />
        </div>
      </div>

      <PeopleBars profile={p} connections={all} />

      <div className="grid gap-6 lg:grid-cols-2 lg:items-start">
        <RequestBars requests={requests} loading={!ready} />
        <VerificationCard profile={p} />
      </div>

      {(events.data?.length ?? 0) >= 2 && <UpcomingEvents events={events.data ?? []} />}
    </div>
  );
}
