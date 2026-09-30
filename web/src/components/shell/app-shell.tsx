"use client";

import {
  Bell, Briefcase, CalendarDays, GraduationCap, Handshake, Home, Leaf, LogOut, MoreHorizontal,
  MessageSquare, Search, Settings, Trophy, UserPlus, Users, X,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { authCall } from "@/lib/api/client";
import { useConnections, useMe, useRoles } from "@/lib/api/hooks";
import type { Profile } from "@/lib/api/types";
import { topRoleLabel } from "@/lib/roles";
import { cn } from "@/lib/utils";
import { Avatar, Badge, IconButton } from "@/components/ui";
import { Logo } from "./logo";

type Item = { label: string; href: string; icon: React.ElementType; soon?: boolean };

const PRIMARY: Item[] = [
  { label: "Home", href: "/home", icon: Home },
  { label: "Alumni", href: "/alumni", icon: Users },
  { label: "Connections", href: "/connections", icon: UserPlus },
  { label: "Schools", href: "/schools", icon: GraduationCap },
];

const SECONDARY: Item[] = [
  { label: "Partners", href: "/partners", icon: Handshake },
  { label: "Sports & Golf", href: "/sports", icon: Trophy, soon: true },
  { label: "Events", href: "/events", icon: CalendarDays, soon: true },
  { label: "Opportunities", href: "/opportunities", icon: Briefcase, soon: true },
  { label: "Projects & Impact", href: "/projects", icon: Leaf, soon: true },
  { label: "Messages", href: "/messages", icon: MessageSquare, soon: true },
  { label: "Notifications", href: "/notifications", icon: Bell, soon: true },
];

function useIncomingCount(): number {
  const me = useMe();
  const conns = useConnections();
  return (conns.data ?? []).filter((c) => c.status === "pending" && c.addressee_id === me.data?.id).length;
}

function useSignOut() {
  const qc = useQueryClient();
  return async () => {
    try {
      await authCall("logout");
    } finally {
      qc.clear();
      window.location.assign("/login");
    }
  };
}

function NavRow({ item, active, incoming }: { item: Item; active: boolean; incoming: number }) {
  const { label, href, icon: Icon, soon } = item;
  const body = (
    <>
      <span
        className={cn(
          "flex size-8 items-center justify-center rounded-lg transition-colors",
          active ? "bg-brand text-white" : "text-white/55 group-hover:text-white/85",
        )}
      >
        <Icon className="size-[18px]" aria-hidden />
      </span>
      <span className="flex-1">{label}</span>
      {soon && <span className="rounded-md bg-white/[0.06] px-1.5 py-0.5 text-[10px] font-medium text-white/40">Soon</span>}
      {href === "/connections" && incoming > 0 && (
        <span className="rounded-full bg-brand px-1.5 text-xs font-semibold text-white">{incoming}</span>
      )}
    </>
  );
  if (soon) {
    return (
      <div aria-disabled className="group flex cursor-not-allowed items-center gap-3 rounded-xl px-2 py-1.5 text-sm text-white/35">
        {body}
      </div>
    );
  }
  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className={cn(
        "group flex items-center gap-3 rounded-xl px-2 py-1.5 text-sm transition-colors",
        active ? "font-semibold text-white" : "text-white/70 hover:bg-white/[0.06] hover:text-white",
      )}
    >
      {body}
    </Link>
  );
}

