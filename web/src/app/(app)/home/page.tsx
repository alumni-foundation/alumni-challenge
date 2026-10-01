"use client";

import Link from "next/link";
import {
  Briefcase, CalendarDays, GraduationCap, Handshake, Search, Trophy, UserPlus, Users,
} from "lucide-react";
import { Avatar, Card, EmptyState, IconChip, LinkButton, Spinner, StatTile, VerifiedMark } from "@/components/ui";
import { cn } from "@/lib/utils";
import { useConnections, useDirectory, useMe, useMyProfile, useOrgs } from "@/lib/api/hooks";

type Quick = { href: string; icon: React.ElementType; label: string; soon?: boolean };
const QUICK: Quick[] = [
  { href: "/alumni", icon: Users, label: "Browse alumni" },
  { href: "/connections", icon: UserPlus, label: "Connections" },
  { href: "/schools", icon: GraduationCap, label: "Schools" },
  { href: "/partners", icon: Handshake, label: "Partners" },
  { href: "/sports", icon: Trophy, label: "Sports & Golf", soon: true },
  { href: "/events", icon: CalendarDays, label: "Events", soon: true },
];

function QuickAction({ href, icon: Icon, label, soon }: Quick) {
  const tone = soon ? "text-white/35" : "text-white";
  const body = (
    <>
      <Icon className={cn("size-8", tone)} strokeWidth={1.5} aria-hidden />
      <span className={cn("text-center text-[13px] font-semibold leading-tight", tone)}>{label}</span>
      {soon && <span className="text-[10px] font-medium text-white/30">Soon</span>}
    </>
  );
  if (soon) {
    return <div aria-disabled className="flex cursor-not-allowed flex-col items-center gap-2 rounded-xl px-2 py-3">{body}</div>;
  }
  return (
    <Link href={href} className="flex flex-col items-center gap-2 rounded-xl px-2 py-3 transition-colors hover:bg-white/[0.07]">
      {body}
    </Link>
  );
}

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
      {/* Full-bleed hero: breaks out of the page's container so the dark
          background reaches the browser edge. Everything — headline,
          search bar, quick-action icons — sits directly on that dark
          background as one continuous block; there is deliberately no
          white card anywhere in the hero. Cards start below the fold,
          same as the reference. */}
      <section className="relative -mx-4 -mt-4 overflow-hidden bg-side sm:-mx-6 sm:-mt-6 lg:-mx-10 lg:-mt-8 xl:-mx-14">
        {/* Demo placeholder — swap the file at web/public/images/hero-demo.jpg
            for a real campus/graduation photo whenever one's ready; nothing
            else here needs to change. */}
        <div
          className="absolute inset-0 bg-cover bg-bottom"
          style={{ backgroundImage: "url(/images/hero-demo.jpg)" }}
          aria-hidden
        />
        <div className="absolute inset-0 bg-side/80" aria-hidden />
        <div className="relative mx-auto max-w-[1680px] px-6 pb-10 pt-10 sm:pb-12 sm:pt-14 lg:px-10 lg:pb-14 xl:px-14">
          <h1 className="max-w-2xl text-3xl font-bold leading-[1.15] text-white sm:text-4xl lg:text-5xl">
            Welcome back, {firstName}.
          </h1>
          <p className="mt-3 max-w-lg text-white/55">
            Connect with fellow alumni, explore schools and partners, and put your network to work.
          </p>

          <div className="relative mt-10">
            <Search className="pointer-events-none absolute left-5 top-1/2 size-5 -translate-y-1/2 text-faint" aria-hidden />
            <input
              type="search"
              disabled
              placeholder="Search alumni, schools, partners…"
              className="h-16 w-full rounded-full border-0 bg-white pl-14 pr-5 text-[15px] text-ink placeholder:text-faint disabled:cursor-not-allowed"
            />
          </div>

          <div className="mt-8 grid grid-cols-3 gap-2 sm:grid-cols-6">
            {QUICK.map((item) => <QuickAction key={item.href} {...item} />)}
          </div>
        </div>
      </section>

      <div className="mb-6 mt-8 flex flex-wrap gap-4">
        <StatTile label="Alumni in directory" value={directory.data?.length ?? "—"} tone="brand" />
        <StatTile label="Your connections" value={accepted.length} tone="blue" />
        <StatTile label="Schools" value={schools.data?.length ?? "—"} tone="gold" />
        <StatTile label="Verification" value={verified ? "Verified" : "Pending"} />
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

          <Card elevation="resting" className="border-dashed opacity-80">
            <IconChip icon={Briefcase} tone="ink" />
            <p className="mt-3 font-semibold">Opportunities & mentorship</p>
            <p className="mt-1 text-sm text-muted">Jobs, internships, and mentor matching for alumni.</p>
            <p className="mt-3 text-xs font-medium text-faint">Coming soon</p>
          </Card>
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
