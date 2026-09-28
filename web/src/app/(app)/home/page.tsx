"use client";

import Link from "next/link";
import { Briefcase, CalendarDays, Leaf, Trophy, UserPlus, Users } from "lucide-react";
import { Avatar, Badge, Card, EmptyState, LinkButton, PageHeader, Spinner, VerifiedMark } from "@/components/ui";
import { useConnections, useDirectory, useMe, useMyProfile, useOrgs } from "@/lib/api/hooks";

const ACTIONS = [
  { href: "/alumni", icon: Users, title: "Browse alumni", body: "Find and connect with fellow members." },
  { href: "/connections", icon: UserPlus, title: "Your connections", body: "See requests and your network." },
  { href: "/schools", icon: Briefcase, title: "Schools", body: "Explore school communities.", swap: true },
  { href: "/partners", icon: Leaf, title: "Partners", body: "Organizations supporting alumni." },
];

export default function HomePage() {
  const me = useMe();
  const profile = useMyProfile();
  const directory = useDirectory(0);
  const connections = useConnections();
  const schools = useOrgs("school");
  const firstName = profile.data?.full_name.split(" ")[0] ?? "there";
  const pending = (connections.data ?? []).filter((c) => c.status === "pending" && c.addressee_id === me.data?.id);

  return (
    <div>
      <PageHeader title={`Welcome back, ${firstName}`} subtitle="Here's what's happening in your network." />

      <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {ACTIONS.map(({ href, icon: Icon, title, body }) => (
          <Link key={href} href={href} className="group">
            <Card className="h-full transition-shadow group-hover:shadow-md">
              <Icon className="size-6 text-brand" aria-hidden />
              <p className="mt-3 font-semibold">{title}</p>
              <p className="mt-1 text-sm text-muted">{body}</p>
            </Card>
          </Link>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card>
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
                  <Link href={`/alumni/${p.id}`} className="flex items-center gap-3 py-3 hover:bg-canvas -mx-2 px-2 rounded-lg">
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
            ].map(({ title, icon: Icon, body }) => (
              <Card key={title} className="opacity-70">
                <Icon className="size-6 text-muted" aria-hidden />
                <p className="mt-3 font-semibold">{title}</p>
                <p className="mt-1 text-sm text-muted">{body}</p>
                <Badge tone="neutral">Coming soon</Badge>
              </Card>
            ))}
          </div>
        </div>

        <div className="space-y-6">
          <Card>
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

          <Card>
            <h2 className="mb-3 font-semibold">Featured schools</h2>
            {schools.isLoading && <Spinner label="Loading" />}
            <ul className="space-y-2">
              {schools.data?.slice(0, 5).map((s) => (
                <li key={s.id}>
                  <Link href={`/schools/${s.id}`} className="block rounded-lg px-2 py-1.5 text-sm hover:bg-canvas">{s.name}</Link>
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
