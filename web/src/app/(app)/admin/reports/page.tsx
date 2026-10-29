"use client";

import { Ban } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { Alert, Badge, Button, Card, ConfirmDialog, EmptyState, ErrorState, PageHeader, ReasonDialog, Skeleton, Tabs, useToast } from "@/components/ui";
import { api } from "@/lib/api/client";
import { friendlyError } from "@/lib/api/messages";
import { REPORTS_PAGE_SIZE, useProfile, useReports, useRoles, useWrite } from "@/lib/api/hooks";
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

function ReportCard({ report, onChange, busy }: { report: Report; onChange: (status: ReportStatus) => void; busy: ReportStatus | null }) {
  const toast = useToast();
  const isProfile = report.target_type === "profile";
  const active = report.status === "open" || report.status === "reviewing";
  const [dialog, setDialog] = useState<"dismiss" | "suspend" | null>(null);
  // A moderator can open the reported profile while its report is open or being reviewed; that gives the account to suspend.
  const profile = useProfile(report.target_id, isProfile && active);
  const suspend = useWrite(
    ({ userId, reason }: { userId: string; reason: string }) => api(`users/${userId}/suspend`, { method: "POST", body: { reason } }),
    [["reports"], ["audit"]],
  );
  return (
    <Card large className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={TONE[report.status]}>{TABS.find((t) => t.value === report.status)?.label}</Badge>
        <span className="text-small font-medium capitalize">{report.target_type}</span>
        <span className="text-caption text-muted">{formatDate(report.created_at)}</span>
      </div>
      <p className="whitespace-pre-line break-words text-body">{report.reason}</p>
      <p className="text-small text-muted" title={`Reporter ${report.reporter_user_id}`}>
        Reported by a member
        {report.reviewed_by ? " · taken on by a moderator" : " · not reviewed yet"}
        {report.resolved_at && <> · closed {formatDate(report.resolved_at)}</>}
      </p>
      <div className="flex flex-col gap-2 border-t border-line pt-3 sm:flex-row sm:flex-wrap">
        {isProfile && active ? (
          <Link
            href={`/alumni/${report.target_id}?report=${report.id}`}
            className="inline-flex h-11 items-center justify-center rounded-full border border-line-strong bg-transparent px-5 text-small font-medium hover:bg-sunken focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink sm:h-9 sm:px-4"
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
            <Button variant="ghost" size="sm" loading={busy === "dismissed"} disabled={busy !== null} onClick={() => setDialog("dismiss")}>Dismiss</Button>
          </>
        )}
        {isProfile && active && (
          <Button
            variant="danger"
            size="sm"
            disabled={!profile.data}
            title={profile.data ? undefined : profile.isError ? "This profile can’t be opened, so it can’t be suspended from here." : "Loading the reported profile…"}
            onClick={() => setDialog("suspend")}
          >
            <Ban className="size-4" aria-hidden /> Suspend account
          </Button>
        )}
      </div>

      <ConfirmDialog
        open={dialog === "dismiss"}
        title="Dismiss this report?"
        body="It moves to Dismissed and the profile is hidden from you again. The system keeps no written note with a dismissal, only the status."
        confirmLabel="Dismiss report"
        onClose={() => setDialog(null)}
        onConfirm={async () => onChange("dismissed")}
      />
      <ReasonDialog
        open={dialog === "suspend"}
        title={`Suspend ${profile.data?.full_name ?? "this account"}?`}
        body="They will be signed out and their profile hidden. The report stays open until you resolve it. Say why, so the activity log explains it."
        confirmLabel="Suspend account"
        danger
        onClose={() => setDialog(null)}
        onSubmit={async (reason) => {
          if (!profile.data) return;
          await suspend.mutateAsync({ userId: profile.data.user_id, reason });
          toast("Account suspended.");
        }}
      />
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
      <Tabs<ReportStatus> pills label="Report status" tabs={TABS} value={status} onChange={(s) => { setStatus(s); setPage(0); }} />
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
