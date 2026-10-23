"use client";

import { BadgeCheck, Mail, Search, UserPlus, Users } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { Alert, Badge, Button, Card, LinkButton, Skeleton, VerifiedMark, useToast } from "@/components/ui";
import { api } from "@/lib/api/client";
import { friendlyError } from "@/lib/api/messages";
import { useConnections, useMe, useMyProfile } from "@/lib/api/hooks";
import type { Profile } from "@/lib/api/types";

const VOUCHES_NEEDED = 3;

/** The profile details that are still empty, in plain words. The owner always sees all of their own fields. */
function missingFields(p: Profile): string[] {
  const out: string[] = [];
  if (!p.school_id) out.push("your school");
  if (!p.graduation_year) out.push("your graduation year");
  if (!p.profession) out.push("your profession");
  if (!p.company) out.push("your company");
  if (!p.bio) out.push("a short bio");
  if (p.skills.length === 0) out.push("your skills");
  if (p.interests.length === 0) out.push("your interests");
  if (!p.avatar_url) out.push("a photo");
  return out;
}

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

  const p = profile.data;
  const emailVerified = Boolean(me.data?.email_verified_at);
  const waiting = (connections.data ?? []).filter((c) => c.status === "pending" && c.addressee_id === me.data?.id).length;
  const verified = p?.verification_status === "verified";
  const missing = p ? missingFields(p) : [];
  const firstName = p?.full_name.split(" ")[0];

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <header>
        <h1 className="text-title">{firstName ? `Welcome, ${firstName}` : "Welcome"}</h1>
        <p className="mt-1 text-muted">Find your school family and keep in touch.</p>
      </header>

      {me.data && !emailVerified && (
        <Alert tone="warn">
          <p className="font-semibold">Verify your email</p>
          <p className="mt-0.5">We sent a link to {me.data.email}. Open it to confirm your address.</p>
          <Button variant="secondary" size="sm" className="mt-3" loading={resending} onClick={resend}>
            <Mail className="size-4" aria-hidden /> Resend link
          </Button>
        </Alert>
      )}

      <div className="flex flex-col gap-3 sm:flex-row">
        <LinkButton href="/directory" className="sm:flex-1"><Search className="size-4" aria-hidden /> Find alumni</LinkButton>
        <LinkButton href="/profile" variant="secondary" className="sm:flex-1">Edit my profile</LinkButton>
        <LinkButton href="/connections" variant="secondary" className="sm:flex-1"><Users className="size-4" aria-hidden /> My connections</LinkButton>
      </div>

      {waiting > 0 && (
        <Link href="/connections?tab=received" className="block rounded-card">
          <Card interactive className="flex items-center gap-3">
            <span className="inline-flex size-11 items-center justify-center rounded-xl bg-brand-soft text-brand-ink"><UserPlus className="size-5" aria-hidden /></span>
            <span>
              <span className="block font-semibold">
                {waiting} connection {waiting === 1 ? "request is" : "requests are"} waiting for you
              </span>
              <span className="block text-small text-muted">Open them to accept or decline.</span>
            </span>
          </Card>
        </Link>
      )}

      <Card className="space-y-3">
        <div className="flex items-center justify-between gap-3">
          <h2 className="flex items-center gap-2 text-heading"><BadgeCheck className="size-5 text-muted" aria-hidden /> Verification</h2>
          {profile.isLoading ? <Skeleton className="h-6 w-24" /> : <Badge tone={verified ? "blue" : "neutral"}>{verified ? "Verified" : "Unverified"}</Badge>}
        </div>
        {verified ? (
          <p className="text-small text-muted">Your school has confirmed you. Others see a <VerifiedMark /> next to your name.</p>
        ) : (
          <>
            <p className="text-small text-muted">A verified mark shows other alumni that you really went to your school. There are three ways to get it:</p>
            <ol className="list-decimal space-y-1.5 pl-5 text-small">
              <li>Sign up with a school email address.</li>
              <li>Ask your school’s administrator to verify you.</li>
              <li>
                Get vouches from verified alumni of your school.
                {p && <> You have <strong>{p.vouch_count} of {VOUCHES_NEEDED}</strong>.</>}
              </li>
            </ol>
          </>
        )}
      </Card>

      {p && missing.length > 0 && (
        <Card className="space-y-2">
          <h2 className="text-heading">Complete your profile</h2>
          <p className="text-small text-muted">
            People find you more easily with more detail. You haven’t added {missing.join(", ")} yet.
          </p>
          <LinkButton href="/profile" variant="secondary" size="sm">Add details</LinkButton>
        </Card>
      )}
    </div>
  );
}
