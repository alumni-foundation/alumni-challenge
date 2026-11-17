"use client";

import { Check, Pencil, Trash2 } from "lucide-react";
import { useState } from "react";
import { Alert, Button, Card, ConfirmDialog, EmptyState, ErrorState, Input, Skeleton, Tabs, useToast } from "@/components/ui";
import { friendlyError } from "@/lib/api/messages";
import {
  useAddWorkLog, useCompleteWorkLog, useDeleteWorkLog, useEditWorkLog, useMyWorkLog,
} from "@/lib/api/hooks";
import type { WorkLogEntry, WorkLogKind } from "@/lib/api/types";
import { cn } from "@/lib/utils";
import { formatCompleted, formatDay, groupByDay, isTodayGroup } from "@/lib/work-log";

const MAX = 500;
const KINDS: { value: WorkLogKind; label: string }[] = [
  { value: "planned", label: "Planned" },
  { value: "done", label: "Done" },
];

// Small icon buttons: 44px to tap on phones, 36px with a mouse. The press shrink is the same quick feedback the pills have.
const iconButton =
  "inline-flex size-11 items-center justify-center rounded-full text-muted transition-[background-color,color,transform] duration-150 hover:bg-sunken hover:text-ink active:scale-[0.96] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink sm:size-9 motion-reduce:transition-none";

function AddForm() {
  const add = useAddWorkLog();
  const [text, setText] = useState("");
  const [kind, setKind] = useState<WorkLogKind>("planned");
  const clean = text.trim();

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!clean || add.isPending) return;
    add.mutate({ kind, text: clean }, { onSuccess: () => setText("") });
  }

  return (
    <Card large className="mb-6">
      <form onSubmit={submit} className="space-y-3">
        <label htmlFor="work-log-text" className="block text-small font-medium">What are you working on?</label>
        <div className="flex flex-col gap-3 sm:flex-row">
          <Input
            id="work-log-text"
            value={text}
            maxLength={MAX}
            onChange={(e) => setText(e.target.value)}
            placeholder={kind === "planned" ? "Something you plan to do today" : "Something you finished"}
            autoComplete="off"
            className="min-w-0 sm:flex-1"
          />
          <Button type="submit" variant="dark" loading={add.isPending} disabled={!clean}>Add</Button>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Tabs tabs={KINDS} value={kind} onChange={setKind} label="This line is" pills />
          {text.length > MAX - 50 && <p className="text-caption text-muted">{MAX - text.length} characters left</p>}
        </div>
        {add.isError && <Alert>{friendlyError(add.error)}</Alert>}
      </form>
    </Card>
  );
}

function EntryRow({ entry }: { entry: WorkLogEntry }) {
  const toast = useToast();
  const complete = useCompleteWorkLog();
  const edit = useEditWorkLog();
  const remove = useDeleteWorkLog();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(entry.text);
  const [confirming, setConfirming] = useState(false);
  const done = entry.kind === "done";

  function save(e: React.FormEvent) {
    e.preventDefault();
    const next = draft.trim();
    if (!next || edit.isPending) return;
    if (next === entry.text) return setEditing(false);
    edit.mutate({ id: entry.id, text: next }, { onSuccess: () => setEditing(false) });
  }

  return (
    <li className="flex min-h-14 items-start gap-3 rounded-2xl border border-line bg-surface px-3 py-2 shadow-resting sm:px-4">
      <div className="flex size-11 shrink-0 items-center justify-center sm:size-9">
        {done ? (
          <span className="flex size-6 items-center justify-center rounded-full bg-ok-soft text-ok" role="img" aria-label="Done">
            <Check className="size-4" aria-hidden />
          </span>
        ) : (
          <input
            type="checkbox"
            checked={false}
            disabled={complete.isPending}
            onChange={() => complete.mutate(entry.id, { onError: (err) => toast(friendlyError(err), "info") })}
            aria-label={`Mark as done: ${entry.text}`}
            className="size-5 cursor-pointer accent-brand focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
          />
        )}
      </div>

      <div className="min-w-0 flex-1 py-2.5 sm:py-1.5">
        {editing ? (
          <form onSubmit={save} className="space-y-2">
            <Input value={draft} maxLength={MAX} onChange={(e) => setDraft(e.target.value)} aria-label="Edit this line" autoFocus />
            {edit.isError && <Alert>{friendlyError(edit.error)}</Alert>}
            <div className="flex gap-2">
              <Button type="submit" variant="dark" size="sm" loading={edit.isPending} disabled={!draft.trim()}>Save</Button>
              <Button variant="ghost" size="sm" onClick={() => { setEditing(false); setDraft(entry.text); edit.reset(); }}>Cancel</Button>
            </div>
          </form>
        ) : (
          <>
            <p className={cn("break-words text-small", done && "text-muted")}>{entry.text}</p>
            {done && entry.completed_at && (
              <p className="text-caption text-muted">Done at {formatCompleted(entry.completed_at, entry.entry_date)}</p>
            )}
          </>
        )}
      </div>

      {entry.editable && !editing && (
        <div className="flex shrink-0 items-center">
          <button type="button" className={iconButton} aria-label={`Edit: ${entry.text}`} onClick={() => { setDraft(entry.text); setEditing(true); }}>
            <Pencil className="size-4" aria-hidden />
          </button>
          <button type="button" className={iconButton} aria-label={`Delete: ${entry.text}`} onClick={() => setConfirming(true)}>
            <Trash2 className="size-4" aria-hidden />
          </button>
        </div>
      )}

      <ConfirmDialog
        open={confirming}
        title="Delete this line?"
        body="It will be removed from your work log. You can’t undo this."
        confirmLabel="Delete"
        danger
        onConfirm={() => remove.mutateAsync(entry.id)}
        onClose={() => setConfirming(false)}
      />
    </li>
  );
}

/** My work log: add a line, tick planned lines off, and look back by day. Edit and delete only on today's lines. */
export function MyWorkLog() {
  const log = useMyWorkLog();

  return (
    <div className="max-w-3xl">
      <AddForm />
      {log.isLoading ? (
        <Skeleton className="h-40 rounded-card" />
      ) : log.isError ? (
        <ErrorState message={friendlyError(log.error)} onRetry={() => void log.refetch()} />
      ) : (log.data ?? []).length === 0 ? (
        <EmptyState title="Nothing here yet" body="Add what you plan to do today, or what you have already finished. It will show up here, one day at a time." />
      ) : (
        <div className="space-y-8">
          {groupByDay(log.data ?? []).map((group) => (
            <section key={group.date} aria-labelledby={`day-${group.date}`}>
              <h2 id={`day-${group.date}`} className="mb-2 text-lead font-semibold">
                {isTodayGroup(group) && <span className="mr-2 rounded-full bg-gold-soft px-2.5 py-0.5 align-middle text-caption font-medium text-gold">Today</span>}
                {formatDay(group.date)}
              </h2>
              <ul className="space-y-2">
                {group.entries.map((e) => <EntryRow key={e.id} entry={e} />)}
              </ul>
            </section>
          ))}
          <p className="text-caption text-muted">Showing the last 60 days. Lines from earlier days can’t be edited or deleted.</p>
        </div>
      )}
    </div>
  );
}
