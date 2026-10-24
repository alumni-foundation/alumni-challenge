"use client";

import { CheckCircle2, XCircle } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { Alert, Button, LinkButton, Spinner, useToast } from "@/components/ui";
import { api, authCall, isSignedIn } from "@/lib/api/client";
import { friendlyError } from "@/lib/api/messages";

type State =
  | { kind: "working" }
  | { kind: "done" }
  | { kind: "failed"; message: string; signedIn: boolean };

function VerifyEmail() {
  const token = useSearchParams().get("token");
  const [state, setState] = useState<State>({ kind: "working" });
  const [resending, setResending] = useState(false);
  const toast = useToast();
  // A link works once, so make sure React's development double-run doesn't spend it twice.
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    if (!token) {
      void isSignedIn().then((signedIn) =>
        setState({ kind: "failed", message: "This link isn’t complete.", signedIn }),
      );
      return;
    }
    authCall("verify-email", { token })
      .then(() => setState({ kind: "done" }))
      .catch(async (err) => setState({ kind: "failed", message: friendlyError(err), signedIn: await isSignedIn() }));
  }, [token]);

  async function resend() {
    setResending(true);
    try {
      await api("auth/email/verify/request", { method: "POST" });
      toast("We sent you a new link.");
    } catch (err) {
      toast(friendlyError(err), "info");
    } finally {
      setResending(false);
    }
  }

  if (state.kind === "working") return <Spinner label="Checking your link" />;

  if (state.kind === "done") {
    return (
      <div className="space-y-5 text-center">
        <CheckCircle2 className="mx-auto size-12 text-ok" aria-hidden />
        <h1 className="text-title">Email verified</h1>
        <p className="text-small text-ink">Thank you. Your email address is confirmed.</p>
        <LinkButton href="/start" variant="dark" className="w-full">Continue</LinkButton>
      </div>
    );
  }
  return (
    <div className="space-y-5">
      <div className="text-center">
        <XCircle className="mx-auto size-12 text-brand-ink" aria-hidden />
        <h1 className="mt-3 text-title">We couldn’t verify that link</h1>
      </div>
      <Alert>{state.message}</Alert>
      {state.signedIn ? (
        <Button variant="dark" className="w-full" onClick={resend} loading={resending}>Send me a new link</Button>
      ) : (
        <p className="text-center text-small text-ink">
          <Link href="/login" className="font-medium text-brand-ink hover:underline">Log in</Link> to ask for a new link.
        </p>
      )}
    </div>
  );
}

export default function VerifyEmailPage() {
  return <Suspense><VerifyEmail /></Suspense>;
}
