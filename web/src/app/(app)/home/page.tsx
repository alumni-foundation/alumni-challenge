"use client";

import Link from "next/link";
import { CalendarDays, GraduationCap, Handshake, Trophy, UserPlus, Users } from "lucide-react";
import { Avatar, Card, EmptyState, IconChip, LinkButton, Spinner, StatTile, VerifiedMark } from "@/components/ui";
import { useConnections, useDirectory, useMe, useMyProfile, useOrgs } from "@/lib/api/hooks";

const ACTIONS = [
  { href: "/alumni", icon: Users, tone: "brand" as const, title: "Browse alumni", body: "Find and connect with fellow members." },
  { href: "/connections", icon: UserPlus, tone: "blue" as const, title: "Your connections", body: "See requests and your network." },
  { href: "/schools", icon: GraduationCap, tone: "gold" as const, title: "Schools", body: "Explore school communities." },
  { href: "/partners", icon: Handshake, tone: "green" as const, title: "Partners", body: "Organizations supporting alumni." },
];

export default function HomePage() {
  const me = useMe();
  const profile = useMyProfile();
  const directory = useDirectory(0);
  const connections = useConnections();
  const schools = useOrgs("school");
  const firstName = profile.data?.full_name.split(" ")[0] ?? "there";
  const all = connections.data ?? [];
  const pending = all.filter((c) => c.status === "pending" && c.addressee_id === me.data?.id);
  const accepted = all.filter((c) => c.status === "accepted");
  const verified = profile.data?.verification_status === "verified";

  return (
    <div>
      {/* Hero: the opening moment is a real welcome, not a page title
          sitting alone on white — this is what gives the app weight. */}
      <div className="relative mb-6 overflow-hidden rounded-2xl bg-gradient-to-br from-side to-side-deep p-6 text-white shadow-lifted sm:p-8">
        <div className="pointer-events-none absolute -right-16 -top-16 size-64 rounded-full bg-brand/30 blur-3xl" aria-hidden />
        <div className="relative">
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Welcome back, {firstName}</h1>
          <p className="mt-1.5 text-white/60">Here&apos;s what&apos;s happening across your network.</p>
        </div>
      </div>

      <div className="mb-6 flex flex-wrap gap-4">
        <StatTile label="Alumni in directory" value={directory.data?.length ?? "—"} tone="brand" />
        <StatTile label="Your connections" value={accepted.length} tone="blue" />
        <StatTile label="Schools" value={schools.data?.length ?? "—"} tone="gold" />
        <StatTile label="Verification" value={verified ? "Verified" : "Pending"} />
      </div>

      <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {ACTIONS.map(({ href, icon, tone, title, body }) => (
          <Link key={href} href={href}>
            <Card elevation="raised" interactive className="h-full">
              <IconChip icon={icon} tone={tone} />
              <p className="mt-3 font-semibold">{title}</p>
              <p className="mt-1 text-sm text-muted">{body}</p>
            </Card>
          </Link>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card elevation="raised">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="font-semibold">Recently active alumni</h2>
              <Link href="/alumni" className="text-sm font-medium text-brand hover:underline">View all</Link>
            </div>
            {directory.isLoading && <Spinner />}
            {directory.data && directory.data.length === 0 && (
              <EmptyState title="No one in the directory yet" body="Be the first — invite classmates to join." />
            )}
            <ul className="divide-y divide-line">
              {directory.data?.slice(0, 6).map((p) => (
                <li key={p.id}>
                  <Link href={`/alumni/${p.id}`} className="-mx-2 flex items-center gap-3 rounded-lg px-2 py-3 hover:bg-canvas">
                    <Avatar name={p.full_name} id={p.id} />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">
                        {p.full_name} {p.verification_status === "verified" && <VerifiedMark />}
                      </p>
                      <p className="truncate text-xs text-muted">{[p.profession, p.country].filter(Boolean).join(" · ") || "Alumni member"}</p>
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          </Card>

          <div className="grid gap-4 sm:grid-cols-2">
            {[
              { title: "Sports & Golf", icon: Trophy, body: "Tournaments and team registration." },
              { title: "Events", icon: CalendarDays, body: "Homecomings, forums and meetups." },
            ].map(({ title, icon, body }) => (
              <Card key={title} elevation="resting" className="border-dashed opacity-80">
                <IconChip icon={icon} tone="ink" />
                <p className="mt-3 font-semibold">{title}</p>
                <p className="mt-1 text-sm text-muted">{body}</p>
                <p className="mt-3 text-xs font-medium text-faint">Coming soon</p>
              </Card>
            ))}
          </div>
        </div>

        <div className="space-y-6">
          <Card elevation="raised">
            <h2 className="mb-3 font-semibold">Pending requests</h2>
            {connections.isLoading && <Spinner label="Loading" />}
            {pending.length === 0 && !connections.isLoading && <p className="text-sm text-muted">No pending requests.</p>}
            <ul className="space-y-3">
              {pending.slice(0, 5).map((c) => (
                <li key={c.id} className="flex items-center gap-3">
                  <Avatar name={c.other_full_name ?? "Alumni member"} id={c.other_user_id} size={32} />
                  <span className="flex-1 truncate text-sm">{c.other_full_name ?? "Alumni member"}</span>
                </li>
              ))}
            </ul>
            {pending.length > 0 && <LinkButton href="/connections" variant="secondary" size="sm" className="mt-3 w-full">Review requests</LinkButton>}
          </Card>

          <Card elevation="raised">
            <h2 className="mb-3 font-semibold">Featured schools</h2>
            {schools.isLoading && <Spinner label="Loading" />}
            <ul className="space-y-1">
              {schools.data?.slice(0, 5).map((s) => (
                <li key={s.id}>
                  <Link href={`/schools/${s.id}`} className="flex items-center gap-2.5 rounded-lg px-2 py-2 text-sm hover:bg-canvas">
                    <IconChip icon={GraduationCap} tone="gold" size={30} />
                    <span className="truncate">{s.name}</span>
                  </Link>
                </li>
              ))}
              {schools.data?.length === 0 && <p className="text-sm text-muted">No schools yet.</p>}
            </ul>
          </Card>
        </div>
      </div>
    </div>
  );
}
