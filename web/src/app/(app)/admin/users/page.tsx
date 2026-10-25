"use client";

import { ChevronRight, UserRound } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { AccountActions } from "@/components/admin/account-actions";
import { Pager, SearchBox, Section, StaffPage } from "@/components/staff/page";
import { Row, RowList } from "@/components/staff/rows";
import { Alert, Avatar, Badge, EmptyState, ErrorState, Field, Input, Skeleton, VerifiedMark } from "@/components/ui";
import { PAGE_SIZE, useDirectorySearch, useRoles, NO_FILTERS } from "@/lib/api/hooks";
import { canModerate, isPlatformAdmin } from "@/lib/roles";
import { useDebounced } from "@/lib/use-debounced";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Reactivate someone who is hidden from search (suspended people are). Needs their user id from the activity log. */
function ById() {
  const [id, setId] = useState("");
  const valid = UUID.test(id.trim());
  return (
    <Section icon={UserRound} tone="ink" title="Reactivate by user ID" hint="Suspended people don’t show up in search. Paste their user ID, which the activity log shows.">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start">
        <div className="flex-1">
          <Field label="User ID" htmlFor="user-id" error={id.trim() && !valid ? "That doesn’t look like a user ID." : undefined}>
            <Input id="user-id" value={id} onChange={(e) => setId(e.target.value)} autoComplete="off" autoCapitalize="none" spellCheck={false} />
          </Field>
        </div>
        <div className="flex gap-2 sm:mt-[26px]">
          {valid && <AccountActions key={id.trim()} userId={id.trim()} name="this person" only="reactivate" size="md" />}
        </div>
      </div>
    </Section>
  );
}

export default function UsersPage() {
  const roles = useRoles();
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(0);
  const settled = useDebounced(query, 300);
  const people = useDirectorySearch({ ...NO_FILTERS, q: settled }, page);

  if (roles.isLoading) return <Skeleton className="h-40 rounded-card" />;
  if (!canModerate(roles.data)) {
    return <EmptyState title="People are for moderators and admins" body="Your account doesn’t hold a moderator or admin role." />;
  }

  const items = people.data?.items ?? [];
  const total = people.data?.total ?? null;
  const hasNext = total !== null ? (page + 1) * PAGE_SIZE < total : items.length === PAGE_SIZE;

  return (
    <StaffPage title="People" subtitle="Find a member to open their profile, or to suspend or reactivate their account.">
      <Alert tone="info">
        Search finds members by name, profession, school and similar words, and only people whose profile is public or for members. The platform has no list of every account yet, so people with a private profile, staff, and anyone already suspended do not appear here.
      </Alert>
      <SearchBox value={query} onChange={(v) => { setQuery(v); setPage(0); }} label="Search members" placeholder="Search by name, school or profession" className="sm:w-96 sm:flex-none" />

      {people.isError ? (
        <ErrorState message={people.error.message} onRetry={() => void people.refetch()} />
      ) : people.isLoading ? (
        <div role="status" aria-label="Loading people" className="space-y-2">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-16 rounded-2xl" />)}</div>
      ) : items.length === 0 ? (
        <EmptyState title="No one matches that search" body="Try a different name or fewer words." />
      ) : (
        <>
          {total !== null && <p className="text-small text-muted">{page * PAGE_SIZE + 1}–{page * PAGE_SIZE + items.length} of {total.toLocaleString("en-KE")}</p>}
          <RowList label="Members">
            {items.map((p) => (
              <Row key={p.id} stack>
                <div className="flex min-w-0 flex-1 items-center gap-3">
                  <Avatar name={p.full_name} id={p.user_id} size={44} />
                  <div className="min-w-0">
                    <p className="flex items-center gap-1.5 font-semibold">
                      <span className="truncate">{p.full_name}</span>
                      {p.verification_status === "verified" && <VerifiedMark />}
                    </p>
                    <p className="truncate text-small text-muted">
                      {[p.profession, p.company, p.graduation_year && `Class of ${p.graduation_year}`].filter(Boolean).join(" · ") || "No details"}
                    </p>
                  </div>
                  <Badge tone="ok">Active</Badge>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <Link href={`/alumni/${p.id}`} className="inline-flex h-11 items-center gap-1 rounded-full border border-line-strong px-4 text-small font-medium hover:bg-sunken focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink sm:h-9 sm:px-3">
                    Open profile <ChevronRight className="size-4" aria-hidden />
                  </Link>
                  <AccountActions userId={p.user_id} name={p.full_name} only="suspend" />
                </div>
              </Row>
            ))}
          </RowList>
          <Pager page={page} hasNext={hasNext} onPage={setPage} busy={people.isFetching} />
        </>
      )}
      {isPlatformAdmin(roles.data) && <ById />}
    </StaffPage>
  );
}
