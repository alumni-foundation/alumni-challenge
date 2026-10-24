import { Building2 } from "lucide-react";
import Link from "next/link";
import { Card, EmptyState } from "@/components/ui";
import { Reveal } from "@/components/ui/reveal";
import type { Organization } from "@/lib/api/types";
import { cn } from "@/lib/utils";

export function OrgLogo({ org, size = 48 }: { org: Pick<Organization, "name" | "logo_url">; size?: number }) {
  return (
    <span
      className={cn("inline-flex shrink-0 items-center justify-center overflow-hidden rounded-xl bg-brand-soft text-brand-ink")}
      style={{ width: size, height: size }}
    >
      {org.logo_url ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={org.logo_url} alt={`${org.name} logo`} className="size-full object-contain" />
      ) : (
        <Building2 className="size-1/2" aria-hidden />
      )}
    </span>
  );
}

/** A grid of schools or partners, each linking to its own public page. */
export function OrgGrid({ orgs, base, noun, reveal = false }: { orgs: Organization[] | null; base: "/schools" | "/partners"; noun: string; reveal?: boolean }) {
  if (orgs === null) {
    return <EmptyState title={`We can’t show ${noun} right now`} body="Please try again in a moment." />;
  }
  if (orgs.length === 0) {
    return <EmptyState title={`No ${noun} yet`} body="They will appear here as they join." />;
  }
  return (
    <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {orgs.map((o, i) => {
        const card = (
          <Link href={`${base}/${o.id}`} className="block h-full rounded-card">
            <Card interactive className="flex h-full items-start gap-3">
              <OrgLogo org={o} />
              <span className="min-w-0">
                <span className="block font-semibold">{o.name}</span>
                {o.description && <span className="mt-1 line-clamp-2 block text-small text-muted">{o.description}</span>}
              </span>
            </Card>
          </Link>
        );
        return (
          <li key={o.id}>
            {reveal ? (
              <Reveal from={i % 2 === 0 ? "left" : "right"} delay={(i % 3) * 90} className="h-full">
                {card}
              </Reveal>
            ) : (
              card
            )}
          </li>
        );
      })}
    </ul>
  );
}
