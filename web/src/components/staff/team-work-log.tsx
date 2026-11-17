"use client";

import { Check, Circle } from "lucide-react";
import { useState } from "react";
import { Avatar, Button, Card, EmptyState, ErrorState, Field, Input, Select, Skeleton } from "@/components/ui";
import { friendlyError } from "@/lib/api/messages";
import { useTeamWorkLog, useWorkLogPeople, type TeamLogFilters } from "@/lib/api/hooks";
import { formatCompleted, formatDay, groupByPerson } from "@/lib/work-log";

/** Everyone's work log for a super admin. Read only: there is no way to change a line from here. */
export function TeamWorkLog() {
  const [filters, setFilters] = useState<TeamLogFilters>({ userId: "", from: "", to: "" });
  const people = useWorkLogPeople(true);
  const backwards = filters.from !== "" && filters.to !== "" && filters.from > filters.to;
  const log = useTeamWorkLog(filters, !backwards);
  const entries = log.data?.pages.flat() ?? [];
  const filtered = filters.userId !== "" || filters.from !== "" || filters.to !== "";

  return (
    <div className="max-w-4xl">
      <Card large className="mb-6">
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Person" htmlFor="wl-person">
            <Select id="wl-person" value={filters.userId} onChange={(e) => setFilters({ ...filters, userId: e.target.value })}>
              <option value="">Everyone</option>
              {(people.data ?? []).map((p) => <option key={p.user_id} value={p.user_id}>{p.name}</option>)}
            </Select>
          </Field>
          <Field label="From" htmlFor="wl-from">
            <Input id="wl-from" type="date" value={filters.from} max={filters.to || undefined} onChange={(e) => setFilters({ ...filters, from: e.target.value })} />
          </Field>
          <Field label="To" htmlFor="wl-to" error={backwards ? "The end date is before the start date." : undefined}>
            <Input id="wl-to" type="date" value={filters.to} min={filters.from || undefined} onChange={(e) => setFilters({ ...filters, to: e.target.value })} />
          </Field>
        </div>
        {filtered && (
          <div className="mt-3">
            <Button variant="ghost" size="sm" onClick={() => setFilters({ userId: "", from: "", to: "" })}>Clear filters</Button>
          </div>
        )}
      </Card>

      {backwards ? null : log.isLoading ? (
        <Skeleton className="h-48 rounded-card" />
      ) : log.isError ? (
        <ErrorState message={friendlyError(log.error)} onRetry={() => void log.refetch()} />
      ) : entries.length === 0 ? (
        <EmptyState
          title={filtered ? "Nothing matches these filters" : "No one has written anything yet"}
          body={filtered ? "Try another person or a wider range of dates." : "When admins and moderators add lines to their work log, you will see them here."}
        />
      ) : (
        <div className="space-y-6">
          {groupByPerson(entries).map((person) => (
            <Card large key={person.userId} className="space-y-5">
              <div className="flex items-center gap-3">
                <Avatar name={person.name} id={person.userId} size={40} />
                <div className="min-w-0">
                  <h2 className="truncate text-lead font-semibold">{person.name}</h2>
                  {person.name !== person.email && <p className="truncate text-caption text-muted">{person.email}</p>}
                </div>
              </div>
              {person.days.map((day) => (
                <section key={day.date} aria-label={formatDay(day.date)}>
                  <h3 className="mb-2 text-small font-medium text-muted">{formatDay(day.date)}</h3>
                  <ul className="space-y-1.5">
                    {day.entries.map((e) => (
                      <li key={e.id} className="flex items-start gap-3 rounded-xl bg-sunken/60 px-3 py-2">
                        {e.kind === "done" ? (
                          <Check className="mt-0.5 size-4 shrink-0 text-ok" aria-label="Done" role="img" />
                        ) : (
                          <Circle className="mt-0.5 size-4 shrink-0 text-faint" aria-label="Planned" role="img" />
                        )}
                        <div className="min-w-0">
                          <p className="break-words text-small">{e.text}</p>
                          {e.kind === "done" && e.completed_at && (
                            <p className="text-caption text-muted">Done at {formatCompleted(e.completed_at, e.entry_date)}</p>
                          )}
                        </div>
                      </li>
                    ))}
                  </ul>
                </section>
              ))}
            </Card>
          ))}
          {log.hasNextPage && (
            <div className="flex justify-center">
              <Button variant="secondary" loading={log.isFetchingNextPage} onClick={() => void log.fetchNextPage()}>Show more</Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
