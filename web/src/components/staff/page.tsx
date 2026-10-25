"use client";

import { ChevronLeft, ChevronRight, Search } from "lucide-react";
import Link from "next/link";
import { Button, Icon3D } from "@/components/ui";
import type { Icon3DTone } from "@/components/ui";
import { cn } from "@/lib/utils";

/**
 * The frame of every staff page: the same wide column and big serif title as the dashboard, with the
 * page's actions on the right and an optional row of number tiles under the title.
 */
export function StaffPage({
  title,
  subtitle,
  actions,
  tiles,
  children,
  className,
}: {
  title: string;
  subtitle?: React.ReactNode;
  actions?: React.ReactNode;
  tiles?: Tile[];
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("page-enter mx-auto max-w-[1280px] space-y-5", className)}>
      <div className="flex flex-wrap items-end justify-between gap-x-4 gap-y-3 pb-1">
        <div className="min-w-0">
          <h1 className="font-serif text-display font-semibold tracking-tight">{title}</h1>
          {subtitle && <div className="mt-1.5 text-small text-muted">{subtitle}</div>}
        </div>
        {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
      </div>
      {tiles && tiles.length > 0 && <StatTiles tiles={tiles} />}
      {children}
    </div>
  );
}

export type Tile = { label: string; value: string | number; href?: string; gold?: boolean; note?: string };

/** The number tiles from the dashboard, for any page: a label, a big serif figure, optionally a link. */
export function StatTiles({ tiles }: { tiles: Tile[] }) {
  const cols = tiles.length >= 4 ? "xl:grid-cols-4 md:grid-cols-2" : tiles.length === 3 ? "md:grid-cols-3" : "md:grid-cols-2";
  return (
    <ul className={cn("grid grid-cols-2 gap-3", cols)} aria-label="Key numbers">
      {tiles.map((t) => {
        const body = (
          <>
            <p className="text-small text-muted">{t.label}</p>
            <p className="mt-3 font-serif text-display font-semibold leading-none tabular-nums lining-nums">
              {typeof t.value === "number" ? t.value.toLocaleString("en-KE") : t.value}
            </p>
            {t.note && <p className="mt-2 text-caption text-muted">{t.note}</p>}
          </>
        );
        const cls = cn(
          "block h-full rounded-[1.5rem] border p-4 shadow-resting transition-[transform,box-shadow] duration-200 motion-reduce:transition-none",
          t.gold ? "border-gold/25 bg-gold-fill" : "border-line bg-surface",
          t.href && "hover:-translate-y-0.5 hover:shadow-raised motion-reduce:hover:translate-y-0",
        );
        return (
          <li key={t.label}>
            {t.href ? (
              <Link href={t.href} className={cn(cls, "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink")}>{body}</Link>
            ) : (
              <div className={cls}>{body}</div>
            )}
          </li>
        );
      })}
    </ul>
  );
}

/** A rounded card with an Icon3D title, the way the dashboard cards are drawn. */
export function Section({
  icon,
  tone = "ink",
  title,
  hint,
  aside,
  children,
  className,
  id,
}: {
  icon: React.ElementType;
  tone?: Icon3DTone;
  title: string;
  hint?: string;
  aside?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  id?: string;
}) {
  return (
    <section id={id} aria-labelledby={id ? `${id}-title` : undefined} className={cn("min-w-0 rounded-[1.75rem] border border-line bg-surface p-5 shadow-resting sm:p-6", className)}>
      <div className="mb-4 flex items-start gap-3">
        <Icon3D icon={icon} tone={tone} size="sm" />
        <div className="min-w-0 flex-1">
          <h2 id={id ? `${id}-title` : undefined} className="text-lead font-semibold">{title}</h2>
          {hint && <p className="text-small text-muted">{hint}</p>}
        </div>
        {aside}
      </div>
      {children}
    </section>
  );
}

/** A search box drawn as the same pill as the dashboard's. */
export function SearchBox({
  value,
  onChange,
  label,
  placeholder,
  className,
  id,
}: {
  value: string;
  onChange: (v: string) => void;
  label: string;
  placeholder?: string;
  className?: string;
  id?: string;
}) {
  return (
    <div role="search" className={cn("relative min-w-[11rem] flex-1", className)}>
      <Search className="pointer-events-none absolute left-4 top-1/2 size-4 -translate-y-1/2 text-muted" aria-hidden />
      <input
        id={id}
        type="search"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-label={label}
        placeholder={placeholder ?? label}
        className="h-11 w-full rounded-full border border-line-strong bg-surface pl-11 pr-4 text-small text-ink placeholder:text-faint focus:border-brand-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
      />
    </div>
  );
}

/** Previous and next, with the page number between. Pass `newer`/`older` words for logs. */
export function Pager({
  page,
  hasNext,
  onPage,
  busy,
  prevLabel = "Previous",
  nextLabel = "Next",
}: {
  page: number;
  hasNext: boolean;
  onPage: (p: number) => void;
  busy?: boolean;
  prevLabel?: string;
  nextLabel?: string;
}) {
  if (page === 0 && !hasNext) return null;
  return (
    <nav aria-label="Pages" className="flex items-center justify-between gap-3 pt-1">
      <Button variant="secondary" disabled={page === 0 || busy} onClick={() => onPage(page - 1)}>
        <ChevronLeft className="size-4" aria-hidden /> {prevLabel}
      </Button>
      <span className="text-small text-muted">Page {page + 1}</span>
      <Button variant="secondary" disabled={!hasNext || busy} onClick={() => onPage(page + 1)}>
        {nextLabel} <ChevronRight className="size-4" aria-hidden />
      </Button>
    </nav>
  );
}
