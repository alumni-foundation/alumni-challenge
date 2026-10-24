"use client";

import {
  Building2, Check, ChevronDown, FileText, Globe, GraduationCap, Home, LayoutDashboard, LogOut, Pencil, Repeat, ScrollText,
  Settings, ShieldCheck, User, UserPlus, Users,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { authCall } from "@/lib/api/client";
import { useConnections, useMe, useOrgs, useRoles } from "@/lib/api/hooks";
import type { Organization, Profile } from "@/lib/api/types";
import { currentViewKey, roleLabel, viewsFor, type StaffView } from "@/lib/roles";
import { cn } from "@/lib/utils";
import { Avatar } from "@/components/ui";
import { Logo } from "./logo";

type NavItem = {
  label: string;
  href: string;
  icon: React.ElementType;
  /** Other path prefixes that should highlight this item (a profile page belongs to Directory). */
  also?: string[];
  /** Left out of the phone tab bar, which has room for five. Still reachable from the dashboard. */
  desktopOnly?: boolean;
};

const MEMBER_NAV: NavItem[] = [
  { label: "Home", href: "/home", icon: Home },
  { label: "Directory", href: "/directory", icon: Users, also: ["/alumni"] },
  { label: "Connections", href: "/connections", icon: UserPlus },
  { label: "My profile", href: "/profile", icon: User },
  { label: "Settings", href: "/settings", icon: Settings },
];
const MEMBER_VIEW_ITEM: NavItem = { label: "Member view", href: "/home", icon: Home };

/** What the navigation shows in each view. School and partner screens add their own items as they are built. */
function navFor(view: StaffView): NavItem[] {
  switch (view.kind) {
    case "member":
      return MEMBER_NAV;
    case "platform":
      return [
        { label: "Dashboard", href: "/admin", icon: LayoutDashboard },
        { label: "Reports", href: "/admin/reports", icon: FileText },
        { label: "Organizations", href: "/admin/organizations", icon: Building2 },
        { label: "Roles", href: "/admin/roles", icon: ShieldCheck, desktopOnly: true },
        { label: "Activity log", href: "/admin/activity", icon: ScrollText },
        MEMBER_VIEW_ITEM,
      ];
    case "moderator":
      return [{ label: "Reports", href: "/admin/reports", icon: FileText }, MEMBER_VIEW_ITEM];
    case "school":
      return [
        { label: "Overview", href: view.href, icon: Building2 },
        { label: "Alumni", href: `${view.href}/roster`, icon: GraduationCap },
        { label: "Team", href: `${view.href}/team`, icon: Users },
        { label: "Activity", href: `${view.href}/activity`, icon: ScrollText },
        { label: "Edit", href: `${view.href}/edit`, icon: Pencil, desktopOnly: true },
        { label: "Email domains", href: `${view.href}/email-domains`, icon: Globe, desktopOnly: true },
        MEMBER_VIEW_ITEM,
      ];
    case "partner":
      return [
        { label: "Overview", href: view.href, icon: Building2 },
        { label: "Team", href: `${view.href}/team`, icon: Users },
        { label: "Activity", href: `${view.href}/activity`, icon: ScrollText },
        { label: "Edit", href: `${view.href}/edit`, icon: Pencil, desktopOnly: true },
        MEMBER_VIEW_ITEM,
      ];
  }
}

function useIsActive() {
  const pathname = usePathname();
  return (item: NavItem) => {
    const roots = [item.href, ...(item.also ?? [])];
    // Dashboard and home are exact matches, otherwise they would light up for every page under them.
    const exact = item.href === "/admin" || item.href === "/home" || /^\/(school|partner)\/[^/]+$/.test(item.href);
    return roots.some((r) => pathname === r || (!exact && pathname.startsWith(`${r}/`)));
  };
}

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
      // Nothing from this person's session may linger for whoever signs in next.
      qc.clear();
      window.location.replace("/login");
    }
  };
}

/** Closes a menu on outside click or Escape. */
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

const menuItem = "flex min-h-11 w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-small text-ink hover:bg-sunken";

function viewLabel(v: StaffView, orgs: Map<string, Organization>): string {
  if (v.kind === "member") return "Member view";
  if (v.kind === "moderator") return "Moderator";
  if (v.kind === "platform") return roleLabel(v.role);
  const name = (v.organizationId && orgs.get(v.organizationId)?.name) || "your organization";
  return `${roleLabel(v.role)} · ${name}`;
}

