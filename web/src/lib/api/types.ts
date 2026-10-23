import type { components } from "./schema";

type S = components["schemas"];
export type User = S["UserResponse"];
export type Membership = S["MembershipResponse"];
export type Profile = S["AlumniProfileResponse"];
export type ProfileSummary = S["AlumniProfileSummary"];
export type Connection = S["ConnectionListItem"];
export type Organization = S["OrganizationResponse"];
export type Session = S["SessionResponse"];
export type EmailDomain = S["EmailDomainResponse"];
export type Role = S["Role"];
export type Visibility = S["ProfileVisibility"];
export type OrgType = S["OrganizationType"];
export type OrgCreate = S["OrganizationCreate"];
export type OrgUpdate = S["OrganizationUpdate"];

/**
 * Matches backend AuditLogEntryResponse. Hand-written because schema.d.ts predates the
 * /audit-log endpoint; replace with S["AuditLogEntryResponse"] after regenerating the schema.
 */
export type AuditLogEntry = {
  id: string;
  actor_user_id: string | null;
  action: string;
  target_type: string;
  target_id: string | null;
  context: Record<string, unknown>;
  created_at: string;
};
