import { cn } from "@/lib/utils";

/**
 * A "bar": a soft, rounded row about 64px high with columns, that lifts a little on hover. The list view of
 * Home (people, requests, events) is made of these. On phones the columns stack inside the bar.
 */
export function BarList({ children, className }: { children: React.ReactNode; className?: string }) {
  return <ul className={cn("space-y-2", className)}>{children}</ul>;
}

export function Bar({ children, columns, className }: { children: React.ReactNode; columns: string; className?: string }) {
  return (
    <li
      className={cn(
        "rounded-2xl border border-line bg-surface px-4 py-2.5 shadow-resting transition-[transform,box-shadow] duration-200 ease-out hover:-translate-y-0.5 hover:shadow-raised motion-reduce:transition-none motion-reduce:hover:translate-y-0",
        className,
      )}
    >
      <div className={cn("grid min-h-[2.75rem] items-center gap-x-4 gap-y-1.5 md:min-h-[2.75rem]", columns)}>{children}</div>
    </li>
  );
}

/** Column titles above a list of bars. Hidden on phones, where each bar stacks its own columns. */
export function BarHeader({ columns, labels }: { columns: string; labels: string[] }) {
  return (
    <div aria-hidden className={cn("mb-2 hidden gap-x-4 px-4 text-caption font-medium uppercase tracking-wide text-muted md:grid", columns)}>
      {labels.map((l, i) => (
        <span key={i}>{l}</span>
      ))}
    </div>
  );
}
