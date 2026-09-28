"use client";

import Link from "next/link";
import { useState } from "react";
import { Alert, Button, Field, Input } from "@/components/ui";
import { ApiError, authCall } from "@/lib/api/client";

export default function RegisterPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [adult, setAdult] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setFields({});
    try {
      await authCall("register", { email: email.trim(), password, confirm_18_or_older: adult });
      await authCall("login", { email: email.trim(), password });
      window.location.assign("/home");
    } catch (err) {
      if (err instanceof ApiError) {
        setFields(err.fieldErrors());
        setError(err.message);
      } else setError("Something went wrong.");
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4" noValidate>
      <div>
        <h1 className="text-2xl font-bold">Create your account</h1>
        <p className="mt-1 text-sm text-muted">Join the alumni community. It takes a minute.</p>
      </div>
      {error && <Alert>{error}</Alert>}
      <Field label="Email" htmlFor="email" error={fields.email}>
        <Input id="email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
      </Field>
      <Field label="Password" htmlFor="password" error={fields.password} hint="Use a long, unique password.">
        <Input id="password" type="password" autoComplete="new-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
      </Field>
      <label className="flex items-start gap-2 text-sm">
        <input type="checkbox" className="mt-0.5 size-4 accent-brand" checked={adult} onChange={(e) => setAdult(e.target.checked)} />
        <span>I confirm that I am 18 years old or older.</span>
      </label>
      <Button type="submit" className="w-full" loading={busy} disabled={!email || !password || !adult}>Create account</Button>
      <p className="text-center text-sm text-muted">
        Already registered? <Link href="/login" className="font-medium text-brand hover:underline">Sign in</Link>
      </p>
    </form>
  );
}
