"use client";

import { AlertCircle, BadgeCheck, Loader2 } from "lucide-react";
import Link from "next/link";
import { cn, initials, toneFor } from "@/lib/utils";

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md";
  loading?: boolean;
};
const VARIANTS = {
  primary: "bg-brand text-white hover:bg-brand-dark",
  secondary: "bg-white text-ink border border-line hover:bg-canvas",
  ghost: "text-muted hover:bg-canvas hover:text-ink",
  danger: "bg-white text-brand border border-brand/30 hover:bg-brand-soft",
};
export function Button({ variant = "primary", size = "md", loading, className, children, disabled, ...rest }: ButtonProps) {
  return (
    <button
      {...rest}
      disabled={disabled || loading}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-60",
        size === "sm" ? "h-8 px-3 text-sm" : "h-10 px-4 text-sm",
        VARIANTS[variant],
        className,
      )}
    >
      {loading && <Loader2 className="size-4 animate-spin" aria-hidden />}
      {children}
    </button>
  );
}

export function LinkButton({ href, variant = "primary", size = "md", className, children }: {
  href: string; variant?: ButtonProps["variant"]; size?: "sm" | "md"; className?: string; children: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-colors",
        size === "sm" ? "h-8 px-3 text-sm" : "h-10 px-4 text-sm",
        VARIANTS[variant ?? "primary"],
        className,
      )}
    >
      {children}
    </Link>
  );
}

const fieldClass =
  "w-full rounded-lg border border-line bg-white px-3 text-sm text-ink placeholder:text-muted/70 focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/20 disabled:bg-canvas";
export const Input = (p: React.InputHTMLAttributes<HTMLInputElement>) => (
  <input {...p} className={cn(fieldClass, "h-10", p.className)} />
);
export const Textarea = (p: React.TextareaHTMLAttributes<HTMLTextAreaElement>) => (
  <textarea {...p} className={cn(fieldClass, "min-h-24 py-2", p.className)} />
);
export const Select = (p: React.SelectHTMLAttributes<HTMLSelectElement>) => (
  <select {...p} className={cn(fieldClass, "h-10", p.className)} />
);

export function Field({ label, error, hint, htmlFor, children }: {
  label: string; error?: string; hint?: string; htmlFor: string; children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={htmlFor} className="text-sm font-medium text-ink">{label}</label>
      {children}
      {error ? <p className="text-sm text-brand" role="alert">{error}</p> : hint ? <p className="text-xs text-muted">{hint}</p> : null}
    </div>
  );
}

export const Card = ({ className, ...p }: React.HTMLAttributes<HTMLDivElement>) => (
  <div {...p} className={cn("rounded-2xl border border-line bg-white p-5 shadow-[0_1px_2px_rgba(20,20,30,0.04)]", className)} />
);

export function Badge({ tone = "neutral", children }: { tone?: "neutral" | "ok" | "warn" | "brand"; children: React.ReactNode }) {
  const tones = { neutral: "bg-canvas text-muted", ok: "bg-green-50 text-ok", warn: "bg-amber-50 text-warn", brand: "bg-brand-soft text-brand" };
  return <span className={cn("inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium", tones[tone])}>{children}</span>;
}

export const VerifiedMark = () => <BadgeCheck className="inline size-4 text-verified" aria-label="Verified alumnus" />;

export function Avatar({ name, id, size = 40 }: { name: string; id: string; size?: number }) {
  return (
    <span
      aria-hidden
      className="inline-flex shrink-0 items-center justify-center rounded-full font-semibold text-white"
      style={{ width: size, height: size, background: toneFor(id), fontSize: size * 0.38 }}
    >
      {initials(name)}
    </span>
  );
}

export const Spinner = ({ label = "Loading" }: { label?: string }) => (
  <div className="flex items-center justify-center gap-2 py-16 text-sm text-muted" role="status">
    <Loader2 className="size-4 animate-spin" aria-hidden /> {label}…
  </div>
);

export function Alert({ children, tone = "error" }: { children: React.ReactNode; tone?: "error" | "info" | "ok" }) {
  const tones = { error: "border-brand/30 bg-brand-soft text-brand-dark", info: "border-line bg-canvas text-ink", ok: "border-green-200 bg-green-50 text-ok" };
  return (
    <div role={tone === "error" ? "alert" : "status"} className={cn("flex gap-2 rounded-lg border px-3 py-2 text-sm", tones[tone])}>
      <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden />
      <div>{children}</div>
    </div>
  );
}

export function EmptyState({ title, body, action }: { title: string; body?: string; action?: React.ReactNode }) {
  return (
    <Card className="py-12 text-center">
      <p className="font-semibold">{title}</p>
      {body && <p className="mx-auto mt-1 max-w-sm text-sm text-muted">{body}</p>}
      {action && <div className="mt-4 flex justify-center">{action}</div>}
    </Card>
  );
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: React.ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-muted">{subtitle}</p>}
      </div>
      {actions}
    </div>
  );
}

export const Chip = ({ children }: { children: React.ReactNode }) => (
  <span className="rounded-full border border-line bg-canvas px-2.5 py-1 text-xs font-medium text-ink">{children}</span>
);
