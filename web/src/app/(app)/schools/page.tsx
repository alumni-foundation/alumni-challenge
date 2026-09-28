"use client";

import Link from "next/link";
import { Building2 } from "lucide-react";
import { Card, EmptyState, PageHeader, Spinner } from "@/components/ui";
import { useOrgs } from "@/lib/api/hooks";

export default function SchoolsPage() {
  const orgs = useOrgs("school");
  return (
    <div>
      <PageHeader title="Schools" subtitle="Schools in the Alumni Challenge network." />
      {orgs.isLoading && <Spinner label="Loading schools" />}
      {orgs.data && orgs.data.length === 0 && <EmptyState title="None yet" body="Check back soon." />}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {orgs.data?.map((o) => (
          <Link key={o.id} href={`/schools/${o.id}`}>
            <Card className="h-full transition-shadow hover:shadow-md">
              <Building2 className="size-6 text-brand" aria-hidden />
              <p className="mt-3 font-semibold">{o.name}</p>
              {o.description && <p className="mt-1 line-clamp-2 text-sm text-muted">{o.description}</p>}
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
