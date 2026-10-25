"use client";

import { Building2, ChevronRight, Handshake, Plus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { StaffPage, SearchBox } from "@/components/staff/page";
import { Row, RowList } from "@/components/staff/rows";
import { Alert, Badge, Button, Card, EmptyState, Field, Icon3D, Input, Select, Skeleton, Tabs, Textarea } from "@/components/ui";
import { useCreateOrg, useOrgs, useRoles } from "@/lib/api/hooks";
import type { Organization, OrgType } from "@/lib/api/types";
import { canManageOrg, isPlatformAdmin } from "@/lib/roles";
import { slugify } from "@/lib/utils";

const SLUG_OK = /^[a-z0-9]+(-[a-z0-9]+)*$/;

function CreateForm({ onDone }: { onDone: (org: Organization) => void }) {
  const create = useCreateOrg();
  const [type, setType] = useState<OrgType>("school");
  const [name, setName] = useState("");
  const [slugEdit, setSlugEdit] = useState<string | null>(null);
  const [description, setDescription] = useState("");
  const [local, setLocal] = useState<Record<string, string>>({});

  const slug = slugEdit ?? slugify(name);
  const server = create.error?.fieldErrors() ?? {};
  const slugConflict = create.error?.status === 409 ? create.error.message : undefined;

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const errs: Record<string, string> = {};
    if (name.trim().length < 2) errs.name = "Enter the organization’s name.";
    if (slug.length < 3 || !SLUG_OK.test(slug)) errs.slug = "Use at least 3 lowercase letters or digits, with single hyphens between words.";
    setLocal(errs);
    if (Object.keys(errs).length) return;
    create.mutate({ type, name: name.trim(), slug, description: description.trim() || null }, { onSuccess: onDone });
  }

  return (
    <Card large className="mb-6">
      <h2 className="text-lead font-semibold">New organization</h2>
      <form onSubmit={submit} className="mt-4 grid gap-4 sm:grid-cols-2" noValidate>
        <Field label="Type" htmlFor="org-type">
          <Select id="org-type" value={type} onChange={(e) => setType(e.target.value as OrgType)}>
            <option value="school">School</option>
            <option value="partner">Partner</option>
          </Select>
        </Field>
        <Field label="Name" htmlFor="org-name" error={local.name ?? server.name}>
          <Input id="org-name" value={name} onChange={(e) => setName(e.target.value)} maxLength={255} />
        </Field>
        <Field
          label="Web address name"
          htmlFor="org-slug"
          error={local.slug ?? slugConflict ?? server.slug}
          hint="Used in links. Can’t be changed later."
        >
          <Input id="org-slug" value={slug} onChange={(e) => setSlugEdit(e.target.value.toLowerCase())} maxLength={100} />
        </Field>
        <div className="sm:col-span-2">
          <Field label="Description (optional)" htmlFor="org-desc" error={server.description}>
            <Textarea id="org-desc" value={description} onChange={(e) => setDescription(e.target.value)} maxLength={2000} />
          </Field>
        </div>
        {create.isError && !slugConflict && Object.keys(server).length === 0 && (
          <div className="sm:col-span-2"><Alert>{create.error.message}</Alert></div>
        )}
        <div className="sm:col-span-2">
          <Button variant="dark" type="submit" loading={create.isPending}>Create organization</Button>
        </div>
      </form>
    </Card>
  );
}

export default function AdminOrganizations() {
  const router = useRouter();
  const roles = useRoles();
  const schools = useOrgs("school");
  const partners = useOrgs("partner");
  const [filter, setFilter] = useState<"all" | OrgType>("all");
  const [creating, setCreating] = useState(false);
  const [query, setQuery] = useState("");

  const platform = isPlatformAdmin(roles.data);
  const loading = schools.isLoading || partners.isLoading || roles.isLoading;
  const failed = schools.isError || partners.isError;

  const all = [...(schools.data ?? []), ...(partners.data ?? [])]
    .filter((o) => canManageOrg(roles.data, o.id))
    .filter((o) => filter === "all" || o.type === filter)
    .filter((o) => !query.trim() || `${o.name} ${o.slug}`.toLowerCase().includes(query.trim().toLowerCase()))
    .sort((a, b) => a.name.localeCompare(b.name));
  const capped = (schools.data?.length ?? 0) >= 100 || (partners.data?.length ?? 0) >= 100;

  const FILTERS: { key: "all" | OrgType; label: string }[] = [
    { key: "all", label: "All" },
    { key: "school", label: "Schools" },
    { key: "partner", label: "Partners" },
  ];

  const visible = [...(schools.data ?? []), ...(partners.data ?? [])].filter((o) => canManageOrg(roles.data, o.id));
  const tiles = loading || failed
    ? undefined
    : [
        { label: "Schools", value: visible.filter((o) => o.type === "school").length, gold: true },
        { label: "Partners", value: visible.filter((o) => o.type === "partner").length },
      ];

  return (
    <StaffPage
      title="Schools and partners"
      subtitle={platform ? "Every organization on the platform." : "The organizations you manage."}
      tiles={tiles}
      actions={
        platform && !creating ? (
          <Button variant="dark" onClick={() => setCreating(true)}><Plus className="size-4" aria-hidden /> New organization</Button>
        ) : undefined
      }
    >
      {platform && creating && (
        <CreateForm onDone={(org) => router.push(`/admin/organizations/${org.id}`)} />
      )}

      <div className="flex flex-wrap items-center gap-3">
        <SearchBox value={query} onChange={setQuery} label="Search organizations" placeholder="Search by name" className="basis-64 sm:w-80 sm:flex-none" />
        {platform && (
          <Tabs<"all" | OrgType> pills label="Filter by type" value={filter} onChange={setFilter} tabs={FILTERS.map((f) => ({ value: f.key, label: f.label }))} />
        )}
      </div>

      {loading && (
        <div role="status" aria-label="Loading organizations" className="space-y-2">
          {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-16 rounded-2xl" />)}
        </div>
      )}
      {failed && <Alert>We couldn’t load the organizations. Refresh the page to try again.</Alert>}
      {!loading && !failed && all.length === 0 && (
        <EmptyState
          title={query.trim() ? "No organization matches your search" : platform ? "No organizations yet" : "You don’t manage any organizations"}
          body={query.trim() ? "Try a different name." : platform ? "Create the first school or partner to get started." : undefined}
        />
      )}
      {all.length > 0 && (
        <RowList label="Organizations">
          {all.map((o) => (
            <Row key={o.id} href={`/admin/organizations/${o.id}`}>
              <Icon3D icon={o.type === "school" ? Building2 : Handshake} tone={o.type === "school" ? "ember" : "gold"} size="sm" />
              <span className="min-w-0 flex-1">
                <span className="block truncate font-semibold">{o.name}</span>
                <span className="block truncate text-small text-muted">{o.slug}</span>
              </span>
              <Badge tone={o.type === "school" ? "brand" : "gold"}>{o.type === "school" ? "School" : "Partner"}</Badge>
              <ChevronRight className="size-5 shrink-0 text-faint" aria-hidden />
            </Row>
          ))}
        </RowList>
      )}
      {capped && <p className="text-sm text-muted">Showing the first 100 of each type.</p>}
    </StaffPage>
  );
}
