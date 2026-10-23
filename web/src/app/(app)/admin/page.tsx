"use client";

import { Building2, ChevronRight, FileText, ScrollText, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { Badge, IconChip, PageHeader, Skeleton } from "@/components/ui";
import { REPORTS_PAGE_SIZE, useReports, useRoles } from "@/lib/api/hooks";
import { isPlatformAdmin, landingFor, topRoleLabel } from "@/lib/roles";

type Tool = { href: string; title: string; body: string; icon: React.ElementType; badge?: string };

export default function AdminHome() {
  const router = useRouter();
  const roles = useRoles();
  const platform = isPlatformAdmin(roles.data);
  const openReports = useReports("open", 0);

  // The dashboard is for platform admins. Everyone else is sent to their own page.
  useEffect(() => {
    if (roles.data && !platform) router.replace(landingFor(roles.data));
  }, [roles.data, platform, router]);

  if (roles.isLoading || !platform) {
    return <Skeleton className="h-48 max-w-3xl rounded-card" />;
  }

  const open = openReports.data?.length ?? 0;
  const tools: Tool[] = [
    {
      href: "/admin/reports",
      title: "Reports",
      body: "Review what members have reported and decide what happens next.",
      icon: FileText,
      badge: openReports.data ? (open === 0 ? "None open" : `${open >= REPORTS_PAGE_SIZE ? `${open}+` : open} open`) : undefined,
    },
    {
      href: "/admin/organizations",
      title: "Schools and partners",
      body: "Add organizations, edit their details, appoint admins and register school email domains.",
      icon: Building2,
    },
    {
      href: "/admin/roles",
      title: "Platform roles",
      body: "Give or take away the moderator and admin roles.",
      icon: ShieldCheck,
    },
    {
      href: "/admin/activity",
      title: "Activity log",
      body: "Who changed what across the platform.",
      icon: ScrollText,
    },
  ];

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader title="Admin" subtitle={`You’re signed in as ${topRoleLabel(roles.data)}.`} />
      <ul className="divide-y divide-line overflow-hidden rounded-card border border-line bg-surface">
        {tools.map(({ href, title, body, icon, badge }) => (
          <li key={href}>
            <Link href={href} className="flex min-h-16 items-center gap-4 px-4 py-4 transition-colors hover:bg-sunken sm:px-5">
              <IconChip icon={icon} />
              <span className="min-w-0 flex-1">
                <span className="flex flex-wrap items-center gap-2 font-semibold">
                  {title}
                  {badge && <Badge tone={badge === "None open" ? "neutral" : "warn"}>{badge}</Badge>}
                </span>
                <span className="mt-0.5 block text-small text-muted">{body}</span>
              </span>
              <ChevronRight className="size-5 shrink-0 text-faint" aria-hidden />
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
