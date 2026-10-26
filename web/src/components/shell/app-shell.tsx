"use client";

import { CalendarCheck, ChevronDown, Ellipsis, LogOut, PanelLeftClose, PanelLeftOpen, Search, Settings, Ticket, User } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { authCall } from "@/lib/api/client";
import { useConnections, useMe, useOrgs, useRoles } from "@/lib/api/hooks";
import type { Profile } from "@/lib/api/types";
import { navGroupsFor, type NavGroup, type NavItem } from "@/lib/nav";
import { topRoleLabel } from "@/lib/roles";
import { cn } from "@/lib/utils";
import { Avatar, Dialog } from "@/components/ui";
import { Icon3D } from "@/components/ui/icon3d";
import { Logo, LogoTile } from "./logo";
import { MessagesLink } from "./messages-link";
import { NotificationBell } from "./notification-bell";

/** Every link the person's roles allow, in groups: Member, Platform, Moderation, then one group per school or partner. */
function useGroups(): NavGroup[] {
  const roles = useRoles();
  const schools = useOrgs("school");
  const partners = useOrgs("partner");
  return useMemo(() => {
    const names = new Map([...(schools.data ?? []), ...(partners.data ?? [])].map((o) => [o.id, o.name]));
    return navGroupsFor(roles.data, (id) => names.get(id));
  }, [roles.data, schools.data, partners.data]);
}

