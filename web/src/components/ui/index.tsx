"use client";

import { AlertCircle, BadgeCheck, CheckCircle2, Eye, EyeOff, Info, Loader2 } from "lucide-react";
import Link from "next/link";
import { cloneElement, isValidElement, useState } from "react";
import { cn, initials, toneFor } from "@/lib/utils";

export { ConfirmDialog, Dialog, ReasonDialog } from "./dialog";
export { ToastProvider, useToast } from "./toast";
export { RadioCards, Switch, Tabs, TagInput } from "./controls";
export { Icon3D } from "./icon3d";
export type { Icon3DSize, Icon3DTone } from "./icon3d";

/* ---- Buttons ---------------------------------------------------------------------------- */

type ButtonSize = "sm" | "md";
type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "dark" | "secondary" | "ghost" | "danger";
  size?: ButtonSize;
  loading?: boolean;
};
const VARIANTS = {
  primary: "bg-brand text-white shadow-raised hover:bg-brand-dark",
  // The sign-in pages' button: the ink pill from the landing page.
  dark: "bg-ink text-white shadow-raised hover:bg-black",
  // Quiet: no fill to compete with the primary, just a fine line.
  secondary: "border border-line-strong bg-transparent text-ink hover:bg-sunken",
  ghost: "text-muted hover:bg-sunken hover:text-ink",
  danger: "border border-brand/40 bg-surface text-brand-ink hover:bg-brand-soft",
};
// 44px tall on phones is the minimum comfortable touch target; "sm" is for dense desktop rows.
const SIZES: Record<ButtonSize, string> = {
  md: "h-11 px-6 text-small",
  sm: "h-11 px-4 text-small sm:h-9 sm:px-3",
};
const buttonBase =
  "inline-flex items-center justify-center gap-2 rounded-full font-medium transition-[background-color,box-shadow,transform] duration-150 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-60";

export function Button({ variant = "primary", size = "md", loading, className, children, disabled, type = "button", ...rest }: ButtonProps) {
  return (
    <button
      type={type}
      {...rest}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cn(buttonBase, SIZES[size], VARIANTS[variant], className)}
    >
      {loading && <Loader2 className="size-4 animate-spin" aria-hidden />}
      {children}
    </button>
  );
}

export function LinkButton({ href, variant = "primary", size = "md", className, children, prefetch }: {
  href: string; variant?: ButtonProps["variant"]; size?: ButtonSize; className?: string; children: React.ReactNode; prefetch?: boolean;
}) {
  return (
    <Link href={href} prefetch={prefetch} className={cn(buttonBase, SIZES[size], VARIANTS[variant ?? "primary"], className)}>
      {children}
    </Link>
  );
}

/* ---- Forms ------------------------------------------------------------------------------ */

// 16px text on phones stops iOS from zooming into the field when it is focused.
const fieldClass =
  "w-full rounded-control border border-line-strong bg-surface px-3.5 text-body text-ink placeholder:text-faint transition-colors focus:border-brand-ink focus:outline-none focus:ring-2 focus:ring-brand-ink/20 disabled:bg-sunken disabled:text-faint aria-[invalid=true]:border-brand-ink sm:text-small";
export const Input = (p: React.ComponentProps<"input">) => (
  <input {...p} className={cn(fieldClass, "h-11", p.className)} />
);

/** A password field with a show/hide button. The button is a real button: Tab reaches it, Space or Enter toggles it, and a screen reader hears its state. */
export function PasswordInput(p: React.ComponentProps<"input">) {
  const [shown, setShown] = useState(false);
  return (
    <div className="relative">
      <Input {...p} type={shown ? "text" : "password"} className={cn("pr-12", p.className)} />
      <button
        type="button"
        onClick={() => setShown((v) => !v)}
        aria-label={shown ? "Hide password" : "Show password"}
        aria-pressed={shown}
        className="absolute right-1 top-1/2 grid size-10 -translate-y-1/2 place-items-center rounded-full text-muted transition-colors hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-0 focus-visible:outline-brand-ink"
      >
        {shown ? <EyeOff className="size-[18px]" aria-hidden /> : <Eye className="size-[18px]" aria-hidden />}
      </button>
    </div>
  );
}
export const Textarea = (p: React.TextareaHTMLAttributes<HTMLTextAreaElement>) => (
  <textarea {...p} className={cn(fieldClass, "min-h-28 py-2.5", p.className)} />
);
export const Select = (p: React.SelectHTMLAttributes<HTMLSelectElement>) => (
  <select {...p} className={cn(fieldClass, "h-11", p.className)} />
);

