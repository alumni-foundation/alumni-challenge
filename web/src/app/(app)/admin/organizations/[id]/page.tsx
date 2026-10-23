"use client";

import { ArrowLeft, Globe } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { MemberPicker, type PickedUser } from "@/components/admin/member-picker";
import { Alert, Badge, Button, Card, EmptyState, Field, Input, LinkButton, Select, Spinner, Textarea } from "@/components/ui";
import {
  useAddEmailDomain, useAssignMembership, useEmailDomains, useOrg, useRoles, useUpdateOrg,
} from "@/lib/api/hooks";
import type { Organization, Role } from "@/lib/api/types";
import { assignableRoles, canManageOrg, roleLabel } from "@/lib/roles";

function DetailsForm({ org }: { org: Organization }) {
  const update = useUpdateOrg(org.id);
  const [name, setName] = useState(org.name);
  const [description, setDescription] = useState(org.description ?? "");
  const [saved, setSaved] = useState(false);
  const [nameError, setNameError] = useState<string>();

  const dirty = name.trim() !== org.name || description.trim() !== (org.description ?? "");
  const server = update.error?.fieldErrors() ?? {};

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (name.trim().length < 2) return setNameError("Enter the organization’s name.");
    setNameError(undefined);
    setSaved(false);
    update.mutate({ name: name.trim(), description: description.trim() || null }, { onSuccess: () => setSaved(true) });
  }

  return (
    <Card>
      <h2 className="font-semibold">Details</h2>
      <form onSubmit={submit} className="mt-4 space-y-4" noValidate>
        <Field label="Name" htmlFor="d-name" error={nameError ?? server.name}>
          <Input id="d-name" value={name} onChange={(e) => { setName(e.target.value); setSaved(false); }} maxLength={255} />
        </Field>
        <Field label="Description" htmlFor="d-desc" error={server.description}>
          <Textarea id="d-desc" value={description} onChange={(e) => { setDescription(e.target.value); setSaved(false); }} maxLength={2000} />
        </Field>
        <p className="text-sm text-muted">Web address name: <span className="font-medium text-ink">{org.slug}</span> (can’t be changed)</p>
        {update.isError && Object.keys(server).length === 0 && <Alert>{update.error.message}</Alert>}
        {saved && <Alert tone="ok">Changes saved.</Alert>}
        <Button type="submit" loading={update.isPending} disabled={!dirty}>Save changes</Button>
      </form>
    </Card>
  );
}

function GrantRole({ org, allowed }: { org: Organization; allowed: Role[] }) {
  const assign = useAssignMembership(org.id);
  const [person, setPerson] = useState<PickedUser | null>(null);
  const [role, setRole] = useState<Role>(allowed[0]);
  const [done, setDone] = useState<string[]>([]);
  const [missing, setMissing] = useState(false);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!person) return setMissing(true);
    setMissing(false);
    assign.mutate(
      { user_id: person.id, role },
      {
        onSuccess: () => {
          setDone((d) => [`${person.label} is now ${roleLabel(role).toLowerCase()}.`, ...d]);
          setPerson(null);
        },
      },
    );
  }

  return (
    <Card>
      <h2 className="font-semibold">Give someone a role</h2>
      <p className="mt-1 text-sm text-muted">The role applies to {org.name} only.</p>
      <form onSubmit={submit} className="mt-4 grid gap-4 sm:grid-cols-[1fr_14rem]" noValidate>
        <Field label="Person" htmlFor="g-person" error={missing ? "Choose who should get the role." : undefined}>
          <MemberPicker id="g-person" value={person} onChange={(v) => { setPerson(v); setMissing(false); assign.reset(); }} />
        </Field>
        <Field label="Role" htmlFor="g-role">
          <Select id="g-role" value={role} onChange={(e) => setRole(e.target.value as Role)}>
            {allowed.map((r) => <option key={r} value={r}>{roleLabel(r)}</option>)}
          </Select>
        </Field>
        <div className="space-y-3 sm:col-span-2">
          {assign.isError && <Alert>{assign.error.message}</Alert>}
          {done.map((m, i) => <Alert key={`${i}-${m}`} tone="ok">{m}</Alert>)}
          <Button type="submit" loading={assign.isPending}>Give role</Button>
        </div>
      </form>
    </Card>
  );
}

