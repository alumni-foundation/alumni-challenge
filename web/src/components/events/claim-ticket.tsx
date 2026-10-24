"use client";

import { useState } from "react";
import { Alert, Button, useToast } from "@/components/ui";
import { api, ApiError } from "@/lib/api/client";
import { friendlyError } from "@/lib/api/messages";

/**
 * For someone signed in who opened a ticket from an email: attach it to their account, so it is in My tickets.
 * The code goes in the request body, never in an address.
 */
export function ClaimTicket({ code }: { code: string }) {
  const toast = useToast();
  const [state, setState] = useState<"idle" | "busy" | "done">("idle");
  const [error, setError] = useState<string | null>(null);

  async function claim() {
    setState("busy");
    setError(null);
    try {
      await api("tickets/claim", { method: "POST", body: { code } });
      setState("done");
      toast("This ticket is now in your account.");
    } catch (e) {
      setState("idle");
      setError(e instanceof ApiError && e.code === "already_claimed" ? "This ticket already belongs to someone else’s account." : friendlyError(e));
    }
  }

  if (state === "done") return <Alert tone="ok">This ticket is now in your account. You will find it under My tickets.</Alert>;
  return (
    <div className="space-y-3">
      {error && <Alert>{error}</Alert>}
      <p className="text-small text-ink">Keep this ticket in your account, so you can find it again under My tickets.</p>
      <Button variant="dark" size="sm" loading={state === "busy"} onClick={claim}>Add to my account</Button>
    </div>
  );
}
