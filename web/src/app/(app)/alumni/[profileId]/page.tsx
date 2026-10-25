"use client";

import { ArrowLeft, Ban, Flag, Gavel, Pencil, RotateCcw, ShieldCheck, ShieldOff, UserCheck, UserMinus, UserPlus, UserX, X } from "lucide-react";
import Link from "next/link";
import { MessageButton } from "@/components/messages/message-button";
import { useParams, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import {
  Alert, Avatar, Badge, Button, Card, Chip, ConfirmDialog, EmptyState, LinkButton, ReasonDialog, Skeleton, VerifiedMark, useToast,
} from "@/components/ui";
import { api, ApiError } from "@/lib/api/client";
import { friendlyError } from "@/lib/api/messages";
import { useBlocked, useConnections, useMe, useMyProfile, useOrg, useProfile, useRoles, useWrite } from "@/lib/api/hooks";
import { canModerate, canVerifyForSchool, isPlatformAdmin } from "@/lib/roles";

const VOUCHES_NEEDED = 3;

type Dialog = "block" | "remove" | "report" | "suspend" | "reactivate" | null;

function ProfileView() {
  const { profileId } = useParams<{ profileId: string }>();
  const fromReport = useSearchParams().get("report") !== null;
  const toast = useToast();
  const me = useMe();
  const roles = useRoles();
  const profile = useProfile(profileId);
  const myProfile = useMyProfile();
  const connections = useConnections();
  const blocked = useBlocked();
  const school = useOrg(profile.data?.school_id ?? "");
  const [dialog, setDialog] = useState<Dialog>(null);
  const [problem, setProblem] = useState<string | null>(null);

  // Whatever an action changes, these are refreshed afterwards.
  const refresh = [["connections"], ["blocked"], ["profile", profileId], ["directory"]];
  const connect = useWrite((userId: string) => api("connections", { method: "POST", body: { addressee_id: userId } }), refresh);
  const cancel = useWrite((id: string) => api(`connections/${id}`, { method: "DELETE" }), refresh);
  const accept = useWrite((id: string) => api(`connections/${id}/accept`, { method: "PATCH" }), refresh);
  const decline = useWrite((id: string) => api(`connections/${id}/decline`, { method: "PATCH" }), refresh);
  const vouch = useWrite(() => api(`alumni/${profileId}/vouch`, { method: "POST" }), refresh);
  const verify = useWrite((verified: boolean) => api(`alumni/${profileId}/verify`, { method: "PATCH", body: { verified } }), refresh);
  const unblock = useWrite((id: string) => api(`connections/${id}/unblock`, { method: "POST" }), refresh);
  const suspend = useWrite(({ userId, reason }: { userId: string; reason: string }) => api(`users/${userId}/suspend`, { method: "POST", body: { reason } }), refresh);
  const reactivate = useWrite(({ userId, reason }: { userId: string; reason: string }) => api(`users/${userId}/reactivate`, { method: "POST", body: { reason } }), refresh);
  const block = useWrite((userId: string) => api("connections/block", { method: "POST", body: { user_id: userId } }), refresh);

  // One place to run an action: clear the last problem, show the server's words if it refuses.
  async function act(fn: () => Promise<unknown>, success: string) {
    setProblem(null);
    try {
      await fn();
      toast(success);
    } catch (e) {
      setProblem(friendlyError(e));
    }
  }

  if (profile.isLoading || me.isLoading) {
    return (
      <div className="mx-auto max-w-2xl space-y-4" role="status" aria-label="Loading profile">
        <Skeleton className="h-6 w-32" />
        <Skeleton className="h-64 rounded-card" />
      </div>
    );
  }
  if (profile.isError) {
    // Hidden, suspended and non-existent profiles all answer 404 on purpose. Never say which.
    const unavailable = profile.error instanceof ApiError && profile.error.status === 404;
    return (
      <div className="mx-auto max-w-2xl">
        <EmptyState
          title={unavailable ? "This profile isn’t available." : "We couldn’t load this profile."}
          body={unavailable ? undefined : "Check your connection and try again."}
          action={
            unavailable ? (
              <LinkButton href="/directory" variant="secondary">Back to the directory</LinkButton>
            ) : (
              <Button variant="secondary" onClick={() => void profile.refetch()}>Try again</Button>
            )
          }
        />
      </div>
    );
  }

  const p = profile.data!;
  const myId = me.data?.id;
  const isMe = p.user_id === myId;
  // Declined and removed rows are history, not a relationship.
  const link = connections.data?.find((c) => c.other_user_id === p.user_id && (c.status === "pending" || c.status === "accepted"));
  const blockedRow = blocked.data?.find((c) => c.other_user_id === p.user_id);
  const canVerify = !isMe && canVerifyForSchool(roles.data, p.school_id);
  const canSuspend = !isMe && canModerate(roles.data);
  const canReactivate = !isMe && isPlatformAdmin(roles.data);
  const verified = p.verification_status === "verified";
  const work = [p.profession, p.company].filter(Boolean).join(" at ");
  const where = [school.data?.name, p.graduation_year && `Class of ${p.graduation_year}`, p.country].filter(Boolean).join(" · ");

  let relationship: React.ReactNode = null;
  if (blockedRow) {
    relationship = (
      <>
        <Badge>You blocked this person</Badge>
        <Button variant="secondary" loading={unblock.isPending} onClick={() => act(() => unblock.mutateAsync(blockedRow.id), "Unblocked.")}>Unblock</Button>
      </>
    );
  } else if (!link) {
    relationship = (
      <Button loading={connect.isPending} onClick={() => act(() => connect.mutateAsync(p.user_id), "Request sent.")}>
        <UserPlus className="size-4" aria-hidden /> Connect
      </Button>
    );
  } else if (link.status === "accepted") {
    relationship = (
      <>
        <Badge tone="ok">Connected</Badge>
        <MessageButton size="md" />
        <Button variant="secondary" onClick={() => setDialog("remove")}><UserMinus className="size-4" aria-hidden /> Remove connection</Button>
      </>
    );
  } else if (link.requester_id === myId) {
    relationship = (
      <>
        <Badge>Request sent</Badge>
        <Button variant="secondary" loading={cancel.isPending} onClick={() => act(() => cancel.mutateAsync(link.id), "Request cancelled.")}>Cancel request</Button>
      </>
    );
  } else {
    relationship = (
      <>
        <Button loading={accept.isPending} onClick={() => act(() => accept.mutateAsync(link.id), "You are now connected.")}>Accept</Button>
        <Button variant="secondary" loading={decline.isPending} onClick={() => act(() => decline.mutateAsync(link.id), "Request declined.")}>Decline</Button>
      </>
    );
  }

  return (
    <div className="mx-auto max-w-2xl">
      <Link href="/directory" className="mb-4 inline-flex min-h-11 items-center gap-1.5 text-small text-muted hover:text-ink">
        <ArrowLeft className="size-4" aria-hidden /> Directory
      </Link>

      {problem && (
        <div className="mb-4">
          <Alert>
            <span className="flex items-start justify-between gap-3">
              {problem}
              <button type="button" onClick={() => setProblem(null)} aria-label="Dismiss message" className="-m-2 inline-flex size-10 shrink-0 items-center justify-center rounded-full hover:bg-black/5">
                <X className="size-4" aria-hidden />
              </button>
            </span>
          </Alert>
        </div>
      )}

      <Card>
        <div className="flex items-start gap-4">
          <Avatar name={p.full_name} id={p.id} size={72} src={p.avatar_url} />
          <div className="min-w-0">
            <h1 className="flex flex-wrap items-center gap-x-2 text-title">
              <span className="break-words">{p.full_name}</span>
              {verified && <VerifiedMark />}
            </h1>
            {work && <p className="text-body">{work}</p>}
            {where && <p className="text-small text-muted">{where}</p>}
          </div>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-2">
          <Badge tone={verified ? "blue" : "neutral"}>{verified ? "Verified alumnus" : "Not verified yet"}</Badge>
          {!verified && <span className="text-caption text-muted">{p.vouch_count} of {VOUCHES_NEEDED} vouches</span>}
        </div>

        {p.bio && <p className="mt-4 whitespace-pre-line text-body">{p.bio}</p>}

        {p.skills.length > 0 && (
          <section className="mt-5" aria-label="Skills">
            <h2 className="mb-2 text-small font-semibold">Skills</h2>
            <div className="flex flex-wrap gap-2">{p.skills.map((s) => <Chip key={s}>{s}</Chip>)}</div>
          </section>
        )}
        {p.interests.length > 0 && (
          <section className="mt-4" aria-label="Interests">
            <h2 className="mb-2 text-small font-semibold">Interests</h2>
            <div className="flex flex-wrap gap-2">{p.interests.map((s) => <Chip key={s}>{s}</Chip>)}</div>
          </section>
        )}

        <div className="mt-6 flex flex-col gap-3 border-t border-line pt-5 sm:flex-row sm:flex-wrap sm:items-center">
          {isMe ? (
            <LinkButton href="/profile"><Pencil className="size-4" aria-hidden /> Edit profile</LinkButton>
          ) : myProfile.data === null ? (
            // Staff accounts often have no member profile of their own, so there is nobody to connect as.
            <p className="text-small text-muted">You are viewing this as staff. Create your own member profile to connect, vouch or report as a member.</p>
          ) : (
            <>
              {relationship}
              <span className="hidden flex-1 sm:block" />
              {!verified && (
                <Button variant="secondary" loading={vouch.isPending} onClick={() => act(() => vouch.mutateAsync(undefined), "Thank you for vouching.")}>
                  <UserCheck className="size-4" aria-hidden /> Vouch
                </Button>
              )}
              <Button variant="ghost" onClick={() => setDialog("report")}><Flag className="size-4" aria-hidden /> Report</Button>
              {!blockedRow && <Button variant="ghost" onClick={() => setDialog("block")}><UserX className="size-4" aria-hidden /> Block</Button>}
            </>
          )}
        </div>
      </Card>

      {canVerify && (
        <Card className="mt-4">
          <p className="mb-1 flex items-center gap-2 font-semibold"><ShieldCheck className="size-4 text-brand-ink" aria-hidden /> School verification</p>
          <p className="mb-3 text-small text-muted">
            {verified ? "This person is verified. You can take the verification away." : "Confirm that this person went to the school."}
          </p>
          {verified ? (
            <Button variant="danger" loading={verify.isPending} onClick={() => act(() => verify.mutateAsync(false), "Verification removed.")}>
              <ShieldOff className="size-4" aria-hidden /> Remove verification
            </Button>
          ) : (
            <Button loading={verify.isPending} onClick={() => act(() => verify.mutateAsync(true), "Verified.")}>
              <ShieldCheck className="size-4" aria-hidden /> Verify
            </Button>
          )}
        </Card>
      )}

      {(canSuspend || canReactivate) && (
        <Card className="mt-4 space-y-3">
          <p className="flex items-center gap-2 font-semibold"><Gavel className="size-4 text-brand-ink" aria-hidden /> Moderation</p>
          {fromReport && (
            <Alert tone="info">You can see this profile because of an open report. When the report is closed, it will be hidden from you again.</Alert>
          )}
          <p className="text-small text-muted">
            Suspending an account signs the person out and hides their profile. A moderator can’t suspend another moderator or an admin. {canReactivate ? "" : "Only an admin can reactivate an account."}
          </p>
          <div className="flex flex-col gap-2 sm:flex-row">
            {canSuspend && <Button variant="danger" onClick={() => setDialog("suspend")}><Ban className="size-4" aria-hidden /> Suspend account</Button>}
            {canReactivate && <Button variant="secondary" onClick={() => setDialog("reactivate")}><RotateCcw className="size-4" aria-hidden /> Reactivate account</Button>}
          </div>
        </Card>
      )}

      <ReasonDialog
        open={dialog === "suspend"}
        title={`Suspend ${p.full_name}?`}
        body="They will be signed out and their profile hidden. Say why, so the activity log explains it."
        label="Reason"
        confirmLabel="Suspend account"
        danger
        onClose={() => setDialog(null)}
        onSubmit={async (reason) => {
          await suspend.mutateAsync({ userId: p.user_id, reason });
          toast("Account suspended.");
        }}
      />
      <ReasonDialog
        open={dialog === "reactivate"}
        title={`Reactivate ${p.full_name}?`}
        body="They will be able to sign in again. Say why, so the activity log explains it."
        label="Reason"
        confirmLabel="Reactivate account"
        onClose={() => setDialog(null)}
        onSubmit={async (reason) => {
          await reactivate.mutateAsync({ userId: p.user_id, reason });
          toast("Account reactivated.");
        }}
      />

      <ConfirmDialog
        open={dialog === "remove"}
        title="Remove this connection?"
        body={<>You and {p.full_name} will no longer be connected. You can send a new request later.</>}
        confirmLabel="Remove connection"
        danger
        onClose={() => setDialog(null)}
        onConfirm={async () => {
          if (!link) return;
          await cancel.mutateAsync(link.id);
          toast("Connection removed.");
        }}
      />
      <ConfirmDialog
        open={dialog === "block"}
        title={`Block ${p.full_name}?`}
        body={<>They won’t be able to find you or contact you, and any connection between you ends. You can unblock them later from Settings, but you would need to connect again.</>}
        confirmLabel="Block"
        danger
        onClose={() => setDialog(null)}
        onConfirm={async () => {
          await block.mutateAsync(p.user_id);
          toast("Blocked.");
        }}
      />
      <ReasonDialog
        open={dialog === "report"}
        title={`Report ${p.full_name}`}
        body="Tell our moderators what is wrong. Only moderators will see this."
        label="What happened?"
        confirmLabel="Send report"
        danger
        onClose={() => setDialog(null)}
        onSubmit={async (reason) => {
          try {
            await api("reports", { method: "POST", body: { target_type: "profile", target_id: p.id, reason } });
          } catch (e) {
            if (e instanceof ApiError && e.status === 409) throw new ApiError(409, e.code, "You already reported this.");
            throw e;
          }
          toast("Thank you. Our moderators will take a look.");
        }}
      />
    </div>
  );
}

export default function AlumniProfilePage() {
  return <Suspense><ProfileView /></Suspense>;
}
