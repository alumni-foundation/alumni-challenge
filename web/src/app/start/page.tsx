"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Alert, Button, Spinner } from "@/components/ui";
import { api } from "@/lib/api/client";
import type { Membership } from "@/lib/api/types";
import { landingFor } from "@/lib/roles";

/** Signed-in people arrive here and are sent on to the right landing page for their roles. */
export default function Start() {
  const router = useRouter();
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    api<Membership[]>("auth/me/roles")
      .then((roles) => {
        if (!cancelled) router.replace(landingFor(roles));
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [router, attempt]);

  if (failed) {
    return (
      <main className="mx-auto max-w-md space-y-4 p-6">
        <Alert>We couldn’t load your account. Check your connection and try again.</Alert>
        <Button
          onClick={() => {
            setFailed(false);
            setAttempt((n) => n + 1);
          }}
        >
          Try again
        </Button>
      </main>
    );
  }
  return <Spinner label="Signing you in" />;
}
