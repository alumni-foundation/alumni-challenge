"use client";

import {
  Bell, Briefcase, CalendarDays, ChevronDown, GraduationCap, Handshake, Home, Leaf, LogOut,
  MoreHorizontal, MessageSquare, Search, Settings, Trophy, User, UserPlus, Users, X,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
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
  { label: "Partners", href: "/partners", icon: Handshake },
];

const SECONDARY: Item[] = [
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

/** Closes a menu on outside click or Escape — shared by the two top-nav dropdowns. */
function useDismiss(open: boolean, onClose: () => void) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const onPointer = (e: PointerEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open, onClose]);
  return ref;
}

function MoreMenu({ isActive }: { isActive: (href: string) => boolean }) {
  const [open, setOpen] = useState(false);
  const ref = useDismiss(open, () => setOpen(false));
  const active = SECONDARY.some((s) => isActive(s.href));

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className={cn(
          "flex items-center gap-1 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
          active ? "text-ink" : "text-muted hover:text-ink",
        )}
      >
        More <ChevronDown className={cn("size-3.5 transition-transform", open && "rotate-180")} aria-hidden />
      </button>
      {open && (
        <div className="absolute left-0 top-full z-30 mt-2 w-64 rounded-xl border border-line bg-white p-2 shadow-lifted">
          {SECONDARY.map(({ label, icon: Icon }) => (
            <div key={label} aria-disabled className="flex cursor-not-allowed items-center gap-3 rounded-lg px-3 py-2 text-sm text-faint">
              <Icon className="size-4" aria-hidden />
              <span className="flex-1">{label}</span>
              <span className="rounded-md bg-canvas px-1.5 py-0.5 text-[10px] font-medium text-faint">Soon</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ProfileMenu({ profile }: { profile: Profile }) {
  const [open, setOpen] = useState(false);
  const ref = useDismiss(open, () => setOpen(false));
  const roles = useRoles();
  const signOut = useSignOut();

  return (
    <div ref={ref} className="relative">
      <button onClick={() => setOpen((v) => !v)} className="flex items-center gap-2 rounded-full py-1 pl-1 pr-2 transition-colors hover:bg-canvas">
        <Avatar name={profile.full_name} id={profile.id} size={32} />
        <span className="hidden text-left sm:block">
          <span className="block max-w-[9rem] truncate text-sm font-semibold leading-tight">{profile.full_name.split(" ")[0]}</span>
        </span>
        <ChevronDown className={cn("hidden size-3.5 text-muted transition-transform sm:block", open && "rotate-180")} aria-hidden />
      </button>
      {open && (
        <div className="absolute right-0 top-full z-30 mt-2 w-60 rounded-xl border border-line bg-white p-2 shadow-lifted">
          <div className="border-b border-line px-3 py-2">
            <p className="truncate text-sm font-semibold">{profile.full_name}</p>
            <p className="truncate text-xs text-muted">{topRoleLabel(roles.data)}</p>
          </div>
          <Link href="/profile" onClick={() => setOpen(false)} className="flex items-center gap-3 rounded-lg px-3 py-2 text-sm text-ink hover:bg-canvas">
            <User className="size-4" aria-hidden /> Your profile
          </Link>
          <Link href="/settings" onClick={() => setOpen(false)} className="flex items-center gap-3 rounded-lg px-3 py-2 text-sm text-ink hover:bg-canvas">
            <Settings className="size-4" aria-hidden /> Settings
          </Link>
          <button onClick={signOut} className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm text-brand hover:bg-brand-soft">
            <LogOut className="size-4" aria-hidden /> Sign out
          </button>
        </div>
      )}
    </div>
  );
}

/**
 * Desktop navigation — a plain white top bar, logo at the far left,
 * nav links next to it, icon buttons and the profile menu at the far
 * right. No sidebar: this is the entire nav surface on large screens.
 */
function TopNav({ profile }: { profile: Profile }) {
  const pathname = usePathname();
  const incoming = useIncomingCount();
  const isActive = (href: string) => pathname === href || pathname.startsWith(href + "/");

  return (
    <header className="sticky top-0 z-30 border-b border-line bg-white">
      <div className="mx-auto flex h-24 max-w-[1680px] items-center gap-8 px-6 lg:px-10 xl:px-14">
        <Link href="/home" className="flex shrink-0 items-center gap-3">
          <Logo size={48} tone="dark" />
          <span className="leading-tight">
            <span className="block text-[20px] font-bold tracking-wide text-ink">ALUMNI CHALLENGE</span>
            <span className="block text-[12px] text-muted">Connect · Support · Create Impact</span>
          </span>
        </Link>

        <nav aria-label="Main" className="hidden flex-1 items-center gap-2 md:flex">
          {PRIMARY.map(({ label, href }) => {
            const active = isActive(href);
            return (
              <Link
                key={href}
                href={href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "relative flex items-center gap-1.5 rounded-lg px-4 py-2.5 text-[15px] font-medium transition-colors",
                  active ? "text-ink" : "text-muted hover:text-ink",
                )}
              >
                {label}
                {href === "/connections" && incoming > 0 && (
                  <span className="rounded-full bg-brand px-1.5 text-xs font-semibold text-white">{incoming}</span>
                )}
                {active && <span className="absolute inset-x-4 -bottom-[1px] h-0.5 rounded-full bg-brand" aria-hidden />}
              </Link>
            );
          })}
          <MoreMenu isActive={isActive} />
        </nav>

        <div className="ml-auto flex items-center gap-3">
          <IconButton icon={Search} label="Search" soon />
          <IconButton icon={MessageSquare} label="Messages" soon />
          <IconButton icon={Bell} label="Notifications" soon />
          <span className="mx-1 hidden h-7 w-px bg-line sm:block" aria-hidden />
          <ProfileMenu profile={profile} />
        </div>
      </div>
    </header>
  );
}

const TABS: Item[] = PRIMARY.slice(0, 4);

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
          <Link href="/partners" onClick={onClose} className={cn("flex items-center gap-3 rounded-xl px-2 py-2 text-sm", isActive("/partners") ? "font-semibold text-white" : "text-white/75 hover:bg-white/[0.06] hover:text-white")}>
            <Handshake className="size-[18px]" aria-hidden /> Partners
          </Link>
          {SECONDARY.map(({ label, href, icon: Icon }) => (
            <div key={href} aria-disabled className="flex items-center gap-3 rounded-xl px-2 py-2 text-sm text-white/35">
              <Icon className="size-[18px]" aria-hidden />
              <span className="flex-1">{label}</span>
              <span className="rounded-md bg-white/[0.06] px-1.5 py-0.5 text-[10px] font-medium text-white/40">Soon</span>
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
  const onMoreSection =
    SECONDARY.some((s) => isActive(s.href)) || pathname === "/settings" || pathname === "/profile" || pathname === "/partners";

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
        <button onClick={() => setMoreOpen(true)} className="flex flex-1 flex-col items-center gap-1 py-2.5 text-[11px]">
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

export function AppShell({ profile, children }: { profile: Profile; children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-canvas">
      <div className="hidden lg:block">
        <TopNav profile={profile} />
      </div>
      <header className="sticky top-0 z-20 flex items-center gap-3 border-b border-line bg-white/90 px-4 py-3 backdrop-blur lg:hidden">
        <Logo size={32} tone="dark" />
        <span className="font-bold tracking-wide text-ink">ALUMNI CHALLENGE</span>
        <div className="ml-auto flex items-center gap-2">
          <IconButton icon={MessageSquare} label="Messages" soon />
          <IconButton icon={Bell} label="Notifications" soon />
        </div>
      </header>
      <main>
        <div className="mx-auto max-w-[1680px] px-4 pb-24 pt-4 sm:px-6 sm:pt-6 lg:px-10 lg:pb-8 lg:pt-8 xl:px-14">{children}</div>
      </main>
      <BottomTabBar profile={profile} />
    </div>
  );
}

export { Badge };
