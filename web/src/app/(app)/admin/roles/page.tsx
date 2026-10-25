"use client";

import { ShieldCheck, ShieldOff } from "lucide-react";
import { useState } from "react";
import { MemberPicker, type PickedUser } from "@/components/admin/member-picker";
import { StaffPage, Section } from "@/components/staff/page";
import { Alert, Button, ConfirmDialog, EmptyState, Field, Select, Skeleton, useToast } from "@/components/ui";
import { api } from "@/lib/api/client";
import { useRoles } from "@/lib/api/hooks";
import type { Role } from "@/lib/api/types";
import { grantablePlatformRoles, isPlatformAdmin, isSuperAdmin, roleLabel } from "@/lib/roles";

const DESCRIPTION: Record<string, string> = {
  moderator: "Reviews reports and can suspend accounts.",
  admin: "Manages organizations and platform settings.",
  super_admin: "Everything an admin can do, and can appoint admins.",
};

export default function PlatformRolesPage() {
  const roles = useRoles();
  const toast = useToast();
  const [person, setPerson] = useState<PickedUser | null>(null);
  const [role, setRole] = useState<Role>("moderator");
  const [confirmGrant, setConfirmGrant] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [revoking, setRevoking] = useState(false);

  if (roles.isLoading) return <Skeleton className="h-40 rounded-card" />;
  if (!isPlatformAdmin(roles.data)) {
    return <EmptyState title="Platform roles are for administrators" body="Your account doesn’t hold an admin role." />;
  }
  const allowed = grantablePlatformRoles(roles.data);
  const chosen = allowed.includes(role) ? role : allowed[0];

  async function grant() {
    if (!person) return;
    await api(`users/${person.id}/platform-roles`, { method: "POST", body: { role: chosen } });
    toast(`${person.label} is now ${roleLabel(chosen).toLowerCase()}.`);
  }

  return (
    <StaffPage title="Platform roles" subtitle="Who can moderate and administer the whole platform.">
      <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
      <Section icon={ShieldCheck} tone="ember" title="Give or take away a role" hint="Search for the person, choose a role, then give it or take it away." className="space-y-5">
        <Field label="Person" htmlFor="role-person">
          <MemberPicker id="role-person" value={person} onChange={(v) => { setPerson(v); setProblem(null); }} />
        </Field>
        <Field label="Role" htmlFor="role-kind" hint={DESCRIPTION[chosen]}>
          <Select id="role-kind" value={chosen} onChange={(e) => { setRole(e.target.value as Role); setProblem(null); }}>
            {allowed.map((r) => <option key={r} value={r}>{roleLabel(r)}</option>)}
          </Select>
        </Field>
        {problem && <Alert>{problem}</Alert>}
        <div className="flex flex-col gap-3 sm:flex-row">
          <Button variant="dark" onClick={() => setConfirmGrant(true)} disabled={!person}>
            <ShieldCheck className="size-4" aria-hidden /> Give role
          </Button>
          <Button variant="danger" onClick={() => setRevoking(true)} disabled={!person}>
            <ShieldOff className="size-4" aria-hidden /> Take role away
          </Button>
        </div>
      </Section>

      <Section icon={ShieldOff} tone="ink" title="What each role can do" className="text-small text-muted">
        <ul className="space-y-3">
          {Object.entries(DESCRIPTION).map(([r, d]) => (
            <li key={r}><span className="font-semibold text-ink">{roleLabel(r as Role)}.</span> {d}</li>
          ))}
        </ul>
      <div className="mt-4 space-y-2">
        <p>{isSuperAdmin(roles.data) ? "As a super admin you can give any platform role." : "As an admin you can give the moderator role."} Nobody can change their own roles, and the last super admin can never be removed.</p>
        <p>Staff accounts usually have no public profile, so they won’t show up when you search by name. Paste their user ID instead.</p>
      </div>
      </Section>
      </div>

      <ConfirmDialog
        open={confirmGrant}
        title={`Make ${person?.label ?? "this person"} ${roleLabel(chosen).toLowerCase()}?`}
        body={DESCRIPTION[chosen] ? `${DESCRIPTION[chosen]} They get it straight away. You can take it away later.` : "They get this role straight away. You can take it away later."}
        confirmLabel="Give role"
        onClose={() => setConfirmGrant(false)}
        onConfirm={grant}
      />
      <ConfirmDialog
        open={revoking}
        title={`Take the ${roleLabel(chosen).toLowerCase()} role from ${person?.label ?? "this person"}?`}
        body="They lose this role straight away. You can give it back later."
        confirmLabel="Take role away"
        danger
        onClose={() => setRevoking(false)}
        onConfirm={async () => {
          if (!person) return;
          await api(`users/${person.id}/platform-roles/${chosen}`, { method: "DELETE" });
          toast(`${roleLabel(chosen)} role removed from ${person.label}.`);
        }}
      />
    </StaffPage>
  );
}
