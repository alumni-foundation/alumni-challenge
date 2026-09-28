"use client";

import {
  Bell, Briefcase, CalendarDays, GraduationCap, Handshake, Home, Leaf, LogOut, Menu,
  MessageSquare, Settings, Trophy, UserPlus, Users, X,
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
import { Avatar, Badge } from "@/components/ui";
import { Logo } from "./logo";

type Item = { label: string; href: string; icon: React.ElementType; soon?: boolean };
const NAV: Item[] = [
  { label: "Home", href: "/home", icon: Home },
  { label: "Alumni", href: "/alumni", icon: Users },
  { label: "Connections", href: "/connections", icon: UserPlus },
  { label: "Schools", href: "/schools", icon: GraduationCap },
  { label: "Sports & Golf", href: "/sports", icon: Trophy, soon: true },
  { label: "Events", href: "/events", icon: CalendarDays, soon: true },
  { label: "Opportunities", href: "/opportunities", icon: Briefcase, soon: true },
  { label: "Partners", href: "/partners", icon: Handshake },
  { label: "Projects & Impact", href: "/projects", icon: Leaf, soon: true },
  { label: "Messages", href: "/messages", icon: MessageSquare, soon: true },
  { label: "Notifications", href: "/notifications", icon: Bell, soon: true },
];

function Sidebar({ profile, onNavigate }: { profile: Profile; onNavigate: () => void }) {
  const pathname = usePathname();
  const qc = useQueryClient();
  const me = useMe();
  const roles = useRoles();
  const conns = useConnections();
  const incoming = (conns.data ?? []).filter((c) => c.status === "pending" && c.addressee_id === me.data?.id).length;

  async function signOut() {
    try {
      await authCall("logout");
    } finally {
      qc.clear();
      window.location.assign("/login");
    }
  }

  return (
    <div className="flex h-full flex-col rounded-2xl bg-side p-4 text-white">
      <Link href="/home" onClick={onNavigate} className="mb-6 flex items-center gap-3 px-2 pt-2">
        <Logo />
        <span>
          <span className="block text-[15px] font-bold leading-tight tracking-wide">ALUMNI CHALLENGE</span>
          <span className="block text-[10px] text-white/60">Connect • Support • Create Impact</span>
        </span>
      </Link>
      <nav aria-label="Main" className="flex-1 space-y-1 overflow-y-auto">
        {NAV.map(({ label, href, icon: Icon, soon }) => {
          const active = pathname === href || pathname.startsWith(href + "/");
          const body = (
            <>
              <Icon className="size-[18px]" aria-hidden />
              <span className="flex-1">{label}</span>
              {soon && <span className="rounded bg-white/10 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-white/50">Soon</span>}
              {href === "/connections" && incoming > 0 && (
                <span className="rounded-full bg-brand px-1.5 text-xs font-semibold">{incoming}</span>
              )}
            </>
          );
          return soon ? (
            <div key={href} aria-disabled className="flex cursor-not-allowed items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-white/40">
              {body}
            </div>
          ) : (
            <Link
              key={href}
              href={href}
              onClick={onNavigate}
              aria-current={active ? "page" : undefined}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors",
                active ? "bg-brand font-semibold text-white" : "text-white/75 hover:bg-white/10 hover:text-white",
              )}
            >
              {body}
            </Link>
          );
        })}
      </nav>
      <div className="mt-4 space-y-2 border-t border-white/10 pt-4">
        <Link href="/profile" onClick={onNavigate} className="flex items-center gap-3 rounded-lg p-2 hover:bg-white/10">
          <Avatar name={profile.full_name} id={profile.id} size={36} />
          <span className="min-w-0">
            <span className="block truncate text-sm font-semibold">{profile.full_name}</span>
            <span className="block truncate text-xs text-white/60">{topRoleLabel(roles.data)}</span>
          </span>
        </Link>
        <div className="flex gap-1">
          <Link href="/settings" onClick={onNavigate} className="flex flex-1 items-center justify-center gap-2 rounded-lg py-2 text-xs text-white/70 hover:bg-white/10 hover:text-white">
            <Settings className="size-4" aria-hidden /> Settings
          </Link>
          <button onClick={signOut} className="flex flex-1 items-center justify-center gap-2 rounded-lg py-2 text-xs text-white/70 hover:bg-white/10 hover:text-white">
            <LogOut className="size-4" aria-hidden /> Sign out
          </button>
        </div>
      </div>
    </div>
  );
}

export function AppShell({ profile, children }: { profile: Profile; children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const close = () => setOpen(false);
  return (
    <div className="min-h-screen">
      <aside className="fixed inset-y-0 left-0 hidden w-72 p-4 lg:block">
        <Sidebar profile={profile} onNavigate={close} />
      </aside>
      <header className="sticky top-0 z-30 flex items-center gap-3 border-b border-line bg-white/90 px-4 py-3 backdrop-blur lg:hidden">
        <button onClick={() => setOpen(true)} aria-label="Open menu" className="rounded-lg p-2 hover:bg-canvas">
          <Menu className="size-5" />
        </button>
        <span className="font-bold tracking-wide">ALUMNI CHALLENGE</span>
      </header>
      {open && (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true" aria-label="Menu">
          <button className="absolute inset-0 bg-black/50" aria-label="Close menu" onClick={close} />
          <div className="absolute inset-y-0 left-0 w-72 max-w-[85%] p-3">
            <Sidebar profile={profile} onNavigate={close} />
            <button onClick={close} aria-label="Close menu" className="absolute right-5 top-5 rounded-lg p-1 text-white/70 hover:text-white">
              <X className="size-5" />
            </button>
          </div>
        </div>
      )}
      <main className="lg:pl-72">
        <div className="mx-auto max-w-6xl p-4 sm:p-6 lg:p-8">{children}</div>
      </main>
    </div>
  );
}

export { Badge };
