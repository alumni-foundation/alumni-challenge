"use client";

import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Lock, ShieldCheck, UserCheck, UserPlus } from "lucide-react";
import { Alert, Avatar, Badge, Button, Card, Chip, EmptyState, Spinner, VerifiedMark } from "@/components/ui";
import { useConnections, useMe, useProfile, useRoles, useWrite } from "@/lib/api/hooks";
import { canVerifyForSchool } from "@/lib/roles";
import { api, ApiError } from "@/lib/api/client";

export default function AlumniProfilePage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const me = useMe();
  const roles = useRoles();
  const profile = useProfile(id);
  const connections = useConnections();

  const connect = useWrite((addressee_id: string) => api("connections", { method: "POST", body: { addressee_id } }), [["connections"]]);
  const vouch = useWrite(() => api(`alumni/${id}/vouch`, { method: "POST" }), [["profile", id]]);
  const verify = useWrite((verified: boolean) => api(`alumni/${id}/verify`, { method: "PATCH", body: { verified } }), [["profile", id]]);

  if (profile.isLoading) return <Spinner label="Loading profile" />;
  if (profile.isError) {
    const notFound = profile.error instanceof ApiError && profile.error.status === 404;
    return (
      <EmptyState
        title={notFound ? "Profile not visible" : "Couldn't load this profile"}
        body={notFound ? "This member has set their profile to private, or it doesn't exist." : "Try again in a moment."}
        action={<Button variant="secondary" onClick={() => router.back()}><ArrowLeft className="size-4" /> Back</Button>}
      />
    );
  }
  const p = profile.data!;
  const isMe = p.user_id === me.data?.id;
  const existing = connections.data?.find((c) => c.other_user_id === p.user_id);
  const canVerify = !isMe && canVerifyForSchool(roles.data, p.school_id);

  return (
    <div className="mx-auto max-w-2xl">
      <button onClick={() => router.back()} className="mb-4 flex items-center gap-1 text-sm text-muted hover:text-ink">
        <ArrowLeft className="size-4" /> Back
      </button>
      {connect.isError && <div className="mb-4"><Alert>{connect.error.message}</Alert></div>}
      {vouch.isError && <div className="mb-4"><Alert>{vouch.error.message}</Alert></div>}

      <Card>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex items-center gap-4">
            <Avatar name={p.full_name} id={p.id} size={64} />
            <div>
              <h1 className="flex items-center gap-1.5 text-xl font-bold">
                {p.full_name} {p.verification_status === "verified" && <VerifiedMark />}
              </h1>
              <p className="text-muted">{[p.profession, p.company].filter(Boolean).join(" at ") || "Alumni member"}</p>
              <p className="text-sm text-muted">{[p.country, p.graduation_year && `Class of ${p.graduation_year}`].filter(Boolean).join(" · ")}</p>
            </div>
          </div>
          {!isMe && (
            <div className="flex flex-col gap-2">
              {existing ? (
                <Badge tone={existing.status === "accepted" ? "ok" : "neutral"}>
                  {existing.status === "accepted" ? "Connected" : existing.status === "pending" ? "Request pending" : existing.status}
                </Badge>
              ) : (
                <Button size="sm" loading={connect.isPending} onClick={() => connect.mutate(p.user_id)}>
                  <UserPlus className="size-4" /> Connect
                </Button>
              )}
              {p.verification_status !== "verified" && (
                <Button size="sm" variant="secondary" loading={vouch.isPending} onClick={() => vouch.mutate()}>
                  <UserCheck className="size-4" /> Vouch for them
                </Button>
              )}
            </div>
          )}
        </div>

        {p.bio && <p className="mt-4 text-sm leading-relaxed">{p.bio}</p>}

        {(p.skills.length > 0 || p.interests.length > 0) && (
          <div className="mt-4 space-y-2">
            {p.skills.length > 0 && (
              <div className="flex flex-wrap gap-1.5">{p.skills.map((s) => <Chip key={s}>{s}</Chip>)}</div>
            )}
            {p.interests.length > 0 && (
              <div className="flex flex-wrap gap-1.5">{p.interests.map((s) => <Chip key={s}>{s}</Chip>)}</div>
            )}
          </div>
        )}

        <div className="mt-4 flex flex-wrap items-center gap-3 border-t border-line pt-4 text-xs text-muted">
          <span className="flex items-center gap-1"><Lock className="size-3.5" /> {p.profile_visibility.replace("_", " ")}</span>
          <span>{p.vouch_count} vouch{p.vouch_count === 1 ? "" : "es"}</span>
        </div>
      </Card>

      {canVerify && p.verification_status !== "verified" && (
        <Card className="mt-4">
          <p className="mb-3 flex items-center gap-2 font-semibold"><ShieldCheck className="size-4 text-brand" /> School admin action</p>
          <Button size="sm" loading={verify.isPending} onClick={() => verify.mutate(true)}>Mark as verified</Button>
        </Card>
      )}
    </div>
  );
}
