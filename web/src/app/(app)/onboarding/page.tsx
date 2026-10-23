"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { NEW_PROFILE, ProfileFields, profileBody, validateProfile, type ProfileValues } from "@/components/profile/profile-fields";
import { Alert, Button } from "@/components/ui";
import { ApiError, api } from "@/lib/api/client";
import { friendlyError } from "@/lib/api/messages";
import { useOrgs } from "@/lib/api/hooks";

function OnboardingForm() {
  const router = useRouter();
  const qc = useQueryClient();
  const welcome = useSearchParams().get("welcome") === "1";
  const schools = useOrgs("school");

  const [values, setValues] = useState<ProfileValues>(NEW_PROFILE);
  const [fields, setFields] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const issues = validateProfile(values);
    setFields(issues);
    if (Object.keys(issues).length) return;

    setBusy(true);
    try {
      await api("alumni/profile", { method: "POST", body: profileBody(values) });
    } catch (err) {
      if (err instanceof ApiError) setFields(err.fieldErrors());
      setError(friendlyError(err));
      setBusy(false);
      return;
    }

    // The profile exists now. Skills and interests are extras: if one fails, say so on the
    // profile page, but carry on.
    const missing: string[] = [];
    for (const [path, names, label] of [
      ["alumni/profile/skills", values.skills, "skills"],
      ["alumni/profile/interests", values.interests, "interests"],
    ] as const) {
      if (names.length === 0) continue;
      try {
        await api(path, { method: "PUT", body: { names } });
      } catch {
        missing.push(label);
      }
    }
    await qc.invalidateQueries({ queryKey: ["profile"] });
    router.replace(missing.length ? `/profile?saved=partial&missing=${missing.join(",")}` : "/start");
  }

  return (
    <form onSubmit={submit} className="space-y-6" noValidate>
      <div>
        <h1 className="text-title">Set up your alumni profile</h1>
        <p className="mt-1 text-small text-muted">This is what other members will see. You can change it any time.</p>
      </div>
      {welcome && <Alert tone="ok">Your account is ready. Check your email to verify your address.</Alert>}
      {error && <Alert>{error}</Alert>}
      <ProfileFields values={values} onChange={setValues} errors={fields} schools={schools} />
      <Button type="submit" className="w-full" loading={busy}>Create my profile</Button>
    </form>
  );
}

export default function Onboarding() {
  return <Suspense><OnboardingForm /></Suspense>;
}
