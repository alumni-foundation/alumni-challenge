"use client";

import { Globe } from "lucide-react";
import { useState } from "react";
import { Row, RowList } from "@/components/staff/rows";
import { Button, Card, ErrorState, Field, Input, Skeleton, useToast } from "@/components/ui";
import { useAddEmailDomain, useEmailDomains } from "@/lib/api/hooks";
import type { Organization } from "@/lib/api/types";

/** The school's email domains. There is no remove in the API, so there is no delete button. */
export function DomainsPanel({ org }: { org: Organization }) {
  const domains = useEmailDomains(org.id, true);
  const add = useAddEmailDomain(org.id);
  const toast = useToast();
  const [value, setValue] = useState("");
  const [localError, setLocalError] = useState<string>();
  const server = add.error?.fieldErrors().domain;

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const domain = value.trim().toLowerCase();
    if (!domain.includes(".") || domain.includes("@") || domain.includes(" ")) {
      return setLocalError("Enter a domain such as school.ac.ke, without the @.");
    }
    setLocalError(undefined);
    add.mutate(domain, {
      onSuccess: () => {
        setValue("");
        toast("Domain added.");
      },
    });
  }

  return (
    <Card large className="space-y-4">
      <div>
        <h2 className="text-lead font-semibold">School email domains</h2>
        <p className="mt-1 text-small text-muted">
          Alumni who sign up with an email address on one of these domains are verified automatically. Once a domain is added it can’t be removed here.
        </p>
      </div>
      {domains.isError ? (
        <ErrorState message={domains.error.message} onRetry={() => void domains.refetch()} />
      ) : domains.isLoading ? (
        <Skeleton className="h-16" />
      ) : domains.data && domains.data.length === 0 ? (
        <p className="text-small text-muted">No domains registered yet.</p>
      ) : (
        <RowList label="Registered domains">
          {domains.data?.map((d) => (
            <Row key={d.id} className="min-h-12 py-2 text-small">
              <Globe className="size-4 text-muted" aria-hidden /> {d.domain}
            </Row>
          ))}
        </RowList>
      )}
      <form onSubmit={submit} className="flex flex-col gap-3 sm:flex-row sm:items-start" noValidate>
        <div className="flex-1">
          <Field label="Add a domain" htmlFor="dom" error={localError ?? (add.isError ? (server ?? add.error.message) : undefined)}>
            <Input id="dom" value={value} onChange={(e) => { setValue(e.target.value); add.reset(); }} placeholder="school.ac.ke" autoCapitalize="none" autoCorrect="off" inputMode="url" />
          </Field>
        </div>
        <Button variant="dark" type="submit" loading={add.isPending} className="sm:mt-[26px]">Add domain</Button>
      </form>
    </Card>
  );
}
