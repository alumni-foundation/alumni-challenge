"use client";

import { Search, SlidersHorizontal } from "lucide-react";
import { useMemo, useState } from "react";
import { PersonCard } from "@/components/member/person-card";
import { Button, EmptyState, ErrorState, Field, Input, PageHeader, Select, Skeleton, Switch } from "@/components/ui";
import { NO_FILTERS, PAGE_SIZE, useDirectorySearch, useOrgs, type DirectoryFilters } from "@/lib/api/hooks";
import { useDebounced } from "@/lib/use-debounced";

/** The API stops counting at 10,000, so that number really means "10,000 or more". */
const COUNT_CAP = 10_000;
const formatTotal = (n: number) => (n >= COUNT_CAP ? "10,000+" : n.toLocaleString("en-KE"));

export default function DirectoryPage() {
  const [form, setForm] = useState<DirectoryFilters>(NO_FILTERS);
  const [page, setPage] = useState(0);
  const [showFilters, setShowFilters] = useState(false);
  const schools = useOrgs("school");

  // Typing waits until it pauses; the dropdown and the switch apply straight away.
  const typed = useDebounced({ q: form.q, country: form.country, year: form.year, skill: form.skill }, 300);
  const filters = useMemo<DirectoryFilters>(
    () => ({ ...typed, schoolId: form.schoolId, verifiedOnly: form.verifiedOnly }),
    [typed, form.schoolId, form.verifiedOnly],
  );
  const results = useDirectorySearch(filters, page);

  const schoolName = useMemo(() => new Map((schools.data ?? []).map((s) => [s.id, s.name])), [schools.data]);
  const activeCount = [form.country, form.year, form.skill, form.schoolId].filter(Boolean).length + (form.verifiedOnly ? 1 : 0);
  const anyFilter = activeCount > 0 || form.q.trim() !== "";

  function change(patch: Partial<DirectoryFilters>) {
    setForm((f) => ({ ...f, ...patch }));
    setPage(0);
  }

  const items = results.data?.items ?? [];
  const total = results.data?.total ?? null;
  const hasNext = total !== null ? (page + 1) * PAGE_SIZE < total : items.length === PAGE_SIZE;
  const first = page * PAGE_SIZE + 1;

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader title="Directory" subtitle="Find alumni by name, school, year or what they do." />

      <div className="space-y-3">
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-muted" aria-hidden />
            <Input
              type="search"
              aria-label="Search alumni"
              placeholder="Search by name"
              value={form.q}
              onChange={(e) => change({ q: e.target.value })}
              className="pl-10"
            />
          </div>
          <Button
            variant="secondary"
            aria-expanded={showFilters}
            aria-controls="directory-filters"
            onClick={() => setShowFilters((v) => !v)}
            className="shrink-0"
          >
            <SlidersHorizontal className="size-4" aria-hidden />
            Filters
            {activeCount > 0 && <span className="rounded-full bg-brand px-1.5 text-caption font-semibold text-white">{activeCount}</span>}
          </Button>
        </div>

        {showFilters && (
          <fieldset id="directory-filters" className="grid gap-4 rounded-card border border-line bg-surface p-4 sm:grid-cols-2">
            <legend className="sr-only">Filters</legend>
            <Field label="Country" htmlFor="f-country">
              <Input id="f-country" value={form.country} onChange={(e) => change({ country: e.target.value })} />
            </Field>
            <Field label="School" htmlFor="f-school">
              <Select id="f-school" value={form.schoolId} onChange={(e) => change({ schoolId: e.target.value })}>
                <option value="">Any school</option>
                {schools.data?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </Select>
            </Field>
            <Field label="Graduation year" htmlFor="f-year">
              <Input id="f-year" type="number" inputMode="numeric" min={1950} value={form.year} onChange={(e) => change({ year: e.target.value })} />
            </Field>
            <Field label="Skill" htmlFor="f-skill">
              <Input id="f-skill" value={form.skill} onChange={(e) => change({ skill: e.target.value })} />
            </Field>
            <div className="sm:col-span-2">
              <Switch label="Verified only" hint="Show only alumni their school has confirmed." checked={form.verifiedOnly} onChange={(v) => change({ verifiedOnly: v })} />
            </div>
            <div className="sm:col-span-2">
              <Button variant="ghost" onClick={() => { setForm(NO_FILTERS); setPage(0); }} disabled={!anyFilter}>Clear filters</Button>
            </div>
          </fieldset>
        )}
      </div>

      <p className="mt-3 text-caption text-muted">
        Only people whose profiles are Public or Members only are listed. Connections-only and Private profiles never appear in search.
      </p>

      <div className="mt-4" aria-live="polite" aria-busy={results.isFetching}>
        {results.isError ? (
          <ErrorState message={results.error.message} onRetry={() => void results.refetch()} />
        ) : results.isLoading ? (
          <div className="space-y-3" role="status" aria-label="Loading results">
            {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-[82px] rounded-card" />)}
          </div>
        ) : items.length === 0 ? (
          <EmptyState title="No one matches your search." body={anyFilter ? "Try fewer filters or a different spelling." : undefined} action={anyFilter ? <Button variant="secondary" onClick={() => { setForm(NO_FILTERS); setPage(0); }}>Clear filters</Button> : undefined} />
        ) : (
          <>
            <p className="mb-3 text-small text-muted">
              {total !== null ? `${first}–${first + items.length - 1} of ${formatTotal(total)}` : `${items.length} shown`}
            </p>
            <ul className="space-y-3">
              {items.map((p) => (
                <li key={p.id}>
                  <PersonCard person={p} schoolName={p.school_id ? schoolName.get(p.school_id) : undefined} />
                </li>
              ))}
            </ul>
            <nav aria-label="Pages" className="mt-6 flex items-center justify-between gap-3">
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
