"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { AvatarEditor } from "@/components/profile/avatar-editor";
import { ProfileFields, profileBody, validateProfile, valuesFromProfile, type ProfileValues } from "@/components/profile/profile-fields";
import { Alert, Button, Card, ErrorState, PageHeader, Skeleton, VerifiedMark, useToast } from "@/components/ui";
import { ApiError, api } from "@/lib/api/client";
import { friendlyError } from "@/lib/api/messages";
import { useMyProfile, useOrgs } from "@/lib/api/hooks";
import type { Profile } from "@/lib/api/types";

const VOUCHES_NEEDED = 3;

function ProfileEditor({ profile }: { profile: Profile }) {
  const qc = useQueryClient();
  const toast = useToast();
  const params = useSearchParams();
  const schools = useOrgs("school");
  const [values, setValues] = useState<ProfileValues>(() => valuesFromProfile(profile));
  const [fields, setFields] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [partial, setPartial] = useState<string[]>(
    params.get("saved") === "partial" ? (params.get("missing") ?? "").split(",").filter(Boolean) : [],
  );
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const issues = validateProfile(values);
    setFields(issues);
    if (Object.keys(issues).length) return;

    setBusy(true);
    try {
      await api("alumni/profile", { method: "PATCH", body: profileBody(values) });
    } catch (err) {
      if (err instanceof ApiError) setFields(err.fieldErrors());
      setError(friendlyError(err));
      setBusy(false);
      return;
    }
    // Each list replaces the old one, so send both even when only one changed.
    const missing: string[] = [];
    for (const [path, names, label] of [
      ["alumni/profile/skills", values.skills, "skills"],
      ["alumni/profile/interests", values.interests, "interests"],
    ] as const) {
      try {
        await api(path, { method: "PUT", body: { names } });
      } catch {
        missing.push(label);
      }
    }
    await qc.invalidateQueries({ queryKey: ["profile"] });
    setPartial(missing);
    setBusy(false);
    if (missing.length === 0) toast("Profile saved.");
  }

  const verified = profile.verification_status === "verified";

  return (
    <div className="mx-auto max-w-2xl">
      <PageHeader title="My profile" subtitle="This is what other members see about you." />

      {partial.length > 0 && (
        <div className="mb-4">
          <Alert tone="warn">
            Your profile is saved, but we couldn’t save your {partial.join(" and ")}. Check the list below and save again.
          </Alert>
        </div>
      )}

      <Card className="mb-6">
        <AvatarEditor profile={profile} />
        <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-line pt-4 text-small">
          {verified ? (
            <span className="inline-flex items-center gap-1.5 font-medium">Verified alumnus <VerifiedMark /></span>
          ) : (
            <span className="text-muted">Not verified yet · {profile.vouch_count} of {VOUCHES_NEEDED} vouches. <Link href="/home" className="font-medium text-brand-ink hover:underline">How to get verified</Link></span>
          )}
        </div>
      </Card>

      <form onSubmit={submit} className="space-y-6" noValidate>
        {error && <Alert>{error}</Alert>}
        <ProfileFields values={values} onChange={setValues} errors={fields} schools={schools} />
        <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
          <Button
            variant="secondary"
            onClick={() => {
              setValues(valuesFromProfile(profile));
              setFields({});
              setError(null);
            }}
            disabled={busy}
          >
            Cancel
          </Button>
          <Button type="submit" loading={busy}>Save</Button>
        </div>
      </form>
    </div>
  );
}

function ProfileLoader() {
  const profile = useMyProfile();
  if (profile.isError) return <ErrorState onRetry={() => void profile.refetch()} />;
  if (profile.isLoading || !profile.data) {
    return (
      <div className="mx-auto max-w-2xl space-y-4" role="status" aria-label="Loading your profile">
        <Skeleton className="h-40 rounded-card" />
        <Skeleton className="h-80 rounded-card" />
      </div>
    );
  }
  // Keyed on the profile id so the form starts from the saved values exactly once.
  return <ProfileEditor key={profile.data.id} profile={profile.data} />;
}

export default function ProfilePage() {
  return <Suspense><ProfileLoader /></Suspense>;
}
