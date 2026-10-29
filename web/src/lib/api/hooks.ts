"use client";

import { useMutation, useQuery, useQueryClient, type QueryKey } from "@tanstack/react-query";
import { useMemo } from "react";
import { api, ApiError, apiPage } from "./client";
import type {
  AuditLogEntry,
  Booking,
  BookingStatus,
  Connection,
  EmailDomain,
  EventCreate,
  EventDetail,
  EventSummary,
  EventUpdate,
  MemberListItem,
  Membership,
  Organization,
  OrgCreate,
  OrgType,
  OrgUpdate,
  Profile,
  ProfileSummary,
  Report,
  ReportStatus,
  Role,
  RosterItem,
  Session,
  SlotUpdate,
  Ticket,
  User,
  UserListItem,
} from "./types";

export const PAGE_SIZE = 20;

export const useMe = () =>
  useQuery({ queryKey: ["me"], queryFn: () => api<User>("auth/me"), staleTime: 60_000, retry: false });

export const useRoles = () =>
  useQuery({ queryKey: ["roles"], queryFn: () => api<Membership[]>("auth/me/roles"), staleTime: 60_000 });

/** null means "signed in but no profile yet" (the API answers 404). */
export const useMyProfile = () =>
  useQuery({
    queryKey: ["profile", "me"],
    queryFn: async () => {
      try {
        return await api<Profile>("alumni/profile/me");
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) return null;
        throw e;
      }
    },
    retry: false,
  });

export const useDirectory = (page: number) =>
  useQuery({
    queryKey: ["directory", page],
    queryFn: () => api<ProfileSummary[]>(`alumni/directory?limit=${PAGE_SIZE}&offset=${page * PAGE_SIZE}`),
    placeholderData: (prev) => prev,
  });

export type DirectoryFilters = { q: string; country: string; schoolId: string; year: string; verifiedOnly: boolean; skill: string };
export const NO_FILTERS: DirectoryFilters = { q: "", country: "", schoolId: "", year: "", verifiedOnly: false, skill: "" };

export function directoryQuery(f: DirectoryFilters, page: number): string {
  const qs = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(page * PAGE_SIZE) });
  if (f.q.trim()) qs.set("q", f.q.trim());
  if (f.country.trim()) qs.set("country", f.country.trim());
  if (f.schoolId) qs.set("school_id", f.schoolId);
  if (f.year.trim()) qs.set("graduation_year", f.year.trim());
  if (f.verifiedOnly) qs.set("verified", "true");
  if (f.skill.trim()) qs.set("skill", f.skill.trim());
  return qs.toString();
}

/** One page of directory results and the total number of matches (null if the API didn't say). */
export const useDirectorySearch = (filters: DirectoryFilters, page: number) =>
  useQuery({
    queryKey: ["directory", filters, page],
    queryFn: () => apiPage<ProfileSummary>(`alumni/directory?${directoryQuery(filters, page)}`),
    placeholderData: (prev) => prev,
  });

export const useBlocked = () =>
  useQuery({ queryKey: ["blocked"], queryFn: () => api<Connection[]>("connections/blocked") });

export const useProfile = (id: string, enabled = true) =>
  useQuery({ queryKey: ["profile", id], queryFn: () => api<Profile>(`alumni/${id}`), retry: false, enabled });

export const useConnections = () =>
  useQuery({ queryKey: ["connections"], queryFn: () => api<Connection[]>("connections") });

export const useOrgs = (type: OrgType) =>
  useQuery({
    queryKey: ["orgs", type],
    queryFn: () => api<Organization[]>(`organizations?type=${type}&limit=100`),
    staleTime: 60_000,
  });

export const useOrg = (id: string) =>
  useQuery({ queryKey: ["org", id], queryFn: () => api<Organization>(`organizations/${id}`), retry: false, enabled: id !== "" });

export const useSessions = () =>
  useQuery({ queryKey: ["sessions"], queryFn: () => api<Session[]>("auth/sessions") });

export const useEmailDomains = (orgId: string, enabled: boolean) =>
  useQuery({
    queryKey: ["domains", orgId],
    queryFn: () => api<EmailDomain[]>(`organizations/${orgId}/email-domains`),
    enabled,
  });

/** Any write: run it, then refresh whatever it could have changed. */
export function useWrite<V, R = unknown>(fn: (v: V) => Promise<R>, invalidate: QueryKey[]) {
  const qc = useQueryClient();
  return useMutation<R, ApiError, V>({
    mutationFn: fn,
    onSuccess: () => {
      for (const key of invalidate) void qc.invalidateQueries({ queryKey: key });
    },
  });
}

export const AUDIT_PAGE_SIZE = 50;

