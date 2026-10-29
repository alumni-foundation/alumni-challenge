import {
  Building2, CalendarDays, FileText, Globe, GraduationCap, Home, LayoutDashboard, Pencil, ScrollText,
  Settings, ShieldCheck, User, UserPlus, Users, UserCog,
} from "lucide-react";
import type { Membership } from "./api/types";
import { isPlatformAdmin, orgIdsWithRole } from "./roles";

export type NavItem = {
  label: string;
  href: string;
  icon: React.ElementType;
  /** Other path prefixes that should highlight this item (a profile page belongs to Directory). */
  also?: string[];
};

export type NavGroup = {
  key: string;
  title: string;
  items: NavItem[];
};

export const MEMBER_NAV: NavItem[] = [
  { label: "Home", href: "/home", icon: Home },
  { label: "Directory", href: "/directory", icon: Users, also: ["/alumni"] },
  { label: "Events", href: "/events", icon: CalendarDays, also: ["/bookings", "/tickets"] },
  { label: "Connections", href: "/connections", icon: UserPlus },
  { label: "My profile", href: "/profile", icon: User },
  { label: "Settings", href: "/settings", icon: Settings },
];

const PLATFORM_NAV: NavItem[] = [
  { label: "Dashboard", href: "/admin", icon: LayoutDashboard },
  { label: "Users", href: "/admin/users", icon: UserCog },
  { label: "Organizations", href: "/admin/organizations", icon: Building2 },
  { label: "Events", href: "/admin/events", icon: CalendarDays },
  { label: "Roles", href: "/admin/roles", icon: ShieldCheck },
  { label: "Activity log", href: "/admin/activity", icon: ScrollText },
];

const REPORTS: NavItem = { label: "Reports", href: "/admin/reports", icon: FileText };

/** Items for one school or partner. The same person can also manage its events, which adds a dashboard link. */
function orgItems(id: string, kind: "school" | "partner" | null, eventManager: boolean): NavItem[] {
  const items: NavItem[] = [];
  if (kind) {
    const base = `/${kind}/${id}`;
    items.push({ label: "Overview", href: base, icon: Building2 });
    if (kind === "school") items.push({ label: "Alumni", href: `${base}/roster`, icon: GraduationCap });
    items.push({ label: "Team", href: `${base}/team`, icon: Users });
    items.push({ label: "Activity", href: `${base}/activity`, icon: ScrollText });
    items.push({ label: "Edit", href: `${base}/edit`, icon: Pencil });
    if (kind === "school") items.push({ label: "Email domains", href: `${base}/email-domains`, icon: Globe });
  }
  if (eventManager) items.push({ label: kind ? "Event dashboard" : "Dashboard", href: `/organizer/${id}`, icon: LayoutDashboard });
  return items;
}

/**
 * Every link this person's roles allow, in groups: Member always, Platform for admins, Moderation for
 * moderators (and the reports link for admins), then one group per school or partner they run or whose
 * events they manage, titled with its name. `orgName` supplies the name once organizations have loaded.
 * Sports managers need no group of their own: Events is in the Member group, and it is all the API shows them.
 */
export function navGroupsFor(m: Membership[] = [], orgName: (id: string) => string | undefined = () => undefined): NavGroup[] {
  const groups: NavGroup[] = [{ key: "member", title: "Member", items: MEMBER_NAV }];
  const platform = isPlatformAdmin(m);
  const moderator = m.some((x) => x.role === "moderator");
  if (platform) groups.push({ key: "platform", title: "Platform", items: PLATFORM_NAV });
  if (platform || moderator) {
    // A moderator who is not an admin has no Platform group, so the dashboard moves here.
    groups.push({ key: "moderation", title: "Moderation", items: platform ? [REPORTS] : [PLATFORM_NAV[0], REPORTS] });
  }

  const schools = orgIdsWithRole(m, "school_admin");
  const partners = orgIdsWithRole(m, "partner_admin");
  const managers = orgIdsWithRole(m, "event_manager");
  const orgs = new Map<string, "school" | "partner" | null>();
  for (const id of schools) orgs.set(id, "school");
  for (const id of partners) if (!orgs.has(id)) orgs.set(id, "partner");
  for (const id of managers) if (!orgs.has(id)) orgs.set(id, null);
  for (const [id, kind] of orgs) {
    const items = orgItems(id, kind, managers.includes(id));
    groups.push({ key: `org:${id}`, title: orgName(id) ?? (kind === "partner" ? "Your partner" : kind === "school" ? "Your school" : "Your organization"), items });
  }
  return groups;
}