/** A labelled field. The single child gets the error and hint wired up for screen readers. */
export function Field({ label, error, hint, htmlFor, children }: {
  label: string; error?: string; hint?: string; htmlFor: string; children: React.ReactElement<{ "aria-describedby"?: string; "aria-invalid"?: boolean }>;
}) {
  const msgId = `${htmlFor}-msg`;
  const control = isValidElement(children)
    ? cloneElement(children, {
        "aria-describedby": error || hint ? msgId : undefined,
        "aria-invalid": error ? true : undefined,
      })
    : children;
  return (
    <div className="space-y-1.5">
      <label htmlFor={htmlFor} className="block text-small font-medium text-ink">{label}</label>
      {control}
      {error ? (
        <p id={msgId} className="text-small text-brand-ink" role="alert">{error}</p>
      ) : hint ? (
        <p id={msgId} className="text-caption text-muted">{hint}</p>
      ) : null}
    </div>
  );
}

/* ---- Surfaces --------------------------------------------------------------------------- */

type Elevation = "resting" | "raised" | "lifted";
const ELEVATION: Record<Elevation, string> = {
  resting: "shadow-resting",
  raised: "shadow-raised",
  lifted: "shadow-lifted",
};
export function Card({
  className,
  elevation = "resting",
  interactive = false,
  ...p
}: React.HTMLAttributes<HTMLDivElement> & { elevation?: Elevation; interactive?: boolean }) {
  return (
    <div
      {...p}
      className={cn(
        "rounded-card border border-line bg-surface p-5 sm:p-6",
        ELEVATION[elevation],
        interactive && "transition-[box-shadow,border-color] duration-200 hover:border-line-strong hover:shadow-lifted",
        className,
      )}
    />
  );
}

const CHIP_TONES = {
  brand: "bg-brand-soft text-brand-ink",
  gold: "bg-gold-soft text-gold",
  blue: "bg-verified-soft text-verified",
  green: "bg-ok-soft text-ok",
  ink: "bg-sunken text-ink",
} as const;
/** A tinted icon container. It stops a row of cards from looking identical. */
export function IconChip({ icon: Icon, tone = "brand", size = 40 }: {
  icon: React.ElementType; tone?: keyof typeof CHIP_TONES; size?: number;
}) {
  return (
    <span
      className={cn("inline-flex shrink-0 items-center justify-center rounded-xl", CHIP_TONES[tone])}
      style={{ width: size, height: size }}
    >
      <Icon className="size-[45%]" aria-hidden />
    </span>
  );
}

export function Badge({ tone = "neutral", children }: { tone?: "neutral" | "ok" | "warn" | "brand" | "gold" | "blue"; children: React.ReactNode }) {
  const tones = {
    neutral: "bg-sunken text-muted",
    ok: "bg-ok-soft text-ok",
    warn: "bg-warn-soft text-warn",
    brand: "bg-brand-soft text-brand-ink",
    gold: "bg-gold-soft text-gold",
    blue: "bg-verified-soft text-verified",
  };
  return <span className={cn("inline-flex items-center rounded-full px-2.5 py-0.5 text-caption font-medium ring-1 ring-inset ring-current/10", tones[tone])}>{children}</span>;
}

export const VerifiedMark = () => <BadgeCheck className="inline size-4 text-verified" aria-label="Verified alumnus" />;

export const Chip = ({ children }: { children: React.ReactNode }) => (
  <span className="rounded-full border border-line bg-sunken px-2.5 py-1 text-caption font-medium text-ink">{children}</span>
);

/** A plain circular icon button, quiet until hovered. */
export function IconButton({ icon: Icon, label, soon = false, dot = false, onClick }: {
  icon: React.ElementType; label: string; soon?: boolean; dot?: boolean; onClick?: () => void;
}) {
  return (
    <button
      type="button"
      title={soon ? `${label} (coming soon)` : label}
      aria-label={soon ? `${label}, coming soon` : label}
      aria-disabled={soon || undefined}
      onClick={soon ? undefined : onClick}
      className={cn(
        "relative inline-flex size-11 items-center justify-center rounded-full bg-sunken text-ink transition-colors",
        soon ? "cursor-default opacity-50" : "hover:bg-line",
      )}
    >
      <Icon className="size-[18px]" aria-hidden />
      {dot && <span className="absolute right-2.5 top-2.5 size-2 rounded-full bg-brand" aria-hidden />}
    </button>
  );
}

