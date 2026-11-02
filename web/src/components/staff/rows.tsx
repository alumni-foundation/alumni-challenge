import Link from "next/link";
import { cn } from "@/lib/utils";

/**
 * Lists on staff pages are bar rows, the same soft rounded bars as Home and the dashboard: a row is a link when it has
 * an `href`, and lifts a little on hover. Columns stack on phones because the content is a flex row that wraps.
 */
export function RowList({ children, className, label }: { children: React.ReactNode; className?: string; label?: string }) {
  return <ul aria-label={label} className={cn("space-y-2", className)}>{children}</ul>;
}

const base =
  "flex min-h-16 gap-3 rounded-2xl border border-line bg-surface px-4 py-3 shadow-resting";
const lift =
  "transition-[transform,box-shadow] duration-200 ease-out hover:-translate-y-0.5 hover:shadow-raised focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink motion-reduce:transition-none motion-reduce:hover:translate-y-0";

export function Row({ href, children, className, stack = false }: { href?: string; children: React.ReactNode; className?: string; stack?: boolean }) {
  // Stacked rows (a person and their buttons) put the buttons under the text on phones; the rest stay on one line.
  const dir = stack ? "flex-col sm:flex-row sm:items-center" : "items-center";
  return (
    <li>
      {href ? (
        <Link href={href} className={cn(base, dir, lift, className)}>{children}</Link>
      ) : (
        <div className={cn(base, dir, className)}>{children}</div>
      )}
    </li>
  );
}