export const useAuditLog = (page: number) =>
  useQuery({
    queryKey: ["audit", page],
    queryFn: () => api<AuditLogEntry[]>(`audit-log?limit=${AUDIT_PAGE_SIZE}&offset=${page * AUDIT_PAGE_SIZE}`),
    placeholderData: (prev) => prev,
    retry: false,
  });

/**
 * Every member the directory will show us, for turning user ids into names. The backend has no
 * name search yet, so this walks the directory (100 per request, capped at 1,000 members).
 * Members with private profiles are not in it.
 */
export const useMemberIndex = (enabled: boolean) => {
  const q = useQuery({
    queryKey: ["member-index"],
    enabled,
    staleTime: 5 * 60_000,
    queryFn: async () => {
      const out: ProfileSummary[] = [];
      for (let page = 0; page < 10; page++) {
        const rows = await api<ProfileSummary[]>(`alumni/directory?limit=100&offset=${page * 100}`);
        out.push(...rows);
        if (rows.length < 100) break;
      }
      return out;
    },
  });
  const byUser = useMemo(() => new Map((q.data ?? []).map((p) => [p.user_id, p])), [q.data]);
  return { ...q, byUser };
};

export const useCreateOrg = () =>
  useWrite((body: OrgCreate) => api<Organization>("organizations", { method: "POST", body }), [["orgs"], ["audit"]]);

export const useUpdateOrg = (id: string) =>
  useWrite(
    (body: OrgUpdate) => api<Organization>(`organizations/${id}`, { method: "PATCH", body }),
    [["orgs"], ["org", id], ["audit"]],
  );

export const useAssignMembership = (orgId: string) =>
  useWrite(
    (body: { user_id: string; role: Role }) =>
      api<Membership>(`organizations/${orgId}/memberships`, { method: "POST", body }),
    [["audit"], ["roles"]],
  );

export const useAddEmailDomain = (orgId: string) =>
  useWrite(
    (domain: string) => api<EmailDomain>(`organizations/${orgId}/email-domains`, { method: "POST", body: { domain } }),
    [["domains", orgId], ["audit"]],
  );

export const useRemoveEmailDomain = (orgId: string) =>
  useWrite(
    (domainId: string) => api<null>(`organizations/${orgId}/email-domains/${domainId}`, { method: "DELETE" }),
    [["domains", orgId], ["audit"]],
  );

/**
 * True when a call failed because the server has no such endpoint yet (405, or the framework's own bare 404 that has no
 * application error code), as opposed to "that thing does not exist". Used to switch a button off with an honest tooltip.
 */
export const isMissingEndpoint = (e: unknown) =>
  e instanceof ApiError && (e.status === 405 || (e.status === 404 && e.code === "error"));

export const USERS_PAGE_SIZE = 25;
export type UserStatusFilter = "" | "active" | "suspended";

/** GET /users (platform admins): search by name or email, filter by status. The total comes from X-Total-Count when sent. */
export const useUsers = (q: string, status: UserStatusFilter, page: number, enabled = true) =>
  useQuery({
    enabled,
    queryKey: ["users", q, status, page],
    queryFn: () => {
      const qs = new URLSearchParams({ limit: String(USERS_PAGE_SIZE), offset: String(page * USERS_PAGE_SIZE) });
      if (q.trim()) qs.set("q", q.trim());
      if (status) qs.set("status", status);
      return apiPage<UserListItem>(`users?${qs.toString()}`);
    },
    placeholderData: (prev) => prev,
    retry: false,
  });

export const REPORTS_PAGE_SIZE = 25;

export const useReports = (status: ReportStatus, page: number, enabled = true) =>
  useQuery({
    enabled,
    queryKey: ["reports", status, page],
    queryFn: () =>
      api<Report[]>(`reports?status=${status}&limit=${REPORTS_PAGE_SIZE}&offset=${page * REPORTS_PAGE_SIZE}`),
    // Keep the old rows while paging within a tab, but never show another tab's reports under this one.
    placeholderData: (prev, prevQuery) => (prevQuery?.queryKey[1] === status ? prev : undefined),
    retry: false,
  });

export const TEAM_PAGE_SIZE = 50;
export const ROSTER_PAGE_SIZE = 25;

/** The people who hold a role in one organization, plus the API's total. */
export const useOrgMembers = (orgId: string, page: number) =>
  useQuery({
    queryKey: ["org-members", orgId, page],
    queryFn: () =>
      apiPage<MemberListItem>(`organizations/${orgId}/members?limit=${TEAM_PAGE_SIZE}&offset=${page * TEAM_PAGE_SIZE}`),
    placeholderData: (prev, prevQuery) => (prevQuery?.queryKey[1] === orgId ? prev : undefined),
    retry: false,
  });

export type RosterFilter = { unverifiedOnly: boolean; year: string };

