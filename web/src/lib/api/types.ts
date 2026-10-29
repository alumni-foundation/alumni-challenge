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
 * TODO: regenerate with `npm run api:types` once GET /users and DELETE /organizations/{id}/email-domains/{domain_id}
 * are in schema.d.ts, then replace this hand-written type with an alias. It follows the backend agent's description:
 * each item has id, email, full_name, status, roles and created_at. `roles` may be plain role names or objects.
 */
export type UserListItem = {
  id: string;
  email: string;
  full_name: string | null;
  status: S["UserStatus"];
  roles: (Role | { role: Role; organization_id?: string | null })[];
  created_at: string;
};

/* Events, bookings and tickets (docs/events-api.md). */
export type EventSummary = S["EventSummary"];
export type EventDetail = S["EventDetail"];
export type EventSlot = S["SlotOut"];
export type EventQuestion = S["QuestionOut"];
export type EventConsent = S["ConsentOut"];
export type Booking = S["BookingOut"];
export type BookingBrief = S["BookingBrief"];
export type BookingStatus = S["BookingStatus"];
export type BookingCreate = S["BookingCreate"];
export type ParticipantInput = S["ParticipantInput"];
export type AnswerInput = S["AnswerInput"];
export type Ticket = S["TicketOut"];

/* Creating and running events (the organizer screens). */
export type EventCreate = S["EventCreate"];
export type EventUpdate = S["EventUpdate"];
export type EventCategory = S["EventCategory"];
export type EventVisibility = S["EventVisibility"];
export type EventStatus = S["EventStatus"];
export type SlotUpdate = S["SlotUpdate"];
