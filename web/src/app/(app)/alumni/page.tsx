"use client";

import Link from "next/link";
import { Search } from "lucide-react";
import { useMemo, useState } from "react";
import { Avatar, Button, Card, EmptyState, Input, PageHeader, Spinner, VerifiedMark } from "@/components/ui";
import { PAGE_SIZE, useDirectory } from "@/lib/api/hooks";

export default function AlumniDirectory() {
  const [page, setPage] = useState(0);
  const [q, setQ] = useState("");
  const directory = useDirectory(page);

  const filtered = useMemo(() => {
    const term = q.trim().toLowerCase();
    if (!term) return directory.data ?? [];
    return (directory.data ?? []).filter((p) =>
      [p.full_name, p.profession, p.country, p.company].some((f) => f?.toLowerCase().includes(term)),
    );
  }, [directory.data, q]);

  return (
    <div>
      <PageHeader title="Alumni Directory" subtitle="Search and connect with fellow alumni." />
      <div className="relative mb-5 max-w-md">
        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" aria-hidden />
        <Input placeholder="Search by name, profession, country…" className="pl-9" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>

      {directory.isLoading && <Spinner label="Loading alumni" />}
      {directory.isError && <EmptyState title="Couldn't load the directory" body="Try again in a moment." />}
      {directory.data && filtered.length === 0 && <EmptyState title="No matches" body="Try a different search term." />}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {filtered.map((p) => (
          <Link key={p.id} href={`/alumni/${p.id}`}>
            <Card className="h-full transition-shadow hover:shadow-md">
              <div className="flex items-center gap-3">
                <Avatar name={p.full_name} id={p.id} size={44} />
                <div className="min-w-0">
                  <p className="truncate font-semibold">
                    {p.full_name} {p.verification_status === "verified" && <VerifiedMark />}
                  </p>
                  <p className="truncate text-sm text-muted">{p.profession || "Alumni member"}</p>
                </div>
              </div>
              <p className="mt-3 truncate text-xs text-muted">{[p.company, p.country].filter(Boolean).join(" · ")}</p>
            </Card>
          </Link>
        ))}
      </div>

      {!q && (
        <div className="mt-6 flex items-center justify-between">
          <Button variant="secondary" size="sm" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>Previous</Button>
          <span className="text-sm text-muted">Page {page + 1}</span>
          <Button variant="secondary" size="sm" disabled={(directory.data?.length ?? 0) < PAGE_SIZE} onClick={() => setPage((p) => p + 1)}>Next</Button>
        </div>
      )}
    </div>
  );
}
