import { LinkButton } from "@/components/ui";

/** A calm full-width message for pages that are not available: not found, not allowed, suspended. */
export function StatusPage({ code, title, children, actions }: {
  code?: string;
  title: string;
  children: React.ReactNode;
  actions?: React.ReactNode;
}) {
  return (
    <div className="mx-auto max-w-md py-8 text-center">
      {code && <p className="text-display font-bold text-brand-ink">{code}</p>}
      <h1 className="mt-2 text-title">{title}</h1>
      <div className="mt-3 space-y-2 text-body text-muted">{children}</div>
      <div className="mt-6 flex flex-col justify-center gap-3 sm:flex-row">
        {actions ?? <LinkButton href="/">Go to the home page</LinkButton>}
      </div>
    </div>
  );
}