export function Avatar({ name, id, size = 40, src }: { name: string; id: string; size?: number; src?: string | null }) {
  // Photo links expire and uploads can fail, so a photo that won't load falls back to initials.
  const [failed, setFailed] = useState<string | null>(null);
  if (src && src !== failed) {
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={src} alt="" width={size} height={size} className="shrink-0 rounded-full object-cover ring-2 ring-surface" style={{ width: size, height: size }} onError={() => setFailed(src)} />;
  }
  return (
    <span
      aria-hidden
      className="inline-flex shrink-0 items-center justify-center rounded-full font-semibold text-white ring-2 ring-surface"
      style={{ width: size, height: size, background: toneFor(id), fontSize: size * 0.38 }}
    >
      {initials(name)}
    </span>
  );
}

/* ---- Status and feedback ---------------------------------------------------------------- */

export const Spinner = ({ label = "Loading" }: { label?: string }) => (
  <div className="flex items-center justify-center gap-2 py-16 text-small text-muted" role="status">
    <Loader2 className="size-4 animate-spin" aria-hidden /> {label}…
  </div>
);

/** A grey placeholder shape for content that is still loading. */
export const Skeleton = ({ className }: { className?: string }) => (
  <div className={cn("animate-pulse rounded-control bg-sunken", className)} aria-hidden />
);

export function Alert({ children, tone = "error" }: { children: React.ReactNode; tone?: "error" | "info" | "ok" | "warn" }) {
  const tones = {
    error: "border-brand/30 bg-brand-soft text-ink",
    warn: "border-warn/30 bg-warn-soft text-ink",
    info: "border-line bg-sunken text-ink",
    ok: "border-ok/30 bg-ok-soft text-ink",
  };
  const icons = { error: AlertCircle, warn: AlertCircle, info: Info, ok: CheckCircle2 };
  const iconTone = { error: "text-brand-ink", warn: "text-warn", info: "text-muted", ok: "text-ok" };
  const Icon = icons[tone];
  return (
    <div role={tone === "error" ? "alert" : "status"} className={cn("flex gap-2.5 rounded-xl border px-3.5 py-3 text-small", tones[tone])}>
      <Icon className={cn("mt-0.5 size-4 shrink-0", iconTone[tone])} aria-hidden />
      <div className="min-w-0">{children}</div>
    </div>
  );
}

export function EmptyState({ title, body, action }: { title: string; body?: string; action?: React.ReactNode }) {
  return (
    <Card className="py-12 text-center">
      <p className="text-lead font-semibold">{title}</p>
      {body && <p className="mx-auto mt-1 max-w-sm text-small text-muted">{body}</p>}
      {action && <div className="mt-4 flex justify-center">{action}</div>}
    </Card>
  );
}

/** What a list shows when its request failed: say so plainly and offer another go. */
export function ErrorState({ message, onRetry }: { message?: string; onRetry?: () => void }) {
  return (
    <Card className="space-y-3 py-8 text-center">
      <p className="font-semibold">We couldn’t load this.</p>
      <p className="mx-auto max-w-sm text-small text-muted">{message ?? "Check your connection and try again."}</p>
      {onRetry && (
        <div className="flex justify-center">
          <Button variant="secondary" onClick={onRetry}>Try again</Button>
        </div>
      )}
    </Card>
  );
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: React.ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div className="min-w-0">
        <h1 className="text-title tracking-tight">{title}</h1>
        {subtitle && <p className="mt-1 text-small text-muted">{subtitle}</p>}
      </div>
      {actions}
    </div>
  );
}

/** A single number and label: the building block for a stats strip. */
export function StatTile({ label, value, tone = "ink" }: { label: string; value: string | number; tone?: keyof typeof CHIP_TONES }) {
  return (
    <div className="flex-1 rounded-card border border-line bg-surface px-5 py-4 shadow-resting">
      <p className={cn("text-title font-bold tabular-nums", tone === "brand" && "text-brand-ink", tone === "gold" && "text-gold")}>
        {value}
      </p>
      <p className="mt-0.5 text-small text-muted">{label}</p>
    </div>
  );
}