function Sidebar({ profile }: { profile: Profile }) {
  const pathname = usePathname();
  const roles = useRoles();
  const incoming = useIncomingCount();
  const signOut = useSignOut();
  const isActive = (href: string) => pathname === href || pathname.startsWith(href + "/");

  return (
    <div className="relative flex h-full flex-col overflow-hidden rounded-2xl bg-gradient-to-b from-side to-side-deep text-white shadow-lifted">
      {/* A quiet brand-colored glow at the top — the thing that gives the
          panel some depth instead of being one flat fill. */}
      <div
        className="pointer-events-none absolute -top-24 left-1/2 h-48 w-full -translate-x-1/2 rounded-full bg-brand/25 blur-3xl"
        aria-hidden
      />
      <div className="relative flex items-center gap-3 border-b border-white/[0.06] px-5 py-5">
        <Logo />
        <span className="min-w-0">
          <span className="block truncate text-[15px] font-bold leading-tight tracking-wide">ALUMNI CHALLENGE</span>
          <span className="block truncate text-[11px] text-white/45">Connect · Support · Create Impact</span>
        </span>
      </div>

      <nav aria-label="Main" className="relative flex-1 space-y-4 overflow-y-auto px-3 py-4">
        <div className="space-y-0.5">
          {PRIMARY.map((item) => (
            <NavRow key={item.href} item={item} active={isActive(item.href)} incoming={incoming} />
          ))}
        </div>
        <div>
          <p className="px-2 pb-1.5 text-[11px] font-medium text-white/30">More</p>
          <div className="space-y-0.5">
            {SECONDARY.map((item) => (
              <NavRow key={item.href} item={item} active={isActive(item.href)} incoming={incoming} />
            ))}
          </div>
        </div>
      </nav>

      <div className="relative border-t border-white/[0.06] p-3">
        <Link href="/profile" className="flex items-center gap-3 rounded-xl p-2 transition-colors hover:bg-white/[0.06]">
          <Avatar name={profile.full_name} id={profile.id} size={38} />
          <span className="min-w-0 flex-1">
            <span className="block truncate text-sm font-semibold">{profile.full_name}</span>
            <span className="block truncate text-xs text-white/45">{topRoleLabel(roles.data)}</span>
          </span>
        </Link>
        <div className="mt-1 flex gap-1">
          <Link href="/settings" className="flex flex-1 items-center justify-center gap-2 rounded-lg py-2 text-xs text-white/60 transition-colors hover:bg-white/[0.06] hover:text-white">
            <Settings className="size-4" aria-hidden /> Settings
          </Link>
          <button onClick={signOut} className="flex flex-1 items-center justify-center gap-2 rounded-lg py-2 text-xs text-white/60 transition-colors hover:bg-white/[0.06] hover:text-white">
            <LogOut className="size-4" aria-hidden /> Sign out
          </button>
        </div>
      </div>
    </div>
  );
}

const TABS: Item[] = [PRIMARY[0], PRIMARY[1], PRIMARY[2], PRIMARY[3]];

function MoreSheet({ profile, onClose }: { profile: Profile; onClose: () => void }) {
  const pathname = usePathname();
  const signOut = useSignOut();
  const isActive = (href: string) => pathname === href || pathname.startsWith(href + "/");

  return (
    <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true" aria-label="More">
      <button className="absolute inset-0 bg-black/50" aria-label="Close" onClick={onClose} />
      <div className="absolute inset-x-0 bottom-0 max-h-[80vh] overflow-y-auto rounded-t-3xl bg-side pb-[env(safe-area-inset-bottom,0px)] text-white shadow-lifted">
        <div className="flex items-center justify-between px-5 pb-2 pt-4">
          <Link href="/profile" onClick={onClose} className="flex items-center gap-3">
            <Avatar name={profile.full_name} id={profile.id} size={40} />
            <span>
              <span className="block text-sm font-semibold">{profile.full_name}</span>
              <span className="block text-xs text-white/45">View profile</span>
            </span>
          </Link>
          <button onClick={onClose} aria-label="Close" className="rounded-lg p-2 text-white/60 hover:text-white">
            <X className="size-5" />
          </button>
        </div>
        <div className="space-y-0.5 px-3 py-3">
          {SECONDARY.map((item) => (
            <div key={item.href} onClick={onClose}>
              <NavRow item={item} active={isActive(item.href)} incoming={0} />
            </div>
          ))}
        </div>
        <div className="space-y-0.5 border-t border-white/[0.06] px-3 py-3">
          <Link href="/settings" onClick={onClose} className="flex items-center gap-3 rounded-xl px-2 py-2 text-sm text-white/75 hover:bg-white/[0.06] hover:text-white">
            <Settings className="size-[18px]" aria-hidden /> Settings
          </Link>
          <button onClick={signOut} className="flex w-full items-center gap-3 rounded-xl px-2 py-2 text-left text-sm text-white/75 hover:bg-white/[0.06] hover:text-white">
            <LogOut className="size-[18px]" aria-hidden /> Sign out
          </button>
        </div>
      </div>
    </div>
  );
}

