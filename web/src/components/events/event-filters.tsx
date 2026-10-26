"use client";

import { Search } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState, useTransition } from "react";
import { cn } from "@/lib/utils";

export type EventFilters = { when: "upcoming" | "past"; price: "all" | "free" | "paid"; q: string };

function Segmented<T extends string>({ label, value, options, onChange }: { label: string; value: T; options: { value: T; label: string }[]; onChange: (v: T) => void }) {
  return (
    <div role="group" aria-label={label} className="inline-flex rounded-full border border-line-strong bg-surface p-1">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          aria-pressed={value === o.value}
          onClick={() => onChange(o.value)}
          className={cn(
            "h-11 rounded-full px-4 text-small sm:h-9 font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink",
            value === o.value ? "bg-ink text-white" : "text-ink hover:bg-sunken",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

/** The list's controls. They live in the address (?when=&price=&q=), so a filtered list can be shared and the page draws on the server. */
export function EventFilterBar({ filters }: { filters: EventFilters }) {
  const router = useRouter();
  const pathname = usePathname();
  const [pending, start] = useTransition();
  const [q, setQ] = useState(filters.q);
  const timer = useRef<number | undefined>(undefined);

  function go(next: Partial<EventFilters>) {
    const merged = { ...filters, q, ...next };
    const params = new URLSearchParams();
    if (merged.when !== "upcoming") params.set("when", merged.when);
    if (merged.price !== "all") params.set("price", merged.price);
    if (merged.q.trim()) params.set("q", merged.q.trim());
    start(() => router.replace(params.size ? `${pathname}?${params}` : pathname, { scroll: false }));
  }

  // Typing waits for a pause before it asks the server.
  useEffect(() => () => window.clearTimeout(timer.current), []);
  function onType(value: string) {
    setQ(value);
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => go({ q: value }), 350);
  }

  return (
    <div className="mb-6 flex flex-col gap-3 lg:flex-row lg:items-center" aria-busy={pending}>
      <form
        role="search"
        className="relative lg:w-80"
        onSubmit={(e) => {
          e.preventDefault();
          window.clearTimeout(timer.current);
          go({ q });
        }}
      >
        <Search className="pointer-events-none absolute left-4 top-1/2 size-4 -translate-y-1/2 text-muted" aria-hidden />
        <input
          type="search"
          value={q}
          onChange={(e) => onType(e.target.value)}
          aria-label="Search events by title"
          placeholder="Search events"
          className="h-11 w-full rounded-full border border-line-strong bg-surface pl-11 pr-4 text-body text-ink placeholder:text-faint focus:border-brand-ink focus:outline-none focus:ring-2 focus:ring-brand-ink/20 sm:text-small"
        />
      </form>
      <div className="flex flex-wrap gap-3">
        <Segmented label="When" value={filters.when} options={[{ value: "upcoming", label: "Upcoming" }, { value: "past", label: "Past" }]} onChange={(when) => go({ when })} />
        <Segmented label="Price" value={filters.price} options={[{ value: "all", label: "All" }, { value: "free", label: "Free" }, { value: "paid", label: "Paid" }]} onChange={(price) => go({ price })} />
      </div>
    </div>
  );
}
