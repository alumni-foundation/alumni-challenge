"use client";

import Link from "next/link";
import { useState } from "react";
import { Alert, Badge, Button, Card, EmptyState, ErrorState, PageHeader, Skeleton, Tabs, useToast } from "@/components/ui";
import { api } from "@/lib/api/client";
import { friendlyError } from "@/lib/api/messages";
import { REPORTS_PAGE_SIZE, useReports, useRoles, useWrite } from "@/lib/api/hooks";
import type { Report, ReportStatus } from "@/lib/api/types";
import { canModerate } from "@/lib/roles";
import { formatDate } from "@/lib/utils";

const TABS: { value: ReportStatus; label: string }[] = [
  { value: "open", label: "Open" },
  { value: "reviewing", label: "Reviewing" },
  { value: "resolved", label: "Resolved" },
  { value: "dismissed", label: "Dismissed" },
];
const TONE: Record<ReportStatus, "warn" | "blue" | "ok" | "neutral"> = {
  open: "warn",
  reviewing: "blue",
  resolved: "ok",
  dismissed: "neutral",
};
const EMPTY: Record<ReportStatus, string> = {
  open: "No open reports. Nothing is waiting for you.",
  reviewing: "Nothing is being reviewed right now.",
  resolved: "No resolved reports yet.",
  dismissed: "No dismissed reports yet.",
};

/** The list gives ids, not names, so show a short, stable tag instead of a bare UUID. */
const shortId = (id: string | null) => (id ? `${id.slice(0, 8)}…` : "—");

function ReportCard({ report, onChange, busy }: { report: Report; onChange: (status: ReportStatus) => void; busy: ReportStatus | null }) {
  const isProfile = report.target_type === "profile";
  const active = report.status === "open" || report.status === "reviewing";
  return (
    <Card className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={TONE[report.status]}>{TABS.find((t) => t.value === report.status)?.label}</Badge>
        <span className="text-small font-medium capitalize">{report.target_type}</span>
        <span className="text-caption text-muted">{formatDate(report.created_at)}</span>
      </div>
      <p className="whitespace-pre-line break-words text-body">{report.reason}</p>
      <dl className="grid gap-x-6 gap-y-1 text-small text-muted sm:grid-cols-2">
        <div className="flex gap-2"><dt>Reported by</dt><dd className="font-mono text-ink" title={report.reporter_user_id}>{shortId(report.reporter_user_id)}</dd></div>
        <div className="flex gap-2"><dt>Reviewed by</dt><dd className="font-mono text-ink" title={report.reviewed_by ?? undefined}>{shortId(report.reviewed_by)}</dd></div>
        {report.resolved_at && <div className="flex gap-2"><dt>Closed</dt><dd className="text-ink">{formatDate(report.resolved_at)}</dd></div>}
      </dl>
      <div className="flex flex-col gap-2 border-t border-line pt-3 sm:flex-row sm:flex-wrap">
        {isProfile && active ? (
          <Link
            href={`/alumni/${report.target_id}?report=${report.id}`}
            className="inline-flex h-11 items-center justify-center rounded-control border border-line-strong bg-surface px-5 text-small font-medium hover:bg-sunken sm:h-9 sm:px-3"
          >
            Open profile
          </Link>
        ) : (
          !isProfile && <span className="self-center text-small text-muted">This kind of report has no page to open yet.</span>
        )}
        {report.status === "open" && (
          <Button variant="secondary" size="sm" loading={busy === "reviewing"} disabled={busy !== null} onClick={() => onChange("reviewing")}>Start review</Button>
        )}
        {active && (
          <>
            <Button variant="dark" size="sm" loading={busy === "resolved"} disabled={busy !== null} onClick={() => onChange("resolved")}>Resolve</Button>
            <Button variant="ghost" size="sm" loading={busy === "dismissed"} disabled={busy !== null} onClick={() => onChange("dismissed")}>Dismiss</Button>
          </>
        )}
      </div>
    </Card>
  );
}

export default function ReportsPage() {
  const roles = useRoles();
  const toast = useToast();
  const [status, setStatus] = useState<ReportStatus>("open");
  const [page, setPage] = useState(0);
  const [working, setWorking] = useState<{ id: string; status: ReportStatus } | null>(null);
  const reports = useReports(status, page, canModerate(roles.data));
  const update = useWrite(
    ({ id, status: next }: { id: string; status: ReportStatus }) => api(`reports/${id}`, { method: "PATCH", body: { status: next } }),
    [["reports"]],
  );

  if (roles.isLoading) return <Skeleton className="h-40 rounded-card" />;
  if (!canModerate(roles.data)) {
    return <EmptyState title="Reports are for moderators" body="Your account doesn’t hold a moderator or admin role." />;
  }

  async function change(report: Report, next: ReportStatus) {
    setWorking({ id: report.id, status: next });
    try {
      await update.mutateAsync({ id: report.id, status: next });
      toast(next === "reviewing" ? "Review started." : next === "resolved" ? "Report resolved." : "Report dismissed.");
    } catch (e) {
      toast(friendlyError(e), "info");
    } finally {
      setWorking(null);
    }
  }

  const items = reports.data ?? [];
  const hasNext = items.length === REPORTS_PAGE_SIZE;

  return (
    <div className="max-w-3xl">
      <PageHeader title="Reports" subtitle="What members have asked us to look at, newest first." />
      <div className="mb-4">
        <Alert tone="info">
          You can open a reported profile only while its report is Open or Reviewing. Once you resolve or dismiss the report, the profile is hidden from you again.
        </Alert>
      </div>
      <Tabs<ReportStatus> label="Report status" tabs={TABS} value={status} onChange={(s) => { setStatus(s); setPage(0); }} />
      <div role="tabpanel" id={`${status}-panel`} aria-labelledby={`${status}-tab`} className="mt-4 space-y-3">
        {reports.isError ? (
          <ErrorState message={reports.error.message} onRetry={() => void reports.refetch()} />
        ) : reports.isLoading ? (
          [0, 1, 2].map((i) => <Skeleton key={i} className="h-40 rounded-card" />)
        ) : items.length === 0 ? (
          <EmptyState title={EMPTY[status]} />
        ) : (
          <>
            {items.map((r) => (
              <ReportCard
                key={r.id}
                report={r}
                busy={working?.id === r.id ? working.status : null}
                onChange={(next) => void change(r, next)}
              />
            ))}
            <nav aria-label="Pages" className="flex items-center justify-between gap-3 pt-2">
              <Button variant="secondary" onClick={() => setPage((p) => p - 1)} disabled={page === 0}>Previous</Button>
              <span className="text-small text-muted">Page {page + 1}</span>
              <Button variant="secondary" onClick={() => setPage((p) => p + 1)} disabled={!hasNext}>Next</Button>
            </nav>
          </>
        )}
      </div>
    </div>
  );
}
