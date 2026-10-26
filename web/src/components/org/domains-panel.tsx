"use client";

import { Globe, Trash2 } from "lucide-react";
import { useState } from "react";
import { Row, RowList } from "@/components/staff/rows";
import { Button, Card, ConfirmDialog, ErrorState, Field, Input, Skeleton, useToast } from "@/components/ui";
import { isMissingEndpoint, useAddEmailDomain, useEmailDomains, useRemoveEmailDomain } from "@/lib/api/hooks";
import type { EmailDomain, Organization } from "@/lib/api/types";

/** The school's email domains: add one, or remove one. Removing is switched off if the server turns out not to support it. */
export function DomainsPanel({ org }: { org: Organization }) {
  const domains = useEmailDomains(org.id, true);
  const add = useAddEmailDomain(org.id);
  const remove = useRemoveEmailDomain(org.id);
  const [removing, setRemoving] = useState<EmailDomain | null>(null);
  const [removeMissing, setRemoveMissing] = useState(false);
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
          Alumni who sign up with an email address on one of these domains are verified automatically. Removing a domain stops that for new sign-ups.
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
              <Globe className="size-4 text-muted" aria-hidden />
              <span className="min-w-0 flex-1 break-all">{d.domain}</span>
              <Button
                variant="secondary"
                size="sm"
                disabled={removeMissing}
                title={removeMissing ? "Removing a domain isn’t available yet." : undefined}
                aria-label={`Remove ${d.domain}`}
                onClick={() => setRemoving(d)}
              >
                <Trash2 className="size-4" aria-hidden /> Remove
              </Button>
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

      <ConfirmDialog
        open={removing !== null}
        title={`Remove ${removing?.domain ?? "this domain"}?`}
        body="New sign-ups with this email domain will no longer be verified automatically."
        confirmLabel="Remove domain"
        danger
        onClose={() => setRemoving(null)}
        onConfirm={async () => {
          if (!removing) return;
          try {
            await remove.mutateAsync(removing.id);
          } catch (e) {
            // No such endpoint yet: say so, and switch the buttons off rather than pretend it worked.
            if (isMissingEndpoint(e)) setRemoveMissing(true);
            throw e;
          }
          toast("Domain removed.");
        }}
      />
    </Card>
  );
}
