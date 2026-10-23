"use client";

import { X } from "lucide-react";
import { useState } from "react";
import { Avatar, Input, Spinner } from "@/components/ui";
import { useMemberIndex } from "@/lib/api/hooks";

export type PickedUser = { id: string; label: string };

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/**
 * Finds a person to act on. The backend has no user search, so this looks through the alumni
 * directory by name, and accepts a pasted user id for anyone the directory can't show
 * (private profiles).
 */
export function MemberPicker({
  id,
  value,
  onChange,
}: {
  id: string;
  value: PickedUser | null;
  onChange: (v: PickedUser | null) => void;
}) {
  const [q, setQ] = useState("");
  const term = q.trim();
  const isId = UUID.test(term);
  const searching = term.length >= 2 && !isId;
  const index = useMemberIndex(searching);

  if (value) {
    return (
      <div className="flex h-10 items-center justify-between gap-2 rounded-lg border border-line bg-canvas px-3 text-sm">
        <span className="truncate font-medium">{value.label}</span>
        <button
          type="button"
          onClick={() => onChange(null)}
          aria-label="Choose someone else"
          className="rounded p-1 text-muted hover:bg-surface hover:text-ink"
        >
          <X className="size-4" aria-hidden />
        </button>
      </div>
    );
  }

  const needle = term.toLowerCase();
  const matches = searching
    ? (index.data ?? []).filter((p) => p.full_name.toLowerCase().includes(needle)).slice(0, 8)
    : [];

  return (
    <div>
      <Input
        id={id}
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Search by name, or paste a user ID"
        autoComplete="off"
      />
      {isId && (
        <button
          type="button"
          onClick={() => onChange({ id: term.toLowerCase(), label: `User ${term.slice(0, 8)}…` })}
          className="mt-2 w-full rounded-lg border border-line px-3 py-2 text-left text-sm hover:bg-canvas"
        >
          Use this user ID
        </button>
      )}
      {searching && index.isLoading && <Spinner label="Looking through members" />}
      {searching && index.isError && (
        <p className="mt-2 text-sm text-brand-ink" role="alert">Couldn’t load members. Paste a user ID instead.</p>
      )}
      {searching && index.data && (
        <ul className="mt-2 overflow-hidden rounded-lg border border-line">
          {matches.map((p) => (
            <li key={p.user_id}>
              <button
                type="button"
                onClick={() => onChange({ id: p.user_id, label: p.full_name })}
                className="flex w-full items-center gap-3 px-3 py-2 text-left text-sm hover:bg-canvas"
              >
                <Avatar name={p.full_name} id={p.user_id} size={28} />
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-medium">{p.full_name}</span>
                  <span className="block truncate text-xs text-muted">
                    {[p.profession, p.graduation_year ? `Class of ${p.graduation_year}` : null].filter(Boolean).join(", ")}
                  </span>
                </span>
              </button>
            </li>
          ))}
          {matches.length === 0 && (
            <li className="px-3 py-3 text-sm text-muted">
              No match. Members with private profiles don’t appear here, so paste their user ID instead.
            </li>
          )}
        </ul>
      )}
    </div>
  );
}
