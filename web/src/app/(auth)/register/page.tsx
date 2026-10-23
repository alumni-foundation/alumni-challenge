"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Alert, Button, Field, Input } from "@/components/ui";
import { ApiError, authCall } from "@/lib/api/client";
import { friendlyError } from "@/lib/api/messages";

const MIN_PASSWORD = 10;

export default function RegisterPage() {
  const router = useRouter();
  const qc = useQueryClient();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [adult, setAdult] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const issues: Record<string, string> = {};
    if (!email.trim()) issues.email = "Enter your email address.";
    if (password.length < MIN_PASSWORD) issues.password = `Use at least ${MIN_PASSWORD} characters.`;
    setFields(issues);
    if (Object.keys(issues).length) return;

    setBusy(true);
    try {
      await authCall("register", { email: email.trim(), password, confirm_18_or_older: adult });
      await authCall("login", { email: email.trim(), password });
      qc.clear();
      router.replace("/onboarding?welcome=1");
    } catch (err) {
      if (err instanceof ApiError) setFields(err.fieldErrors());
      setError(friendlyError(err));
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-5" noValidate>
      <div>
        <h1 className="text-title">Create your account</h1>
        <p className="mt-1 text-small text-muted">Join the alumni community. It takes a minute.</p>
      </div>
      {error && <Alert>{error}</Alert>}
      <Field label="Email" htmlFor="email" error={fields.email}>
        <Input id="email" type="email" autoComplete="email" inputMode="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
      </Field>
      <Field label="Password" htmlFor="password" error={fields.password} hint={`At least ${MIN_PASSWORD} characters.`}>
        <Input id="password" type="password" autoComplete="new-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
      </Field>
      <label className="flex min-h-11 items-center gap-3 text-small">
        <input
          type="checkbox"
          className="size-5 shrink-0 accent-brand"
          checked={adult}
          onChange={(e) => setAdult(e.target.checked)}
        />
        <span>I am 18 or older.</span>
      </label>
      <Button type="submit" className="w-full" loading={busy} disabled={!email || !password || !adult}>Create account</Button>
      <p className="text-center text-caption text-muted">
        By creating an account you agree to our{" "}
        <Link href="/terms" className="font-medium text-brand-ink hover:underline">Terms</Link> and{" "}
        <Link href="/privacy" className="font-medium text-brand-ink hover:underline">Privacy Policy</Link>.
      </p>
      <p className="text-center text-small text-muted">
        Already registered? <Link href="/login" className="font-medium text-brand-ink hover:underline">Log in</Link>
      </p>
    </form>
  );
}