function BottomTabBar({ profile }: { profile: Profile }) {
  const pathname = usePathname();
  const [moreOpen, setMoreOpen] = useState(false);
  const incoming = useIncomingCount();
  const isActive = (href: string) => pathname === href || pathname.startsWith(href + "/");
  const onMoreSection = SECONDARY.some((s) => isActive(s.href)) || pathname === "/settings" || pathname === "/profile";

  return (
    <>
      <nav
        aria-label="Main"
        className="fixed inset-x-0 bottom-0 z-30 flex items-stretch justify-around border-t border-white/[0.08] bg-side pb-[env(safe-area-inset-bottom,0px)] lg:hidden"
      >
        {TABS.map(({ label, href, icon: Icon }) => {
          const active = isActive(href);
          return (
            <Link
              key={href}
              href={href}
              aria-current={active ? "page" : undefined}
              className="relative flex flex-1 flex-col items-center gap-1 py-2.5 text-[11px]"
            >
              <span className={cn("flex size-8 items-center justify-center rounded-lg", active ? "bg-brand text-white" : "text-white/55")}>
                <Icon className="size-[18px]" aria-hidden />
              </span>
              <span className={cn(active ? "font-semibold text-white" : "text-white/55")}>{label}</span>
              {href === "/connections" && incoming > 0 && (
                <span className="absolute right-6 top-1.5 flex size-4 items-center justify-center rounded-full bg-brand text-[9px] font-bold text-white">
                  {incoming}
                </span>
              )}
            </Link>
          );
        })}
        <button
          onClick={() => setMoreOpen(true)}
          className="flex flex-1 flex-col items-center gap-1 py-2.5 text-[11px]"
        >
          <span className={cn("flex size-8 items-center justify-center rounded-lg", onMoreSection ? "bg-brand text-white" : "text-white/55")}>
            <MoreHorizontal className="size-[18px]" aria-hidden />
          </span>
          <span className={cn(onMoreSection ? "font-semibold text-white" : "text-white/55")}>More</span>
        </button>
      </nav>
      {moreOpen && <MoreSheet profile={profile} onClose={() => setMoreOpen(false)} />}
    </>
  );
}

/**
 * The clean, white, icon-button top bar — a search field on the left,
 * Messages and Notifications on the right. Neither has a backend yet
 * (see the sidebar's "Soon" items), so the buttons are present and
 * correctly placed but inert rather than linking to something that
 * doesn't exist — the same honesty the sidebar already applies.
 */
function TopBar() {
  return (
    <div className="sticky top-0 z-20 border-b border-line bg-white/90 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center gap-3 px-4 py-3 sm:px-6 lg:px-8">
        <div className="relative hidden flex-1 max-w-md sm:block">
          <Search className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-faint" aria-hidden />
          <input
            type="search"
            placeholder="Search alumni, schools, partners…"
            disabled
            className="h-10 w-full rounded-full border border-line bg-canvas/60 pl-10 pr-4 text-sm text-ink placeholder:text-faint disabled:cursor-not-allowed"
          />
        </div>
        <div className="flex flex-1 items-center justify-end gap-2 sm:flex-none">
          <IconButton icon={MessageSquare} label="Messages" soon />
          <IconButton icon={Bell} label="Notifications" soon />
        </div>
      </div>
    </div>
  );
}

export function AppShell({ profile, children }: { profile: Profile; children: React.ReactNode }) {
  return (
    <div className="app-canvas min-h-screen">
      <aside className="fixed inset-y-0 left-0 hidden w-72 p-4 lg:block">
        <Sidebar profile={profile} />
      </aside>
      <header className="sticky top-0 z-20 flex items-center gap-3 border-b border-line bg-white/85 px-4 py-3 backdrop-blur lg:hidden">
        <Logo size={28} />
        <span className="font-bold tracking-wide">ALUMNI CHALLENGE</span>
        <div className="ml-auto flex items-center gap-2">
          <IconButton icon={MessageSquare} label="Messages" soon />
          <IconButton icon={Bell} label="Notifications" soon />
        </div>
      </header>
      <main className="lg:pl-72">
        <div className="hidden lg:block">
          <TopBar />
        </div>
        <div className="mx-auto max-w-6xl p-4 pb-24 sm:p-6 lg:p-8 lg:pb-8">{children}</div>
      </main>
      <BottomTabBar profile={profile} />
    </div>
  );
}

export { Badge };
