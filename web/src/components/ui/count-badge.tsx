import { cn } from "@/lib/utils";

/** The red count (or small dot) that sits on a corner of an icon button. Decorative: the button's label carries the number. */
export function CountBadge({ count, dot = false, className }: { count?: number; dot?: boolean; className?: string }) {
  if (!dot && !count) return null;
  return (
    <span
      aria-hidden
      className={cn(
        "absolute flex items-center justify-center rounded-full bg-brand font-bold text-white ring-2 ring-canvas",
        dot ? "-right-0.5 -top-0.5 size-3" : "-right-1.5 -top-1.5 h-5 min-w-5 px-1 text-[11px] leading-none",
        className,
      )}
    >
      {dot ? null : count && count > 9 ? "9+" : count}
    </span>
  );
}
