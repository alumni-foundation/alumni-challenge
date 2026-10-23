"use client";

import { useMutation, useQuery, useQueryClient, type QueryKey } from "@tanstack/react-query";
import { useMemo } from "react";
import { api, ApiError } from "./client";
import type {
  AuditLogEntry,
  Connection,
  EmailDomain,
  Membership,
  Organization,
  OrgCreate,
  OrgType,
  OrgUpdate,
  Profile,
  ProfileSummary,
  Role,
  Session,
  User,
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

export const useProfile = (id: string) =>
  useQuery({ queryKey: ["profile", id], queryFn: () => api<Profile>(`alumni/${id}`), retry: false });

export const useConnections = () =>
  useQuery({ queryKey: ["connections"], queryFn: () => api<Connection[]>("connections") });

export const useOrgs = (type: OrgType) =>
  useQuery({
    queryKey: ["orgs", type],
    queryFn: () => api<Organization[]>(`organizations?type=${type}&limit=100`),
    staleTime: 60_000,
  });

export const useOrg = (id: string) =>
  useQuery({ queryKey: ["org", id], queryFn: () => api<Organization>(`organizations/${id}`), retry: false });

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
