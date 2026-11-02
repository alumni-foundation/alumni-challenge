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

/* ---- Where each kind of person lands, and which organizations they work in ------------------ */

/** The distinct organizations where this person holds `role`, in the order the memberships came. */
export const orgIdsWithRole = (m: Membership[] = [], role: Role): string[] => [
  ...new Set(m.filter((x) => x.role === role && x.organization_id).map((x) => x.organization_id as string)),
];

/**
 * The page to open after sign-in. The highest role wins: admin, then moderator, then school
 * admin, then partner admin. Someone who runs several schools (or partners) lands on the
 * picker at /school (or /partner). Event managers land on their organization's dashboard,
 * sports managers on Events, and everyone else on the member home.
 */
export function landingFor(m: Membership[] = []): string {
  if (isPlatformAdmin(m)) return "/admin";
  if (m.some((x) => x.role === "moderator")) return "/admin/reports";
  for (const [role, base] of [["school_admin", "/school"], ["partner_admin", "/partner"]] as const) {
    const ids = orgIdsWithRole(m, role);
    if (ids.length > 1) return base;
    if (ids.length === 1) return `${base}/${ids[0]}`;
  }
  // Event and sports managers: whichever role the memberships list first.
  const manager = m.find((x) => x.organization_id && (x.role === "event_manager" || x.role === "sports_manager"));
  if (manager?.role === "event_manager") return `/organizer/${manager.organization_id}`;
  if (manager) return "/events";
  return "/home";
}