function EmailDomains({ org }: { org: Organization }) {
  const domains = useEmailDomains(org.id, true);
  const add = useAddEmailDomain(org.id);
  const [value, setValue] = useState("");
  const [localError, setLocalError] = useState<string>();
  const server = add.error?.fieldErrors().domain;

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const domain = value.trim().toLowerCase();
    if (!domain.includes(".")) return setLocalError("Enter a domain such as school.ac.ke.");
    setLocalError(undefined);
    add.mutate(domain, { onSuccess: () => setValue("") });
  }

  return (
    <Card>
      <h2 className="font-semibold">School email domains</h2>
      <p className="mt-1 text-sm text-muted">Alumni who sign up with one of these domains can be verified automatically.</p>
      {domains.isLoading && <Spinner label="Loading domains" />}
      {domains.isError && <div className="mt-4"><Alert>{domains.error.message}</Alert></div>}
      {domains.data && domains.data.length === 0 && <p className="mt-4 text-sm text-muted">No domains registered yet.</p>}
      {domains.data && domains.data.length > 0 && (
        <ul className="mt-4 divide-y divide-line rounded-lg border border-line">
          {domains.data.map((d) => (
            <li key={d.id} className="flex items-center gap-3 px-3 py-2 text-sm">
              <Globe className="size-4 text-muted" aria-hidden /> {d.domain}
            </li>
          ))}
        </ul>
      )}
      <form onSubmit={submit} className="mt-4 flex flex-wrap items-start gap-3" noValidate>
        <div className="min-w-56 flex-1">
          <Field label="Add a domain" htmlFor="dom" error={localError ?? (add.isError ? (server ?? add.error.message) : undefined)}>
            <Input id="dom" value={value} onChange={(e) => { setValue(e.target.value); add.reset(); }} placeholder="school.ac.ke" autoCapitalize="none" />
          </Field>
        </div>
        <Button type="submit" loading={add.isPending} className="mt-[26px]">Add domain</Button>
      </form>
    </Card>
  );
}

export default function AdminOrgDetail() {
  const { id } = useParams<{ id: string }>();
  const org = useOrg(id);
  const roles = useRoles();

  if (org.isLoading || roles.isLoading) return <Spinner label="Loading organization" />;
  const back = <LinkButton href="/admin/organizations" variant="secondary">Back to organizations</LinkButton>;
  if (org.isError || !org.data) return <EmptyState title="Organization not found" action={back} />;
  if (!canManageOrg(roles.data, org.data.id)) {
    return <EmptyState title="You can’t manage this organization" body="Only its admins and platform administrators can." action={back} />;
  }

  const o = org.data;
  const allowed = assignableRoles(roles.data, o);

  return (
    <div className="max-w-3xl">
      <Link href="/admin/organizations" className="mb-4 inline-flex items-center gap-1 text-sm text-muted hover:text-ink">
        <ArrowLeft className="size-4" aria-hidden /> Schools and partners
      </Link>
      <div className="mb-6 flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-bold tracking-tight">{o.name}</h1>
        <Badge tone={o.type === "school" ? "brand" : "gold"}>{o.type === "school" ? "School" : "Partner"}</Badge>
      </div>
      <div className="space-y-6">
        <DetailsForm key={`${o.id}-${o.name}-${o.description ?? ""}`} org={o} />
        {allowed.length > 0 && <GrantRole org={o} allowed={allowed} />}
        {o.type === "school" && <EmailDomains org={o} />}
      </div>
    </div>
  );
}
