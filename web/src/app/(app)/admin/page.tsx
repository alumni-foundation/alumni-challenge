"use client";

import { Building2, ChevronRight, Flag, ScrollText } from "lucide-react";
import Link from "next/link";
import { Badge, IconChip, PageHeader } from "@/components/ui";
import { useRoles } from "@/lib/api/hooks";
import { canManageAnyOrg, canModerate, canViewAuditLog, isPlatformAdmin, topRoleLabel } from "@/lib/roles";

type Tool = { href: string; title: string; body: string; icon: React.ElementType; show: boolean; soon?: boolean };

export default function AdminHome() {
  const roles = useRoles().data;
  const platform = isPlatformAdmin(roles);

  const tools: Tool[] = [
    {
      href: "/admin/organizations",
      title: "Schools and partners",
      body: platform
        ? "Add organizations, edit their details, appoint admins and register school email domains."
        : "Edit the organizations you manage, give people roles and register school email domains.",
      icon: Building2,
      show: canManageAnyOrg(roles),
    },
    {
      href: "/admin/activity",
      title: "Activity log",
      body: platform
        ? "Who changed what across the platform."
        : "Who changed what in the organizations you manage.",
      icon: ScrollText,
      show: canViewAuditLog(roles),
    },
    {
      href: "/admin/reports",
      title: "Reports and blocked members",
      body: "Review reports from members and decide what happens next.",
      icon: Flag,
      show: canModerate(roles),
      soon: true,
    },
  ];
  const visible = tools.filter((t) => t.show);

  return (
    <div>
      <PageHeader title="Admin" subtitle={`You’re signed in as ${topRoleLabel(roles)}.`} />
      <ul className="divide-y divide-line overflow-hidden rounded-2xl border border-line bg-surface">
        {visible.map(({ href, title, body, icon, soon }) => {
          const inner = (
            <>
              <IconChip icon={icon} tone={soon ? "ink" : "brand"} />
              <span className="min-w-0 flex-1">
                <span className="flex items-center gap-2 font-semibold">
                  {title}
                  {soon && <Badge>Coming soon</Badge>}
                </span>
                <span className="mt-0.5 block text-sm text-muted">{body}</span>
              </span>
              {!soon && <ChevronRight className="size-5 shrink-0 text-faint" aria-hidden />}
            </>
          );
          return (
            <li key={href}>
              {soon ? (
                <div aria-disabled className="flex items-center gap-4 px-5 py-4 opacity-60">{inner}</div>
              ) : (
                <Link href={href} className="flex items-center gap-4 px-5 py-4 transition-colors hover:bg-canvas">
                  {inner}
                </Link>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
