"use client";

import { CalendarPlus, ChevronRight, Globe, GraduationCap, Pencil, ScrollText, Users } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { BarList } from "@/components/home/bars";
import { EmptyState, Icon3D, LinkButton, PageHeader, Skeleton } from "@/components/ui";
import { Dashboard } from "@/components/admin/dashboard/dashboard";
import { OrgLogo } from "@/components/public/org";
import { useOrgs, useRoles } from "@/lib/api/hooks";
import type { Organization } from "@/lib/api/types";
import { ActivityPanel } from "./activity-panel";
import { DomainsPanel } from "./domains-panel";
import { EditPanel } from "./edit-panel";
import { OrgGate, OrgHeader, type OrgKind } from "./gate";
import { RosterPanel } from "./roster-panel";
import { TeamPanel } from "./team-panel";

export type Section = "overview" | "edit" | "domains" | "team" | "roster" | "activity";

const TITLES: Record<Exclude<Section, "overview">, { title: string; subtitle: string }> = {
  edit: { title: "Edit details", subtitle: "What visitors see on your public page." },
  domains: { title: "Email domains", subtitle: "Alumni with these email addresses are verified automatically." },
  team: { title: "Team", subtitle: "Who can help run this organization." },
  roster: { title: "Alumni", subtitle: "Everyone who named your school, and who is waiting to be verified." },
  activity: { title: "Activity", subtitle: "What has changed, newest first." },
};

function Overview({ org, kind }: { org: Organization; kind: OrgKind }) {
  const base = `/${kind}/${org.id}`;
  type Entry = { href: string; title: string; body: string; icon: React.ElementType };
  const links: Entry[] = [];
  if (kind === "school") links.push({ href: `${base}/roster`, title: "Alumni", body: "See who named your school and verify people who are waiting.", icon: GraduationCap });
  links.push({ href: `${base}/team`, title: "Team", body: "Find someone by email and give them a role, or take a role away.", icon: Users });
  links.push({ href: `${base}/edit`, title: "Edit details and logo", body: "Change the name, description and logo.", icon: Pencil });
  if (kind === "school") links.push({ href: `${base}/email-domains`, title: "Email domains", body: "Verify alumni automatically when they sign up with a school email.", icon: Globe });
  links.push({ href: `${base}/activity`, title: "Activity", body: "What has changed, and who changed it.", icon: ScrollText });

  return (
    <div className="mx-auto max-w-[1280px] space-y-8">
      <Dashboard scope={{ kind, organizationId: org.id }} org={org} />
      <section aria-label="Manage" className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-lead font-semibold">Manage {org.name}</h2>
          <LinkButton href={`/admin/events/new?org=${org.id}`} variant="dark" size="sm"><CalendarPlus className="size-4" aria-hidden /> Create event</LinkButton>
        </div>
        {org.description && <p className="whitespace-pre-line text-small text-muted">{org.description}</p>}
        <BarList className="grid gap-3 space-y-0 md:grid-cols-2 xl:grid-cols-3">
          {links.map(({ href, title, body, icon }) => (
            <li key={href}>
              <Link href={href} className="flex min-h-16 items-center gap-4 rounded-2xl border border-line bg-surface px-4 py-3 shadow-resting transition-[transform,box-shadow] duration-200 hover:-translate-y-0.5 hover:shadow-raised focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink motion-reduce:transition-none">
                <Icon3D icon={icon} tone="ink" size="sm" />
                <span className="min-w-0 flex-1">
                  <span className="block font-semibold">{title}</span>
                  <span className="mt-0.5 block text-small text-muted">{body}</span>
                </span>
                <ChevronRight className="size-5 shrink-0 text-faint" aria-hidden />
              </Link>
            </li>
          ))}
        </BarList>
      </section>
      <Link href={`/${kind === "school" ? "schools" : "partners"}/${org.id}`} className="mt-4 inline-flex min-h-11 items-center text-small font-medium text-brand-ink hover:underline">
        See the public page
      </Link>
    </div>
  );
}

/** One screen of the school or partner admin area. The route files are one-liners that pick the section. */
export function OrgSectionPage({ kind, id, section }: { kind: OrgKind; id: string; section: Section }) {
  return (
    <OrgGate id={id} kind={kind}>
      {(org) => {
        if (section === "overview") return <Overview org={org} kind={kind} />;
        if ((section === "domains" || section === "roster") && kind !== "school") {
          return <EmptyState title="This page is for schools." />;
        }
        const { title, subtitle } = TITLES[section];
        return (
          <div className="max-w-3xl">
            <OrgHeader org={org} title={title} subtitle={org.name} back={{ href: `/${kind}/${org.id}`, label: "Overview" }} />
            <p className="-mt-3 mb-6 text-small text-muted">{subtitle}</p>
            {section === "edit" && <EditPanel org={org} />}
            {section === "domains" && <DomainsPanel org={org} />}
            {section === "team" && <TeamPanel org={org} />}
            {section === "roster" && <RosterPanel org={org} />}
            {section === "activity" && <ActivityPanel />}
          </div>
        );
      }}
    </OrgGate>
  );
}

/** For someone who runs several schools (or partners): choose which one. One goes straight in. */
export function OrgPicker({ kind }: { kind: OrgKind }) {
  const router = useRouter();
  const roles = useRoles();
  const orgs = useOrgs(kind);
  const role = kind === "school" ? "school_admin" : "partner_admin";
  const mine = (orgs.data ?? []).filter((o) => (roles.data ?? []).some((m) => m.role === role && m.organization_id === o.id));

  useEffect(() => {
    if (mine.length === 1) router.replace(`/${kind}/${mine[0].id}`);
  }, [mine, kind, router]);

  if (roles.isLoading || orgs.isLoading || mine.length === 1) return <Skeleton className="mx-auto h-40 max-w-3xl rounded-card" />;
  if (mine.length === 0) {
    return <EmptyState title={`You don’t run any ${kind === "school" ? "schools" : "partners"}.`} />;
  }
  return (
    <div className="max-w-3xl">
      <PageHeader title={kind === "school" ? "Your schools" : "Your partners"} subtitle="Choose one to manage." />
      <ul className="divide-y divide-line overflow-hidden rounded-card border border-line bg-surface">
        {mine.map((o) => (
          <li key={o.id}>
            <Link href={`/${kind}/${o.id}`} className="flex min-h-16 items-center gap-4 px-4 py-4 hover:bg-sunken sm:px-5">
              <OrgLogo org={o} size={44} />
              <span className="min-w-0 flex-1 truncate font-semibold">{o.name}</span>
              <ChevronRight className="size-5 shrink-0 text-faint" aria-hidden />
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

