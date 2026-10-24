"use client";

import { MailCheck, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { RowList, Row } from "@/components/staff/rows";
import { Avatar, Badge, Button, EmptyState, ErrorState, Field, Input, Skeleton, Tabs, useToast, VerifiedMark } from "@/components/ui";
import { api } from "@/lib/api/client";
import { friendlyError } from "@/lib/api/messages";
import { ROSTER_PAGE_SIZE, useRoster, useWrite, type RosterFilter } from "@/lib/api/hooks";
import type { Organization, RosterItem } from "@/lib/api/types";
import { useDebounced } from "@/lib/use-debounced";

type Tab = "all" | "waiting";

const METHOD: Record<string, string> = {
  admin: "by a school admin",
  peer: "by vouches",
  email_domain: "by school email",
};

/** Everyone who named this school, including private profiles, with a quick way to verify. */
export function RosterPanel({ org }: { org: Organization }) {
  const toast = useToast();
  const [tab, setTab] = useState<Tab>("waiting");
  const [year, setYear] = useState("");
  const [page, setPage] = useState(0);
  const [verifying, setVerifying] = useState<string | null>(null);
  const settledYear = useDebounced(year, 300);
  const filter: RosterFilter = { unverifiedOnly: tab === "waiting", year: settledYear };
  const roster = useRoster(org.id, filter, page);
  const verify = useWrite(
    (profileId: string) => api(`alumni/${profileId}/verify`, { method: "PATCH", body: { verified: true } }),
    [["roster", org.id], ["audit"], ["directory"]],
  );

  async function verifyOne(p: RosterItem) {
    setVerifying(p.profile_id);
    try {
      await verify.mutateAsync(p.profile_id);
      toast(`${p.full_name} is verified.`);
    } catch (e) {
      toast(friendlyError(e), "info");
    } finally {
      setVerifying(null);
    }
  }

  const items = roster.data?.items ?? [];
  const total = roster.data?.total ?? null;
  const hasNext = total !== null ? (page + 1) * ROSTER_PAGE_SIZE < total : items.length === ROSTER_PAGE_SIZE;

  return (
    <div className="space-y-4">
      <Tabs<Tab>
        pills
        label="Alumni"
        value={tab}
        onChange={(t) => { setTab(t); setPage(0); }}
        tabs={[{ value: "waiting", label: "Waiting for verification" }, { value: "all", label: "All alumni" }]}
      />
      <div role="tabpanel" id={`${tab}-panel`} aria-labelledby={`${tab}-tab`} className="space-y-4">
        <div className="max-w-xs">
          <Field label="Graduation year" htmlFor="roster-year">
            <Input id="roster-year" type="number" inputMode="numeric" value={year} onChange={(e) => { setYear(e.target.value); setPage(0); }} />
          </Field>
        </div>

        {roster.isError ? (
          <ErrorState message={roster.error.message} onRetry={() => void roster.refetch()} />
        ) : roster.isLoading ? (
          <div className="space-y-3" role="status" aria-label="Loading alumni">
            {[0, 1, 2].map((i) => <Skeleton key={i} className="h-20 rounded-card" />)}
          </div>
        ) : items.length === 0 ? (
          <EmptyState
            title={tab === "waiting" ? "No one is waiting for verification." : "No alumni have named this school yet."}
            body={tab === "waiting" ? "Everyone who named your school is already verified." : undefined}
          />
        ) : (
          <>
            <p className="text-small text-muted">
              {total !== null ? `${page * ROSTER_PAGE_SIZE + 1}–${page * ROSTER_PAGE_SIZE + items.length} of ${total.toLocaleString("en-KE")}` : `${items.length} shown`}
            </p>
            <RowList label="Alumni">
                {items.map((p) => {
                  const verified = p.verification_status === "verified";
                  return (
                    <Row key={p.profile_id} stack>
                      <div className="flex min-w-0 flex-1 items-center gap-3">
                        <Avatar name={p.full_name} id={p.user_id} size={44} />
                        <div className="min-w-0">
                          <Link href={`/alumni/${p.profile_id}`} className="flex min-h-11 items-center gap-1.5 font-medium hover:underline">
                            <span className="truncate">{p.full_name}</span>
                            {verified && <VerifiedMark />}
                          </Link>
                          <p className="text-small text-muted">
                            {[p.graduation_year && `Class of ${p.graduation_year}`, p.country].filter(Boolean).join(" · ") || "No details"}
                          </p>
                          <p className="mt-0.5 flex flex-wrap items-center gap-2 text-caption text-muted">
                            <Badge tone={verified ? "blue" : "neutral"}>
                              {verified ? `Verified${p.verification_method ? ` ${METHOD[p.verification_method] ?? ""}` : ""}` : "Not verified"}
                            </Badge>
                            {p.email_verified && <span className="inline-flex items-center gap-1"><MailCheck className="size-3.5" aria-hidden /> Email confirmed</span>}
                          </p>
                        </div>
                      </div>
                      {!verified && (
                        <Button variant="dark" size="sm" loading={verifying === p.profile_id} disabled={verifying !== null} onClick={() => void verifyOne(p)}>
                          <ShieldCheck className="size-4" aria-hidden /> Verify
                        </Button>
                      )}
                    </Row>
                  );
                })}
            </RowList>
            <nav aria-label="Pages" className="flex items-center justify-between gap-3">
              <Button variant="secondary" onClick={() => setPage((p) => p - 1)} disabled={page === 0}>Previous</Button>
              <span className="text-small text-muted">Page {page + 1}</span>
              <Button variant="secondary" onClick={() => setPage((p) => p + 1)} disabled={!hasNext}>Next</Button>
            </nav>
          </>
        )}
      </div>
    </div>
  );
}
