"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useRef, useState } from "react";
import { Alert, Button, Field, Input, PasswordInput } from "@/components/ui";
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
  const [missing, setMissing] = useState<{ email?: string; password?: string }>({});
  const emailRef = useRef<HTMLInputElement>(null);
  const passwordRef = useRef<HTMLInputElement>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    // The button is never disabled: an empty field is explained here, and focus goes to the first one.
    const gaps = { email: email.trim() ? undefined : "Enter your email.", password: password ? undefined : "Enter your password." };
    setMissing(gaps);
    if (gaps.email || gaps.password) {
      (gaps.email ? emailRef : passwordRef).current?.focus();
      return;
    }
    setBusy(true);
    try {
      await authCall("login", { email: email.trim(), password });
      // Start from a clean slate so nothing from a previous person's session is shown.
      qc.clear();
      const roles = await api<Membership[]>("auth/me/roles");
      router.replace(next ?? landingFor(roles));
    } catch (err) {
      setError(loginErrorMessage(err));
      if (err instanceof ApiError && err.status === 401) {
        setPassword("");
        passwordRef.current?.focus();
      }
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-5" noValidate>
      <div>
        <h1 className="text-title">Welcome back</h1>
        <p className="mt-2 text-body text-ink">Sign in to your Alumni Challenge account.</p>
      </div>
      {params.get("reason") === "expired" && !error && <Alert tone="info">{SESSION_EXPIRED} Please log in again.</Alert>}
      {params.get("reset") === "1" && !error && <Alert tone="ok">Your password has been changed. Log in with the new one.</Alert>}
      {error && <Alert>{error}</Alert>}
      <Field label="Email" htmlFor="email" error={missing.email}>
        <Input ref={emailRef} id="email" type="email" autoComplete="email" inputMode="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
      </Field>
      <Field label="Password" htmlFor="password" error={missing.password}>
        <PasswordInput ref={passwordRef} id="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
      </Field>
      <div className="-mt-1 text-right">
        <Link href="/forgot-password" className="inline-flex min-h-11 items-center text-small font-medium text-brand-ink hover:underline">Forgot password?</Link>
      </div>
      <Button type="submit" variant="dark" className="w-full" loading={busy}>Log in</Button>
      <div className="flex items-center gap-3 text-caption text-muted" aria-hidden>
        <span className="h-px flex-1 bg-line-strong" />
        <span>or</span>
        <span className="h-px flex-1 bg-line-strong" />
      </div>
      <p className="text-center text-small text-ink">
        New here?{" "}
        <Link href="/register" className="inline-flex min-h-11 items-center font-semibold text-brand-ink hover:underline">Create account</Link>
      </p>
    </form>
  );
}

export default function LoginPage() {
  return <Suspense><LoginForm /></Suspense>;
}
