"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { Alert, Button, Field, Input } from "@/components/ui";
import { ApiError, api, authCall, safeNext } from "@/lib/api/client";
import { SESSION_EXPIRED, loginErrorMessage } from "@/lib/api/messages";
import type { Membership } from "@/lib/api/types";
import { landingFor } from "@/lib/roles";

function LoginForm() {
  const params = useSearchParams();
  const next = safeNext(params.get("next"));
  const router = useRouter();
  const qc = useQueryClient();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await authCall("login", { email: email.trim(), password });
      // Start from a clean slate so nothing from a previous person's session is shown.
      qc.clear();
      const roles = await api<Membership[]>("auth/me/roles");
      router.replace(next ?? landingFor(roles));
    } catch (err) {
      setError(loginErrorMessage(err));
      if (err instanceof ApiError && err.status === 401) setPassword("");
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-5" noValidate>
      <div>
        <h1 className="text-title">Welcome back</h1>
        <p className="mt-1 text-small text-muted">Sign in to your Alumni Challenge account.</p>
      </div>
      {params.get("reason") === "expired" && !error && <Alert tone="info">{SESSION_EXPIRED} Please log in again.</Alert>}
      {params.get("reset") === "1" && !error && <Alert tone="ok">Your password has been changed. Log in with the new one.</Alert>}
      {error && <Alert>{error}</Alert>}
      <Field label="Email" htmlFor="email">
        <Input id="email" type="email" autoComplete="email" inputMode="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
      </Field>
      <Field label="Password" htmlFor="password">
        <Input id="password" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
      </Field>
      <Button type="submit" className="w-full" loading={busy} disabled={!email || !password}>Log in</Button>
      <div className="flex flex-col items-center gap-2 text-small text-muted sm:flex-row sm:justify-between">
        <Link href="/forgot-password" className="inline-flex min-h-11 items-center font-medium text-brand-ink hover:underline">Forgot password?</Link>
        <Link href="/register" className="inline-flex min-h-11 items-center font-medium text-brand-ink hover:underline">
          New here? Create account
        </Link>
      </div>
    </form>
  );
}

export default function LoginPage() {
  return <Suspense><LoginForm /></Suspense>;
}
