"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { Alert, Button, Field, Input } from "@/components/ui";
import { authCall } from "@/lib/api/client";
import { friendlyError } from "@/lib/api/messages";

const MIN_PASSWORD = 10;

function ResetForm() {
  const token = useSearchParams().get("token");
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [again, setAgain] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (!token) {
    return (
      <div className="space-y-5">
        <h1 className="text-title">This link isn’t complete</h1>
        <Alert>Open the link from your email again, or ask for a new one.</Alert>
        <Link href="/forgot-password" className="flex min-h-11 items-center justify-center text-small font-medium text-brand-ink hover:underline">Ask for a new link</Link>
      </div>
    );
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const issues: Record<string, string> = {};
    if (password.length < MIN_PASSWORD) issues.password = `Use at least ${MIN_PASSWORD} characters.`;
    if (again !== password) issues.again = "The two passwords don’t match.";
    setFieldErrors(issues);
    if (Object.keys(issues).length) return;

    setBusy(true);
    try {
      await authCall("reset-password", { token, new_password: password });
      router.replace("/login?reset=1");
    } catch (err) {
      setError(friendlyError(err));
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-5" noValidate>
      <div>
        <h1 className="text-title">Choose a new password</h1>
        <p className="mt-1 text-small text-muted">Use at least {MIN_PASSWORD} characters.</p>
      </div>
      {error && (
        <Alert>
          {error}{" "}
          <Link href="/forgot-password" className="font-medium underline">Ask for a new link</Link>
        </Alert>
      )}
      <Field label="New password" htmlFor="password" error={fieldErrors.password}>
        <Input id="password" type="password" autoComplete="new-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
      </Field>
      <Field label="New password again" htmlFor="again" error={fieldErrors.again}>
        <Input id="again" type="password" autoComplete="new-password" required value={again} onChange={(e) => setAgain(e.target.value)} />
      </Field>
      <Button type="submit" className="w-full" loading={busy} disabled={!password || !again}>Set new password</Button>
    </form>
  );
}

export default function ResetPasswordPage() {
  return <Suspense><ResetForm /></Suspense>;
}
