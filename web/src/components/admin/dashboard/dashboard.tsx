"use client";

import { ArrowRight, ChevronDown, Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { MessagesLink } from "@/components/shell/messages-link";
import { NotificationBell } from "@/components/shell/notification-bell";
import { OrgLogo } from "@/components/public/org";
import { EmptyState, ErrorState, LinkButton } from "@/components/ui";
import { ApiError } from "@/lib/api/client";
import { useMemberIndex, useMyProfile, useOrgs } from "@/lib/api/hooks";
import type { Organization } from "@/lib/api/types";
import { firstNameOf, greetingFor, useAdminOverview, type DashboardScope, type OverviewPeriod } from "@/lib/admin-overview";
import { DashboardBody, DashboardSkeleton } from "./parts";

const pill = "h-11 rounded-full border border-line-strong bg-surface text-small text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink";

/** The greeting, recomputed each minute so it is right if the page stays open across noon. */
function useGreeting() {
  const [now, setNow] = useState<Date | null>(null);
  useEffect(() => {
    const tick = () => setNow(new Date());
    tick();
    const t = window.setInterval(tick, 60_000);
    return () => window.clearInterval(t);
  }, []);
  return now ? greetingFor(now) : "Hello";
}

function SearchField() {
  const router = useRouter();
  const [value, setValue] = useState("");
  return (
    <form
      role="search"
      className="relative min-w-[11rem] flex-1 basis-56 xl:max-w-xs xl:flex-none xl:basis-64"
      onSubmit={(e) => {
        e.preventDefault();
        const q = value.trim();
        router.push(q ? `/directory?q=${encodeURIComponent(q)}` : "/directory");
      }}
    >
      <Search className="pointer-events-none absolute left-4 top-1/2 size-4 -translate-y-1/2 text-muted" aria-hidden />
      <input
        type="search"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        aria-label="Search alumni"
        placeholder="Search alumni"
        className={`${pill} w-full pl-11 pr-4 placeholder:text-faint focus:border-brand-ink`}
      />
    </form>
  );
}

/** Platform admins only: all organizations, or one school or partner. */
function ScopeSelect({ value, onChange }: { value: string; onChange: (id: string) => void }) {
  const schools = useOrgs("school");
  const partners = useOrgs("partner");
  const opts = (list: Organization[] | undefined) => (list ?? []).map((o) => <option key={o.id} value={o.id}>{o.name}</option>);
  return (
    <span className="relative inline-flex">
      <select aria-label="Show numbers for" value={value} onChange={(e) => onChange(e.target.value)} className={`${pill} max-w-[14rem] appearance-none truncate pl-4 pr-10 font-medium`}>
        <option value="">All organizations</option>
        {(schools.data?.length ?? 0) > 0 && <optgroup label="Schools">{opts(schools.data)}</optgroup>}
        {(partners.data?.length ?? 0) > 0 && <optgroup label="Partners">{opts(partners.data)}</optgroup>}
      </select>
      <ChevronDown className="pointer-events-none absolute right-3.5 top-1/2 size-4 -translate-y-1/2 text-muted" aria-hidden />
    </span>
  );
}

const NEXT_PAGE: Record<DashboardScope["kind"], (id: string | null) => { href: string; label: string }> = {
  platform: () => ({ href: "/admin/reports", label: "Reports" }),
  moderator: () => ({ href: "/admin/reports", label: "Reports" }),
  school: (id) => ({ href: `/school/${id}/roster`, label: "Alumni roster" }),
  partner: (id) => ({ href: `/partner/${id}/team`, label: "Team" }),
  organizer: () => ({ href: "/events", label: "Events" }),
};

/**
 * The staff dashboard: greeting and tools, five number tiles, the member journey, three working cards and the sign-up
 * chart. Everything comes from GET /admin/overview; a section the API leaves out (null) is not drawn.
 */
export function Dashboard({ scope, org }: { scope: DashboardScope; org?: Organization }) {
  const profile = useMyProfile();
  const greeting = useGreeting();
  const name = firstNameOf(profile.data?.full_name);
  const [period, setPeriod] = useState<OverviewPeriod>("30d");
  const [picked, setPicked] = useState("");
  const partners = useOrgs("partner");
  const partnerPicked = Boolean(picked) && (partners.data ?? []).some((p) => p.id === picked);
  const organizationId = scope.organizationId ?? (picked || null);
  const overview = useAdminOverview(period, organizationId);
  const isPartner = scope.kind === "partner" || org?.type === "partner" || partnerPicked;
  // Members belong to schools. A partner has none, so its member numbers would only ever read 0.
  const o = overview.data && isPartner ? { ...overview.data, totals: null, funnel: null, signups_per_day: null } : overview.data;
  const members = useMemberIndex(Boolean(o?.recent_audit?.length));
  const next = NEXT_PAGE[scope.kind](scope.organizationId);
  const effective: DashboardScope = organizationId && scope.kind === "platform" ? { kind: "platform", organizationId } : scope;

  const status = overview.error instanceof ApiError ? overview.error.status : undefined;
  // Event managers cannot open the activity log, so their card has no link to it.
  const activityHref =
    scope.kind === "platform" ? "/admin/activity" : scope.kind === "school" || scope.kind === "partner" ? `/${scope.kind}/${scope.organizationId}/activity` : undefined;

  return (
    <div className="page-enter mx-auto max-w-[1280px] space-y-4">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-3 pb-1">
        <div className="min-w-0 basis-full xl:basis-auto xl:flex-1">
          <h1 className="font-serif text-display font-semibold tracking-tight">
            {greeting}{name ? `, ${name}` : ""}
          </h1>
          {org && (
            <p className="mt-1.5 flex items-center gap-2 text-small text-muted">
              <OrgLogo org={org} size={28} /> <span className="truncate">{org.name}</span>
            </p>
          )}
        </div>
        <SearchField />
        {scope.kind === "platform" && <ScopeSelect value={picked} onChange={setPicked} />}
        <div className="hidden items-center gap-1 lg:flex">
          <MessagesLink />
          <NotificationBell />
        </div>
        <LinkButton href={next.href} variant="dark">
          {next.label} <ArrowRight className="size-4" aria-hidden />
        </LinkButton>
      </div>

      {overview.isLoading ? (
        <DashboardSkeleton />
      ) : overview.isError && !o ? (
        status === 403 ? (
          <EmptyState title="There’s no dashboard for your role" body="Your account can open the pages in the menu, but the overview numbers are not part of your role." />
        ) : status === 404 ? (
          <EmptyState title="We can’t find that organization" body="Pick another from the list, or choose All organizations." />
        ) : (
          <ErrorState message="We couldn’t load the overview. Check your connection and try again." onRetry={() => void overview.refetch()} />
        )
      ) : o ? (
        <>
          {overview.isError && <p role="alert" className="rounded-2xl bg-warn-soft px-4 py-2 text-small text-warn">We couldn’t refresh the numbers, so you’re seeing the last ones we had.</p>}
          <DashboardBody
            overview={o}
            scope={effective}
            period={period}
            onPeriod={setPeriod}
            fetching={overview.isFetching}
            nameOf={(id) => (id ? (members.byUser.get(id)?.full_name ?? null) : null)}
            activityHref={activityHref}
          />
        </>
      ) : null}
    </div>
  );
}
