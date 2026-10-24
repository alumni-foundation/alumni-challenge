"use client";

import { Clock } from "lucide-react";
import type { EventSlot } from "@/lib/api/types";
import { rangeText, seatsText } from "@/lib/events";
import { cn } from "@/lib/utils";

const isFull = (s: EventSlot) => s.availability === "full" || (s.spots_left !== null && s.spots_left <= 0);

/**
 * The sessions (tee times, shifts, evenings) as selectable bars: the time, its name, and the seats left, or "Full".
 * A full session cannot be chosen. With `readOnly` it only lists them, for people who are not signed in.
 */
export function SlotPicker({ slots, value, onChange, error, readOnly = false }: { slots: EventSlot[]; value?: string; onChange?: (id: string) => void; error?: string; readOnly?: boolean }) {
  const sorted = [...slots].sort((a, b) => a.position - b.position || a.starts_at.localeCompare(b.starts_at));
  return (
    <fieldset id="slot-group" tabIndex={-1} className="min-w-0 space-y-2.5 focus:outline-none" aria-describedby={error ? "slot-msg" : undefined}>
      <legend className="mb-1 text-small font-semibold text-ink">{sorted.length > 1 ? "Choose a session" : "When"}</legend>
      <ul className="space-y-2">
        {sorted.map((s) => {
          const full = isFull(s);
          const seats = seatsText(s.spots_left);
          const selected = value === s.id;
          const body = (
            <>
              <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-gold-soft text-gold" aria-hidden><Clock className="size-5" /></span>
              <span className="min-w-0 flex-1">
                <span className="block whitespace-nowrap font-semibold">{rangeText(s.starts_at, s.ends_at)}</span>
                {s.label && <span className="block text-small text-muted">{s.label}</span>}
              </span>
              {seats && (
                <span className="basis-full pl-[3.25rem] sm:basis-auto sm:pl-0">
                  <span className={cn("inline-block shrink-0 rounded-full px-3 py-1 text-small font-semibold", full ? "bg-sunken text-ink" : s.availability === "few_left" ? "bg-warn-soft text-warn" : "bg-sunken text-ink")}>{seats}</span>
                </span>
              )}
            </>
          );
          return (
            <li key={s.id}>
              {readOnly ? (
                <div className="flex min-h-16 flex-wrap items-center gap-x-3 gap-y-2 rounded-2xl border border-line bg-surface px-4 py-2.5">{body}</div>
              ) : (
                <label className={cn("relative flex min-h-16 flex-wrap items-center gap-x-3 gap-y-2 rounded-2xl border bg-surface px-4 py-2.5 transition-[transform,box-shadow,border-color] duration-200", full ? "cursor-not-allowed opacity-60" : "cursor-pointer hover:-translate-y-0.5 hover:shadow-raised motion-reduce:hover:translate-y-0", selected ? "border-ink shadow-raised ring-1 ring-ink" : "border-line")}>
                  <input type="radio" name="slot" value={s.id} checked={selected} disabled={full} onChange={() => onChange?.(s.id)} className="peer sr-only" />
                  <span aria-hidden className="pointer-events-none absolute inset-0 rounded-2xl peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-ink" />
                  {body}
                </label>
              )}
            </li>
          );
        })}
      </ul>
      {error && <p id="slot-msg" className="text-small text-brand-ink" role="alert">{error}</p>}
    </fieldset>
  );
}