/** The alumni who declared this school, with the total (it can include private profiles). */
export const useRoster = (orgId: string, filter: RosterFilter, page: number) =>
  useQuery({
    queryKey: ["roster", orgId, filter, page],
    queryFn: () => {
      const qs = new URLSearchParams({ limit: String(ROSTER_PAGE_SIZE), offset: String(page * ROSTER_PAGE_SIZE) });
      if (filter.unverifiedOnly) qs.set("verification", "unverified");
      if (filter.year.trim()) qs.set("graduation_year", filter.year.trim());
      return apiPage<RosterItem>(`organizations/${orgId}/roster?${qs.toString()}`);
    },
    placeholderData: (prev) => prev,
    retry: false,
  });

/** The next published events the person may see, soonest first (GET /events lists upcoming ones). */
export const useUpcomingEvents = (limit = 4) =>
  useQuery({
    queryKey: ["events", "upcoming", limit],
    queryFn: () => api<EventSummary[]>(`events?limit=${limit}`),
    staleTime: 60_000,
    retry: false,
  });

/** One event. The page draws it on the server first (`initialData`); a signed-in person also gets their own booking on it. */
export const useEvent = (id: string, opts: { initialData?: EventDetail; enabled: boolean }) =>
  useQuery({
    queryKey: ["event", id],
    queryFn: () => api<EventDetail>(`events/${id}`),
    initialData: opts.initialData,
    enabled: opts.enabled,
    staleTime: 10_000,
    retry: false,
  });

export const BOOKINGS_PAGE_SIZE = 20;

export const useBookings = (status: BookingStatus | "", page: number) =>
  useQuery({
    queryKey: ["bookings", status, page],
    queryFn: () => {
      const qs = new URLSearchParams({ limit: String(BOOKINGS_PAGE_SIZE), offset: String(page * BOOKINGS_PAGE_SIZE) });
      if (status) qs.set("status", status);
      return apiPage<Booking>(`bookings?${qs}`);
    },
    placeholderData: (prev) => prev,
  });

export const useBooking = (id: string) =>
  useQuery({ queryKey: ["booking", id], queryFn: () => api<Booking>(`bookings/${id}`), retry: false });

/** The tickets of one booking. A booking only has tickets once it is confirmed. */
export const useBookingTickets = (id: string, enabled: boolean) =>
  useQuery({ queryKey: ["booking", id, "tickets"], queryFn: () => api<Ticket[]>(`bookings/${id}/tickets`), enabled, retry: false });

/** My tickets for events that have not ended. */
export const useMyTickets = () => useQuery({ queryKey: ["tickets", "mine"], queryFn: () => api<Ticket[]>("tickets/mine") });

export const MANAGED_EVENTS_PAGE_SIZE = 20;

/** The events this person runs, drafts and cancelled ones included (GET /events?manage=true). */
export const useManagedEvents = (page: number, enabled = true) =>
  useQuery({
    enabled,
    queryKey: ["events", "manage", page],
    queryFn: () => apiPage<EventSummary>(`events?manage=true&limit=${MANAGED_EVENTS_PAGE_SIZE}&offset=${page * MANAGED_EVENTS_PAGE_SIZE}`),
    placeholderData: (prev) => prev,
    retry: false,
  });

/** One event for its editor, with whatever state it is in now. No cache: an editor must not start from old data. */
export const useEventToEdit = (id: string) =>
  useQuery({ queryKey: ["event", id, "edit"], queryFn: () => api<EventDetail>(`events/${id}`), retry: false, gcTime: 0, staleTime: 0 });

/**
 * The calls the event editor makes. They are plain functions, not mutations: the editor runs several in a row (save,
 * then the slot, then publish) and shows the server's own words when one fails.
 */
export const eventCalls = {
  create: (body: EventCreate) => api<EventDetail>("events", { method: "POST", body }),
  update: (id: string, body: EventUpdate) => api<EventDetail>(`events/${id}`, { method: "PATCH", body }),
  updateSlot: (id: string, slotId: string, body: SlotUpdate) => api<unknown>(`events/${id}/slots/${slotId}`, { method: "PATCH", body }),
  get: (id: string) => api<EventDetail>(`events/${id}`),
  publish: (id: string) => api<EventDetail>(`events/${id}/publish`, { method: "POST" }),
  close: (id: string) => api<EventDetail>(`events/${id}/close`, { method: "POST" }),
  reopen: (id: string) => api<EventDetail>(`events/${id}/reopen`, { method: "POST" }),
  cancel: (id: string, reason: string) => api<EventDetail>(`events/${id}/cancel`, { method: "POST", body: { reason } }),
  remove: (id: string) => api<null>(`events/${id}`, { method: "DELETE" }),
  setPoster: (id: string, fileId: string) => api<EventDetail>(`events/${id}/poster`, { method: "PUT", body: { file_id: fileId } }),
  removePoster: (id: string) => api<EventDetail>(`events/${id}/poster`, { method: "DELETE" }),
};
