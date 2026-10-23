"use client";

import { useState } from "react";
import { Alert, Button, Card, Field, Input, Textarea, useToast } from "@/components/ui";
import { useUpdateOrg } from "@/lib/api/hooks";
import type { Organization } from "@/lib/api/types";
import { LogoEditor } from "./logo-editor";

/** Name, description and logo. The web address name can't change once it exists. */
export function EditPanel({ org }: { org: Organization }) {
  const update = useUpdateOrg(org.id);
  const toast = useToast();
  const [name, setName] = useState(org.name);
  const [description, setDescription] = useState(org.description ?? "");
  const [nameError, setNameError] = useState<string>();

  const dirty = name.trim() !== org.name || description.trim() !== (org.description ?? "");
  const server = update.error?.fieldErrors() ?? {};

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (name.trim().length < 2) return setNameError("Enter the organization’s name.");
    setNameError(undefined);
    update.mutate(
      { name: name.trim(), description: description.trim() || null },
      { onSuccess: () => toast("Changes saved.") },
    );
  }

  return (
    <div className="space-y-6">
      <Card>
        <h2 className="mb-4 text-heading">Logo</h2>
        <LogoEditor org={org} />
      </Card>
      <Card>
        <h2 className="text-heading">Details</h2>
        <form onSubmit={submit} className="mt-4 space-y-4" noValidate>
          <Field label="Name" htmlFor="d-name" error={nameError ?? server.name}>
            <Input id="d-name" value={name} onChange={(e) => setName(e.target.value)} maxLength={255} />
          </Field>
          <Field label="Description" htmlFor="d-desc" error={server.description} hint="Shown on the public page.">
            <Textarea id="d-desc" rows={5} value={description} onChange={(e) => setDescription(e.target.value)} maxLength={2000} />
          </Field>
          <p className="text-small text-muted">Web address name: <span className="font-medium text-ink">{org.slug}</span> (can’t be changed)</p>
          {update.isError && Object.keys(server).length === 0 && <Alert>{update.error.message}</Alert>}
          <Button type="submit" loading={update.isPending} disabled={!dirty}>Save changes</Button>
        </form>
      </Card>
    </div>
  );
}
