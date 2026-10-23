import type { Membership, Role } from "./api/types";

export const isPlatformAdmin = (m: Membership[] = []) =>
  m.some((x) => x.organization_id === null && (x.role === "admin" || x.role === "super_admin"));

export const isSuperAdmin = (m: Membership[] = []) =>
  m.some((x) => x.organization_id === null && x.role === "super_admin");

/**
 * The platform roles this person may give. Mirrors the server: a super admin can give any of
 * them, an admin can give moderator only. The server still decides (it also checks rank).
 */
export const grantablePlatformRoles = (m: Membership[] = []): Role[] =>
  isSuperAdmin(m) ? ["moderator", "admin", "super_admin"] : isPlatformAdmin(m) ? ["moderator"] : [];

export const canManageOrg = (m: Membership[] = [], orgId: string) =>
  isPlatformAdmin(m) ||
  m.some(
    (x) => x.organization_id === orgId && (x.role === "school_admin" || x.role === "partner_admin"),
  );

export const canVerifyForSchool = (m: Membership[] = [], schoolId: string | null) =>
  isPlatformAdmin(m) ||
  (schoolId !== null && m.some((x) => x.organization_id === schoolId && x.role === "school_admin"));

const LABELS: Record<Role, string> = {
  super_admin: "Super admin",
  admin: "Admin",
  moderator: "Moderator",
  school_admin: "School admin",
  partner_admin: "Partner admin",
  event_manager: "Event manager",
  sports_manager: "Sports manager",
  alumni: "Alumni member",
};
export const roleLabel = (r: Role) => LABELS[r];

const RANK: Role[] = ["super_admin", "admin", "moderator", "school_admin", "partner_admin", "event_manager", "sports_manager"];
export const topRoleLabel = (m: Membership[] = []) => {
  const best = RANK.find((r) => m.some((x) => x.role === r));
  return best ? LABELS[best] : LABELS.alumni;
};

const ADMIN_ROLES: Role[] = ["super_admin", "admin", "moderator", "school_admin", "partner_admin"];

/** True for anyone who holds a role that unlocks part of the admin area. */
export const isAnyAdmin = (m: Membership[] = []) => m.some((x) => ADMIN_ROLES.includes(x.role));

/** school_admin / partner_admin of at least one organization. */
export const isOrgAdmin = (m: Membership[] = []) =>
  m.some((x) => x.organization_id !== null && (x.role === "school_admin" || x.role === "partner_admin"));

/** Mirrors the backend: platform admins see everything, org admins see their own orgs. Moderators get a 403. */
export const canViewAuditLog = (m: Membership[] = []) => isPlatformAdmin(m) || isOrgAdmin(m);

export const canManageAnyOrg = (m: Membership[] = []) => isPlatformAdmin(m) || isOrgAdmin(m);

export const canModerate = (m: Membership[] = []) => isPlatformAdmin(m) || m.some((x) => x.role === "moderator");

/**
 * Roles the signed-in user may grant inside one organization. Mirrors the backend matrix:
 * org admins are appointed by platform admins only; event and sports managers by the
 * organization's own admin or a platform admin.
 */
export const assignableRoles = (m: Membership[] = [], org: { id: string; type: "school" | "partner" }): Role[] => {
  const adminRole: Role = org.type === "school" ? "school_admin" : "partner_admin";
  const platform = isPlatformAdmin(m);
  const orgAdmin = m.some((x) => x.organization_id === org.id && x.role === adminRole);
  const out: Role[] = [];
  if (platform) out.push(adminRole);
  if (platform || orgAdmin) out.push("event_manager", "sports_manager");
  return out;
};

/* ---- Where each kind of person lands, and which views they can switch between ---------- */

export type ViewKind = "member" | "platform" | "moderator" | "school" | "partner";

export type StaffView = {
  /** Stable key for lists and the remembered choice. */
  key: string;
  kind: ViewKind;
  /** The role that grants this view (alumni for the member view). */
  role: Role;
  organizationId: string | null;
  href: string;
};

const MEMBER_VIEW: StaffView = { key: "member", kind: "member", role: "alumni", organizationId: null, href: "/home" };

/**
 * Every view this person can open: the member view first, then one per staff role (one per
 * organization for school and partner admins), highest rank first. Event and sports managers
 * have no features yet, so they only get the member view.
 */
export function viewsFor(m: Membership[] = []): StaffView[] {
  const out: StaffView[] = [MEMBER_VIEW];
  const platformRole = m.find((x) => x.organization_id === null && x.role === "super_admin")
    ?? m.find((x) => x.organization_id === null && x.role === "admin");
  if (platformRole) {
    out.push({ key: "platform", kind: "platform", role: platformRole.role, organizationId: null, href: "/admin" });
  }
  if (m.some((x) => x.role === "moderator")) {
    out.push({ key: "moderator", kind: "moderator", role: "moderator", organizationId: null, href: "/admin/reports" });
  }
  const seen = new Set<string>();
  for (const [role, kind, base] of [
    ["school_admin", "school", "/school"],
    ["partner_admin", "partner", "/partner"],
  ] as const) {
    for (const x of m) {
      if (x.role !== role || !x.organization_id || seen.has(`${kind}:${x.organization_id}`)) continue;
      seen.add(`${kind}:${x.organization_id}`);
      out.push({ key: `${kind}:${x.organization_id}`, kind, role, organizationId: x.organization_id, href: `${base}/${x.organization_id}` });
    }
  }
  return out;
}

/**
 * The page to open after sign-in. The highest role wins: admin, then moderator, then school
 * admin, then partner admin. Someone who runs several schools (or partners) lands on the
 * picker at /school (or /partner). Everyone else, including event and sports managers, lands
 * on the member home.
 */
export function landingFor(m: Membership[] = []): string {
  const views = viewsFor(m);
  const first = views.find((v) => v.kind !== "member");
  if (!first) return MEMBER_VIEW.href;
  if (first.kind === "school" || first.kind === "partner") {
    const same = views.filter((v) => v.kind === first.kind);
    if (same.length > 1) return `/${first.kind}`;
  }
  return first.href;
}

/** The view that matches the current page, so the "Switch view" menu can mark it. */
export function currentViewKey(pathname: string, views: StaffView[]): string {
  const staff = views.filter((v) => v.kind !== "member");
  const match = staff.find((v) => pathname === v.href || pathname.startsWith(`${v.href}/`));
  if (match) return match.key;
  if (pathname.startsWith("/admin")) return staff.find((v) => v.kind === "platform" || v.kind === "moderator")?.key ?? "member";
  return "member";
}