function useIsActive() {
  const pathname = usePathname();
  return (item: NavItem) => {
    const roots = [item.href, ...(item.also ?? [])];
    // Dashboard and home are exact matches, otherwise they would light up for every page under them.
    const exact = item.href === "/admin" || item.href === "/home" || /^\/(school|partner|organizer)\/[^/]+$/.test(item.href);
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

type Placement = "down" | "rail";
const menuPlace = (p: Placement, w: string) =>
  p === "rail" ? `absolute bottom-0 left-full z-40 ml-3 ${w}` : `absolute right-0 top-full z-40 mt-2 ${w}`;

function ProfileMenu({ profile, placement = "down" }: { profile: Profile | null; placement?: Placement }) {
  const me = useMe();
  const [open, setOpen] = useState(false);
  const ref = useDismiss(open, () => setOpen(false));
  const roles = useRoles();
  const signOut = useSignOut();
  const roleName = topRoleLabel(roles.data);

  return (
    <div ref={ref} className={cn("relative", placement === "rail" && "w-full")}>
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="Account menu"
        onClick={() => setOpen((v) => !v)}
        className={cn(
          "flex min-h-11 items-center focus-visible:outline-2 focus-visible:outline-offset-2",
          placement === "rail" ? "w-full gap-3 rounded-2xl p-0.5 hover:bg-white/10 focus-visible:outline-white" : "gap-2 rounded-full py-1 pl-1 pr-2 hover:bg-sunken focus-visible:outline-ink",
        )}
      >
        <span className={cn("shrink-0 rounded-full", placement === "rail" && "ring-2 ring-white/25")}>
          <Avatar name={profile?.full_name ?? me.data?.email ?? "Account"} id={profile?.id ?? me.data?.id ?? "me"} size={placement === "rail" ? 40 : 36} src={profile?.avatar_url} />
        </span>
        {placement === "rail" && (
          <span className="rail-name min-w-0 text-left">
            <span className="block truncate text-small font-semibold text-white">{profile?.full_name ?? me.data?.email}</span>
            <span className="block truncate text-caption text-white/80">{roleName}</span>
          </span>
        )}
        {placement === "down" && <ChevronDown className={cn("hidden size-3.5 text-muted transition-transform sm:block", open && "rotate-180")} aria-hidden />}
      </button>
      {open && (
        <div role="menu" className={cn(menuPlace(placement, "w-64 max-w-[calc(100vw-2rem)]"), "rounded-xl border border-line bg-surface p-2 shadow-lifted motion-rise")}>
          <div className="border-b border-line px-3 py-2">
            <p className="truncate text-small font-semibold">{profile?.full_name ?? me.data?.email}</p>
            <p className="truncate text-caption text-muted">{roleName}</p>
          </div>
          <Link role="menuitem" href="/profile" onClick={() => setOpen(false)} className={menuItem}>
            <User className="size-4" aria-hidden /> My profile
          </Link>
          <Link role="menuitem" href="/bookings" onClick={() => setOpen(false)} className={menuItem}>
            <CalendarCheck className="size-4" aria-hidden /> My bookings
          </Link>
          <Link role="menuitem" href="/tickets" onClick={() => setOpen(false)} className={menuItem}>
            <Ticket className="size-4" aria-hidden /> My tickets
          </Link>
          <Link role="menuitem" href="/settings" onClick={() => setOpen(false)} className={menuItem}>
            <Settings className="size-4" aria-hidden /> Settings
          </Link>
          <button role="menuitem" type="button" onClick={signOut} className={cn(menuItem, "text-danger-ink hover:bg-danger-soft")}>
            <LogOut className="size-4" aria-hidden /> Log out
          </button>
        </div>
      )}
    </div>
  );
}

function Brand({ compact = false, light = false, label = false }: { compact?: boolean; light?: boolean; label?: boolean }) {
  return (
    <Link href="/start" className="flex min-h-11 shrink-0 items-center focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink" aria-label="Alumni Challenge home">
      {light ? <LogoTile size={40} /> : <Logo variant="mark" size={compact ? 36 : 40} />}
      {label && <span className="rail-label whitespace-nowrap text-[11px] font-semibold uppercase tracking-[0.12em] text-white" aria-hidden>Alumni Challenge</span>}
    </Link>
  );
}

/** The search in the top bar: Enter opens the directory with what was typed. */
function SearchForm({ className, id }: { className?: string; id: string }) {
  const router = useRouter();
  const params = useSearchParams();
  const pathname = usePathname();
  const [value, setValue] = useState(pathname === "/directory" ? (params.get("q") ?? "") : "");
  return (
    <form
      role="search"
      className={cn("relative", className)}
      onSubmit={(e) => {
        e.preventDefault();
        const q = value.trim();
        router.push(q ? `/directory?q=${encodeURIComponent(q)}` : "/directory");
      }}
    >
      <Search className="pointer-events-none absolute left-4 top-1/2 size-4 -translate-y-1/2 text-muted" aria-hidden />
      <input
        id={id}
        type="search"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        aria-label="Search alumni"
        placeholder="Search alumni"
        className="h-11 w-full rounded-full border border-line-strong bg-surface pl-11 pr-4 text-body text-ink placeholder:text-faint transition-colors focus:border-brand-ink focus:outline-none focus:ring-2 focus:ring-brand-ink/20 sm:text-small"
      />
    </form>
  );
}

const SearchBox = ({ className, id }: { className?: string; id: string }) => (
  <Suspense fallback={null}><SearchForm className={className} id={id} /></Suspense>
);

/** One item in the sidebar: the tile stays put; the label slides out beside it when the sidebar is open, and a tooltip names it when it is not. */
function RailItem({ item, active, badge }: { item: NavItem; active: boolean; badge?: number }) {
  return (
    <Link
      href={item.href}
      aria-label={badge ? `${item.label}, ${badge} waiting` : item.label}
      aria-current={active ? "page" : undefined}
      className="rail-item group relative flex h-12 w-full items-center gap-3 rounded-2xl pl-0.5 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
    >
      <span className="relative shrink-0">
        <Icon3D icon={item.icon} tone={active ? "ember" : "ink"} size="sm" className="transition-transform duration-200 group-hover:-translate-y-0.5 group-focus-visible:-translate-y-0.5" />
        {badge ? (
          <span className="rail-dot absolute -right-1 -top-1 flex min-w-4 items-center justify-center rounded-full bg-white px-1 text-[10px] font-bold leading-4 text-brand-ink" aria-hidden>{badge}</span>
        ) : null}
      </span>
      <span className={cn("rail-label text-body font-medium", active ? "text-white" : "text-white/85")} aria-hidden>{item.label}</span>
      {badge ? <span className="rail-pill ml-auto mr-2 rounded-full bg-white px-2 text-caption font-bold leading-5 text-brand-ink" aria-hidden>{badge}</span> : null}
      <span
        aria-hidden
        className="rail-tip pointer-events-none absolute left-[calc(100%+1.25rem)] z-50 translate-x-1 whitespace-nowrap rounded-full bg-ink px-3.5 py-1.5 text-small font-medium text-white opacity-0 shadow-lifted transition-[opacity,transform] duration-200 group-hover:translate-x-0 group-hover:opacity-100 group-focus-visible:translate-x-0 group-focus-visible:opacity-100"
      >
        {item.label}
      </span>
    </Link>
  );
}

const WIDE = "(min-width: 1280px)";
const subscribeWide = (cb: () => void) => {
  const m = window.matchMedia(WIDE);
  m.addEventListener("change", cb);
  return () => m.removeEventListener("change", cb);
};
const useWide = () => useSyncExternalStore(subscribeWide, () => window.matchMedia(WIDE).matches, () => false);

/** Desktop: a dark sidebar. Collapsed it is a slim icon rail; expanded it shows labels, the badge and the person's name. */
function Rail({ profile, expanded, onToggle }: { profile: Profile | null; expanded: boolean; onToggle: () => void }) {
  const incoming = useIncomingCount();
  const isActive = useIsActive();
  const groups = useGroups();
  const Toggle = expanded ? PanelLeftClose : PanelLeftOpen;
  return (
    <aside className="rail fixed bottom-3 left-3 top-3 z-30 hidden flex-col rounded-[28px] bg-side px-4 py-4 shadow-lifted lg:flex">
      <div className="rail-head">
        <Brand light label />
        <button
          type="button"
          onClick={onToggle}
          aria-expanded={expanded}
          aria-label={expanded ? "Collapse sidebar" : "Expand sidebar"}
          className="grid size-9 shrink-0 place-items-center rounded-xl bg-white/10 text-white transition-colors hover:bg-white/20 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
        >
          <Toggle className="size-[18px]" aria-hidden />
        </button>
      </div>
      <nav aria-label="Main" className="mt-4 flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto overflow-x-clip py-1">
        {groups.map((g, i) => (
          <div key={g.key} role="group" aria-label={g.title} className="flex flex-col gap-2">
            {i > 0 && <hr className="rail-group-rule mx-2 my-1 border-white/15" />}
            <p className="rail-group-title truncate px-1 pb-0.5 pt-3 text-caption font-semibold uppercase tracking-wide text-white/80">{g.title}</p>
            {g.items.map((item) => (
              <RailItem key={item.href + item.label} item={item} active={isActive(item)} badge={item.href === "/connections" ? incoming : undefined} />
            ))}
          </div>
        ))}
      </nav>
      <div className="mt-3 flex flex-col gap-3">
        <ProfileMenu profile={profile} placement="rail" />
      </div>
    </aside>
  );
}

/** The quiet bar over the page: its title and the search. On phones it also holds the logo, view switcher and account menu. */
function TopBar({ profile }: { profile: Profile | null }) {
  const isActive = useIsActive();
  const groups = useGroups();
  const pathname = usePathname();
  const title = pathname.startsWith("/messages") ? "Messages" : (groups.flatMap((g) => g.items).find(isActive)?.label ?? "");
  // The search finds alumni, so it belongs on the member pages and not over the staff screens.
  const member = groups[0].items.some(isActive) || pathname.startsWith("/messages");
  // The dashboards draw their own bell in their header row, so the bar does not repeat it on wide screens.
  const onDashboard = /^\/(admin|(school|partner|organizer)\/[^/]+)$/.test(pathname);
  return (
    <header className="bg-canvas lg:sticky lg:top-0 lg:z-20 lg:bg-canvas/85 lg:backdrop-blur">
      <div className="flex items-center gap-2 px-4 pt-3 sm:px-6 lg:hidden">
        <Brand compact />
        <p className="min-w-0 flex-1 truncate pl-1 text-lead font-semibold">{title}</p>
        <MessagesLink />
        <NotificationBell />
        <ProfileMenu profile={profile} />
      </div>
      {member && <div className="px-4 pb-1 pt-2 sm:px-6 lg:hidden"><SearchBox id="top-search-phone" className="w-full" /></div>}
      <div className="mx-auto hidden h-20 max-w-[1680px] items-center gap-6 px-10 xl:px-14 lg:flex">
        <p className="min-w-0 flex-1 truncate text-heading font-semibold">{title}</p>
        {member && <SearchBox id="top-search" className="w-full max-w-sm" />}
        {!onDashboard && (
          <div className="flex items-center gap-1">
            <MessagesLink />
            <NotificationBell />
          </div>
        )}
      </div>
    </header>
  );
}

/** Phone: five tabs along the bottom and a More tab that opens everything else, in the same groups as the sidebar. */
function PhoneTabs() {
  const incoming = useIncomingCount();
  const isActive = useIsActive();
  const groups = useGroups();
  const [more, setMore] = useState(false);
  const all = groups.flatMap((g) => g.items);
  // Home, Directory, Events and Connections for everyone; the fifth is the staff landing page, or My profile for members.
  const member = groups[0].items;
  const fifth = groups[1]?.items[0] ?? member.find((i) => i.href === "/profile");
  const tabs = [...member.filter((i) => ["/home", "/directory", "/events", "/connections"].includes(i.href)), ...(fifth ? [fifth] : [])];
  const hidden = all.length > tabs.length;
  const moreActive = hidden && all.some((i) => isActive(i) && !tabs.includes(i));

  const tabClass = "relative flex min-h-[4.25rem] flex-1 flex-col items-center justify-center gap-1 px-0.5 pb-1 pt-1.5 text-[11px] leading-none focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ink";
  return (
    <>
      <nav aria-label="Main" className="fixed inset-x-0 bottom-0 z-30 flex items-stretch justify-around border-t border-line bg-surface pb-[env(safe-area-inset-bottom,0px)] lg:hidden">
        {tabs.map((item) => {
          const active = isActive(item);
          const badge = item.href === "/connections" ? incoming : 0;
          return (
            <Link
              key={item.href + item.label}
              href={item.href}
              aria-current={active ? "page" : undefined}
              aria-label={badge ? `${item.label}, ${badge} waiting` : undefined}
              className={tabClass}
            >
              <Icon3D icon={item.icon} tone={active ? "ember" : "paper"} size="sm" />
              <span className={cn("max-w-full truncate", active ? "font-semibold text-ink" : "text-muted")}>{item.label === "My profile" ? "Profile" : item.label}</span>
              {badge > 0 && (
                <span className="absolute right-[calc(50%-26px)] top-1 flex size-4 items-center justify-center rounded-full bg-brand text-[10px] font-bold text-white" aria-hidden>{badge}</span>
              )}
            </Link>
          );
        })}
        {hidden && (
          <button type="button" aria-haspopup="dialog" aria-expanded={more} onClick={() => setMore(true)} className={tabClass}>
            <Icon3D icon={Ellipsis} tone={moreActive ? "ember" : "paper"} size="sm" />
            <span className={cn("max-w-full truncate", moreActive ? "font-semibold text-ink" : "text-muted")}>More</span>
          </button>
        )}
      </nav>
      <Dialog open={more} onClose={() => setMore(false)} title="More">
        <nav aria-label="All pages" className="space-y-5 pb-2">
          {groups.map((g) => (
            <div key={g.key} role="group" aria-label={g.title}>
              <p className="px-1 pb-1 text-caption font-semibold uppercase tracking-wide text-muted">{g.title}</p>
              <ul>
                {g.items.map((item) => (
                  <li key={item.href + item.label}>
                    <Link
                      href={item.href}
                      onClick={() => setMore(false)}
                      aria-current={isActive(item) ? "page" : undefined}
                      className={cn("flex min-h-11 items-center gap-3 rounded-lg px-2 text-body hover:bg-sunken", isActive(item) && "font-semibold text-brand-ink")}
                    >
                      <item.icon className="size-5 shrink-0" aria-hidden /> {item.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </nav>
      </Dialog>
    </>
  );
}

export function AppShell({ profile, sidebar, children }: { profile: Profile | null; sidebar: "expanded" | "collapsed" | null; children: React.ReactNode }) {
  // The saved choice comes from a cookie, so the server draws the right width. With no choice yet, CSS decides by
  // screen width (collapsed under 1280px, expanded from 1280px) and the toggle starts from the same rule.
  const [pref, setPref] = useState(sidebar);
  const wide = useWide();
  const expanded = pref ? pref === "expanded" : wide;
  function toggle() {
    const next = expanded ? "collapsed" : "expanded";
    setPref(next);
    document.cookie = `ac_sidebar=${next}; path=/; max-age=31536000; samesite=lax${window.location.protocol === "https:" ? "; secure" : ""}`;
  }
  return (
    <div className="shell min-h-dvh bg-canvas lg:pl-[var(--rail-gap)]" data-sb={pref ?? "auto"}>
      <Rail profile={profile} expanded={expanded} onToggle={toggle} />
      <TopBar profile={profile} />
      <PhoneTabs />
      <main id="main">
        <div className="mx-auto max-w-[1680px] px-4 pb-32 pt-4 sm:px-6 sm:pt-5 lg:px-10 lg:pb-10 lg:pt-2 xl:px-14">{children}</div>
      </main>
    </div>
  );
}
