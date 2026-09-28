import type { Membership, Role } from "./api/types";

export const isPlatformAdmin = (m: Membership[] = []) =>
  m.some((x) => x.organization_id === null && (x.role === "admin" || x.role === "super_admin"));

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
