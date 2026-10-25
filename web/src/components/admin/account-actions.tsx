"use client";

import { Ban, RotateCcw } from "lucide-react";
import { useState } from "react";
import { Button, ReasonDialog, useToast } from "@/components/ui";
import { api } from "@/lib/api/client";
import { useRoles, useWrite } from "@/lib/api/hooks";
import { canModerate, isPlatformAdmin } from "@/lib/roles";

type Which = "suspend" | "reactivate" | null;

/**
 * Suspend and Reactivate for one account, each behind a dialog that asks for a reason in plain words.
 * The API takes the person's user id; it will refuse if the role rules say no (a moderator cannot suspend
 * another moderator or an admin), and the dialog shows its message.
 * `resolveUserId` lets a caller that only has a profile id (a report) look the user up when a button is pressed.
 */
export function AccountActions({
  userId,
  resolveUserId,
  name,
  onDone,
  size = "sm",
  only,
}: {
  userId?: string;
  resolveUserId?: () => Promise<string>;
  name: string;
  onDone?: (change: "suspended" | "reactivated") => void;
  size?: "sm" | "md";
  /** Show just one of the two buttons (a report only offers Suspend). */
  only?: "suspend" | "reactivate";
}) {
  const roles = useRoles();
  const toast = useToast();
  const [which, setWhich] = useState<Which>(null);
  const [id, setId] = useState<string | undefined>(userId);
  const [looking, setLooking] = useState<Which>(null);
  const call = useWrite(
    ({ to, reason }: { to: "suspend" | "reactivate"; reason: string }) => api(`users/${id}/${to}`, { method: "POST", body: { reason } }),
    [["reports"], ["audit"], ["directory"], ["org-members"], ["roster"]],
  );

  async function open(w: "suspend" | "reactivate") {
    if (!id && resolveUserId) {
      setLooking(w);
      try {
        setId(await resolveUserId());
      } catch {
        toast("We couldn’t find this person’s account. Their profile may be hidden from you now.", "info");
        setLooking(null);
        return;
      }
      setLooking(null);
    }
    setWhich(w);
  }

  const canSuspend = canModerate(roles.data) && only !== "reactivate";
  const canReactivate = isPlatformAdmin(roles.data) && only !== "suspend";
  if (!canSuspend && !canReactivate) return null;

  return (
    <>
      {canSuspend && (
        <Button variant="danger" size={size} loading={looking === "suspend"} onClick={() => void open("suspend")}>
          <Ban className="size-4" aria-hidden /> Suspend
        </Button>
      )}
      {canReactivate && (
        <Button variant="secondary" size={size} loading={looking === "reactivate"} onClick={() => void open("reactivate")}>
          <RotateCcw className="size-4" aria-hidden /> Reactivate
        </Button>
      )}
      <ReasonDialog
        open={which === "suspend"}
        title={`Suspend ${name}?`}
        body="They will be signed out straight away and their profile will be hidden from other members. Say why, so the activity log explains it. You can reactivate the account later."
        confirmLabel="Suspend account"
        danger
        onClose={() => setWhich(null)}
        onSubmit={async (reason) => {
          await call.mutateAsync({ to: "suspend", reason });
          toast(`${name}’s account is suspended.`);
          onDone?.("suspended");
        }}
      />
      <ReasonDialog
        open={which === "reactivate"}
        title={`Reactivate ${name}?`}
        body="They will be able to sign in again and their profile will show again. Say why, so the activity log explains it."
        confirmLabel="Reactivate account"
        onClose={() => setWhich(null)}
        onSubmit={async (reason) => {
          await call.mutateAsync({ to: "reactivate", reason });
          toast(`${name}’s account is active again.`);
          onDone?.("reactivated");
        }}
      />
    </>
  );
}
