"use client";

import { X } from "lucide-react";
import { useId, useRef, useState } from "react";
import { cn } from "@/lib/utils";

/** On/off switch with a visible label. */
export function Switch({ checked, onChange, label, hint }: {
  checked: boolean;
  onChange: (next: boolean) => void;
  label: string;
  hint?: string;
}) {
  const id = useId();
  return (
    <div className="flex items-center justify-between gap-4 py-1">
      <div className="min-w-0">
        <label htmlFor={id} className="block text-small font-medium">{label}</label>
        {hint && <p className="text-caption text-muted">{hint}</p>}
      </div>
      <button
        id={id}
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={cn(
          "relative inline-flex h-7 w-12 shrink-0 items-center rounded-full transition-colors duration-200",
          checked ? "bg-brand" : "bg-line-strong",
        )}
      >
        <span
          aria-hidden
          className={cn(
            "inline-block size-5 rounded-full bg-white shadow-raised transition-transform duration-200",
            checked ? "translate-x-6" : "translate-x-1",
          )}
        />
      </button>
    </div>
  );
}

export type TabItem<T extends string> = { value: T; label: string; count?: number };

/** Tabs with arrow-key movement. The caller renders the panel and gives it id `${value}-panel`. */
export function Tabs<T extends string>({ tabs, value, onChange, label }: {
  tabs: TabItem<T>[];
  value: T;
  onChange: (next: T) => void;
  label: string;
}) {
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});

  function onKey(e: React.KeyboardEvent, index: number) {
    const step = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
    if (!step) return;
    e.preventDefault();
    const target = tabs[(index + step + tabs.length) % tabs.length];
    onChange(target.value);
    refs.current[target.value]?.focus();
  }

  return (
    <div role="tablist" aria-label={label} className="-mx-4 flex gap-1 overflow-x-auto border-b border-line px-4 sm:mx-0 sm:px-0">
      {tabs.map((t, i) => {
        const active = t.value === value;
        return (
          <button
            key={t.value}
            ref={(el) => { refs.current[t.value] = el; }}
            type="button"
            role="tab"
            id={`${t.value}-tab`}
            aria-selected={active}
            aria-controls={`${t.value}-panel`}
            tabIndex={active ? 0 : -1}
            onClick={() => onChange(t.value)}
            onKeyDown={(e) => onKey(e, i)}
            className={cn(
              "relative inline-flex h-11 shrink-0 items-center gap-2 px-4 text-small font-medium transition-colors",
              active ? "text-ink" : "text-muted hover:text-ink",
            )}
          >
            {t.label}
            {t.count !== undefined && t.count > 0 && (
              <span className="rounded-full bg-brand px-1.5 text-caption font-semibold text-white">{t.count}</span>
            )}
            {active && <span className="absolute inset-x-3 -bottom-px h-0.5 rounded-full bg-brand-ink" aria-hidden />}
          </button>
        );
      })}
    </div>
  );
}

export type RadioOption<T extends string> = { value: T; label: string; help: string };

/** A group of choices where each one explains itself in a sentence. Arrow keys move between them. */
export function RadioCards<T extends string>({ legend, name, options, value, onChange }: {
  legend: string;
  name: string;
  options: RadioOption<T>[];
  value: T;
  onChange: (next: T) => void;
}) {
  return (
    <fieldset className="space-y-2">
      <legend className="mb-1 text-small font-medium">{legend}</legend>
      {options.map((o) => {
        const checked = o.value === value;
        return (
          <label
            key={o.value}
            className={cn(
              "flex min-h-14 cursor-pointer items-start gap-3 rounded-control border px-4 py-3 transition-colors",
              checked ? "border-brand-ink bg-brand-soft" : "border-line-strong bg-surface hover:bg-sunken",
              "has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-brand-ink",
            )}
          >
            <input
              type="radio"
              name={name}
              value={o.value}
              checked={checked}
              onChange={() => onChange(o.value)}
              className="mt-1 size-4 shrink-0 accent-brand"
            />
            <span>
              <span className="block text-small font-medium">{o.label}</span>
              <span className="block text-caption text-muted">{o.help}</span>
            </span>
          </label>
        );
      })}
    </fieldset>
  );
}

const TAG_MAX_LENGTH = 30;
const TAG_MAX_COUNT = 20;

/** Free-text tags: type, then press Enter or comma (or Add). Each tag has a Remove button. */
export function TagInput({ id, label, value, onChange, hint }: {
  id: string;
  label: string;
  value: string[];
  onChange: (next: string[]) => void;
  hint?: string;
}) {
  const [draft, setDraft] = useState("");
  const full = value.length >= TAG_MAX_COUNT;

  function commit(raw: string) {
    const parts = raw.split(",").map((t) => t.trim()).filter(Boolean);
    const next = [...value];
    for (const t of parts) {
      const tag = t.slice(0, TAG_MAX_LENGTH);
      if (next.length < TAG_MAX_COUNT && !next.some((x) => x.toLowerCase() === tag.toLowerCase())) next.push(tag);
    }
    onChange(next);
    setDraft("");
  }

  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="block text-small font-medium">{label}</label>
      {value.length > 0 && (
        <ul className="flex flex-wrap gap-2" aria-label={`${label} added`}>
          {value.map((t) => (
            <li key={t} className="inline-flex items-center gap-1 rounded-full border border-line bg-sunken py-0.5 pl-3 pr-1 text-small">
              {t}
              <button
                type="button"
                onClick={() => onChange(value.filter((x) => x !== t))}
                aria-label={`Remove ${t}`}
                className="inline-flex size-8 items-center justify-center rounded-full text-muted hover:bg-line hover:text-ink"
              >
                <X className="size-4" aria-hidden />
              </button>
            </li>
          ))}
        </ul>
      )}
      <div className="flex gap-2">
        <input
          id={id}
          value={draft}
          disabled={full}
          maxLength={TAG_MAX_LENGTH * 4}
          onChange={(e) => (e.target.value.includes(",") ? commit(e.target.value) : setDraft(e.target.value))}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              if (draft.trim()) commit(draft);
            }
          }}
          aria-describedby={`${id}-hint`}
          className="h-11 w-full rounded-control border border-line-strong bg-surface px-3.5 text-body text-ink placeholder:text-faint focus:border-brand-ink focus:outline-none focus:ring-2 focus:ring-brand-ink/20 disabled:bg-sunken sm:text-small"
        />
        <button
          type="button"
          onClick={() => draft.trim() && commit(draft)}
          disabled={full || !draft.trim()}
          className="h-11 shrink-0 rounded-control border border-line-strong bg-surface px-4 text-small font-medium hover:bg-sunken disabled:opacity-50"
        >
          Add
        </button>
      </div>
      <p id={`${id}-hint`} className="text-caption text-muted">
        {full ? `You can add up to ${TAG_MAX_COUNT}.` : hint ?? "Type one and press Enter."}
      </p>
    </div>
  );
}