function useViews() {
  const roles = useRoles();
  const pathname = usePathname();
  const schools = useOrgs("school");
  const partners = useOrgs("partner");
  const views = useMemo(() => viewsFor(roles.data), [roles.data]);
  const orgs = useMemo(
    () => new Map([...(schools.data ?? []), ...(partners.data ?? [])].map((o) => [o.id, o])),
    [schools.data, partners.data],
  );
  const current = views.find((v) => v.key === currentViewKey(pathname, views)) ?? views[0];
  return { views, orgs, current };
}

function SwitchView() {
  const [open, setOpen] = useState(false);
  const ref = useDismiss(open, () => setOpen(false));
  const router = useRouter();
  const { views, orgs, current } = useViews();
  if (views.length < 2) return null;

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        aria-label="Switch view"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="inline-flex h-11 items-center gap-2 whitespace-nowrap rounded-full border border-line-strong bg-surface px-3.5 text-small font-medium hover:bg-sunken"
      >
        <Repeat className="size-4 text-muted" aria-hidden />
        <span aria-hidden className="hidden sm:inline lg:hidden xl:inline">Switch view</span>
        <ChevronDown className={cn("size-3.5 text-muted transition-transform", open && "rotate-180")} aria-hidden />
      </button>
      {open && (
        <div role="menu" aria-label="Switch view" className="absolute right-0 top-full z-40 mt-2 w-72 max-w-[calc(100vw-2rem)] rounded-xl border border-line bg-surface p-2 shadow-lifted motion-rise">
          <p className="px-3 pb-1 pt-2 text-caption font-medium uppercase tracking-wide text-muted">View as</p>
          {views.map((v) => (
            <button
              key={v.key}
              role="menuitem"
              type="button"
              onClick={() => {
                setOpen(false);
                router.push(v.href);
              }}
              className={menuItem}
            >
              <span className="flex-1">{viewLabel(v, orgs)}</span>
              {v.key === current.key && <Check className="size-4 text-brand-ink" aria-label="Current view" />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function ProfileMenu({ profile }: { profile: Profile | null }) {
  const me = useMe();
  const [open, setOpen] = useState(false);
  const ref = useDismiss(open, () => setOpen(false));
  const roles = useRoles();
  const signOut = useSignOut();
  const top = viewsFor(roles.data).at(-1);
  const roleName = viewsFor(roles.data).length > 1 && top ? roleLabel(top.role) : "Alumni member";

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="Account menu"
        onClick={() => setOpen((v) => !v)}
        className="flex min-h-11 items-center gap-2 rounded-full py-1 pl-1 pr-2 hover:bg-sunken"
      >
        <Avatar name={profile?.full_name ?? me.data?.email ?? "Account"} id={profile?.id ?? me.data?.id ?? "me"} size={36} src={profile?.avatar_url} />
        <ChevronDown className={cn("hidden size-3.5 text-muted transition-transform sm:block", open && "rotate-180")} aria-hidden />
      </button>
      {open && (
        <div role="menu" className="absolute right-0 top-full z-40 mt-2 w-64 max-w-[calc(100vw-2rem)] rounded-xl border border-line bg-surface p-2 shadow-lifted motion-rise">
          <div className="border-b border-line px-3 py-2">
            <p className="truncate text-small font-semibold">{profile?.full_name ?? me.data?.email}</p>
            <p className="truncate text-caption text-muted">{roleName}</p>
          </div>
          <Link role="menuitem" href="/profile" onClick={() => setOpen(false)} className={menuItem}>
            <User className="size-4" aria-hidden /> My profile
          </Link>
          <Link role="menuitem" href="/settings" onClick={() => setOpen(false)} className={menuItem}>
            <Settings className="size-4" aria-hidden /> Settings
          </Link>
          <button role="menuitem" type="button" onClick={signOut} className={cn(menuItem, "text-brand-ink hover:bg-brand-soft")}>
            <LogOut className="size-4" aria-hidden /> Log out
          </button>
        </div>
      )}
    </div>
  );
}

function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <Link href="/start" className="flex min-h-11 shrink-0 items-center gap-2.5" aria-label="Alumni Challenge home">
      <Logo size={compact ? 32 : 40} tone="dark" />
      <span className={cn("font-bold tracking-wide text-ink", compact ? "hidden min-[400px]:inline" : "hidden text-lead xl:inline")}>ALUMNI CHALLENGE</span>
    </Link>
  );
}

/** Desktop: logo, this view's links, then the view switcher and account menu. */
function TopNav({ profile }: { profile: Profile | null }) {
  const incoming = useIncomingCount();
  const isActive = useIsActive();
  const { current } = useViews();
  // Settings and My profile live in the account menu on desktop; the top bar stays short.
  const items = navFor(current).filter((i) => !(current.kind === "member" && (i.href === "/settings" || i.href === "/profile")));

  return (
    <header className="sticky top-0 z-30 hidden border-b border-line bg-surface lg:block">
      <div className="mx-auto flex h-20 max-w-[1680px] items-center gap-4 px-6 xl:gap-6 xl:px-10 2xl:gap-8 2xl:px-14">
        <Brand />
        <nav aria-label="Main" className="flex flex-1 items-center gap-1">
          {items.map((item) => {
            const active = isActive(item);
            return (
              <Link
                key={item.href + item.label}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "relative flex min-h-11 items-center gap-1.5 whitespace-nowrap rounded-lg px-2.5 text-body font-medium transition-colors xl:px-3 2xl:px-4",
                  active ? "text-ink" : "text-muted hover:text-ink",
                )}
              >
                {item.label}
                {item.href === "/connections" && incoming > 0 && (
                  <span className="rounded-full bg-brand px-1.5 text-caption font-semibold text-white" aria-label={`${incoming} waiting`}>{incoming}</span>
                )}
                {active && <span className="absolute inset-x-2.5 -bottom-[17px] xl:inset-x-3 2xl:inset-x-4 h-0.5 rounded-full bg-brand-ink" aria-hidden />}
              </Link>
            );
          })}
        </nav>
        <div className="flex items-center gap-3">
          <SwitchView />
          <ProfileMenu profile={profile} />
        </div>
      </div>
    </header>
  );
}

/** Phone: a slim header with the view switcher and account menu, plus tabs along the bottom. */
function PhoneChrome({ profile }: { profile: Profile | null }) {
  const incoming = useIncomingCount();
  const isActive = useIsActive();
  const { views, current } = useViews();

  // Members get four tabs, and staff get one more that opens their highest staff view.
  const tabs: NavItem[] =
    current.kind === "member"
      ? [...MEMBER_NAV.slice(0, 3), { label: "Profile", href: "/profile", icon: User }]
      : navFor(current).filter((i) => !i.desktopOnly);
  const staffView = views.find((v) => v.kind !== "member");
  const withAdmin: NavItem[] =
    current.kind === "member" && staffView
      ? [...tabs, { label: "Admin", href: staffView.href, icon: ShieldCheck }]
      : tabs;

  return (
    <>
      <header className="sticky top-0 z-30 flex items-center gap-2 border-b border-line bg-surface/95 px-4 backdrop-blur lg:hidden">
        <Brand compact />
        <div className="ml-auto flex items-center gap-1">
          <SwitchView />
          <ProfileMenu profile={profile} />
        </div>
      </header>
      <nav
        aria-label="Main"
        className="fixed inset-x-0 bottom-0 z-30 flex items-stretch justify-around border-t border-line bg-surface pb-[env(safe-area-inset-bottom,0px)] lg:hidden"
      >
        {withAdmin.map((item) => {
          const active = isActive(item);
          const Icon = item.icon;
          return (
            <Link
              key={item.href + item.label}
              href={item.href}
              aria-current={active ? "page" : undefined}
              className="relative flex min-h-14 flex-1 flex-col items-center justify-center gap-0.5 px-1 text-caption"
            >
              <Icon className={cn("size-5", active ? "text-brand-ink" : "text-muted")} aria-hidden />
              <span className={cn("max-w-full truncate", active ? "font-semibold text-ink" : "text-muted")}>{item.label}</span>
              {item.href === "/connections" && incoming > 0 && (
                <span className="absolute right-[calc(50%-22px)] top-1.5 flex size-4 items-center justify-center rounded-full bg-brand text-[10px] font-bold text-white" aria-label={`${incoming} waiting`}>
                  {incoming}
                </span>
              )}
            </Link>
          );
        })}
      </nav>
    </>
  );
}

export function AppShell({ profile, children }: { profile: Profile | null; children: React.ReactNode }) {
  return (
    <div className="min-h-dvh bg-canvas">
      <TopNav profile={profile} />
      <PhoneChrome profile={profile} />
      <main id="main">
        <div className="mx-auto max-w-[1680px] px-4 pb-28 pt-5 sm:px-6 sm:pt-6 lg:px-10 lg:pb-10 lg:pt-8 xl:px-14">{children}</div>
      </main>
    </div>
  );
}
