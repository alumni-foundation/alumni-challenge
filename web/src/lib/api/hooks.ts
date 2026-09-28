"use client";

import { useMutation, useQuery, useQueryClient, type QueryKey } from "@tanstack/react-query";
import { api, ApiError } from "./client";
import type {
  Connection,
  EmailDomain,
  Membership,
  Organization,
  OrgType,
  Profile,
  ProfileSummary,
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
