"use client";

import Link from "next/link";
import { useState } from "react";
import { Alert, Button, Field, Input } from "@/components/ui";
import { authCall } from "@/lib/api/client";
import { friendlyError } from "@/lib/api/messages";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await authCall("forgot-password", { email: email.trim() });
      // Always the same words, so this page never reveals whether an email has an account.
      setSent(true);
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setBusy(false);
    }
  }

  if (sent) {
    return (
      <div className="space-y-5">
        <h1 className="text-title">Check your email</h1>
        <Alert tone="ok">If that email has an account, we sent a link.</Alert>
        <p className="text-small text-ink">The link works for a short time. If nothing arrives, check your spam folder.</p>
        <Link href="/login" className="flex min-h-11 items-center justify-center text-small font-medium text-brand-ink hover:underline">Back to log in</Link>
      </div>
    );
  }
  return (
    <form onSubmit={submit} className="space-y-5" noValidate>
      <div>
        <h1 className="text-title">Forgot your password?</h1>
        <p className="mt-2 text-body text-ink">Enter your email and we will send you a link to choose a new one.</p>
      </div>
      {error && <Alert>{error}</Alert>}
      <Field label="Email" htmlFor="email">
        <Input id="email" type="email" autoComplete="email" inputMode="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
      </Field>
      <Button type="submit" variant="dark" className="w-full" loading={busy} disabled={!email.trim()}>Send me a link</Button>
      <Link href="/login" className="flex min-h-11 items-center justify-center text-small font-medium text-brand-ink hover:underline">Back to log in</Link>
    </form>
  );
}
