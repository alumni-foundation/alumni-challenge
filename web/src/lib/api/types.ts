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
export type Report = S["ReportResponse"];
export type MemberListItem = S["MemberListItem"];
export type RosterItem = S["RosterItem"];
export type UserLookupMatch = S["UserLookupMatch"];
export type ReportStatus = S["ReportStatus"];

export type AuditLogEntry = S["AuditLogEntryResponse"];

/**
 * One event in the list (GET /events). Written by hand from the API's EventSummary because the generated
 * schema file predates the events API; only the fields the app reads are here.
 */
export type EventSummary = {
  id: string;
  title: string;
  category: string;
  starts_at: string;
  ends_at: string;
  venue_name: string | null;
  poster_url: string | null;
  price_minor: number;
  currency: string;
  going_count: number;
  /** null when the event has no cap. */
  spots_left: number | null;
  availability: string;
};
