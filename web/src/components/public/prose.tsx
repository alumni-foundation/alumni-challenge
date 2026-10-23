import { cn } from "@/lib/utils";

/** Long-form reading text: comfortable line length, clear headings, nothing fancy. */
export function Prose({ title, intro, children }: { title: string; intro?: string; children: React.ReactNode }) {
  return (
    <article className="mx-auto max-w-2xl">
      <h1 className="text-title">{title}</h1>
      {intro && <p className="mt-2 text-lead text-muted">{intro}</p>}
      <div
        className={cn(
          "mt-8 space-y-4 text-body",
          "[&_h2]:mt-10 [&_h2]:text-heading [&_h3]:mt-6 [&_h3]:font-semibold",
          "[&_ul]:list-disc [&_ul]:space-y-2 [&_ul]:pl-6",
          "[&_a]:font-medium [&_a]:text-brand-ink [&_a:hover]:underline",
        )}
      >
        {children}
      </div>
    </article>
  );
}
