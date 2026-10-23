"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { Alert, Button, Field, Input, RadioCards, Select, TagInput, Textarea } from "@/components/ui";
import { ApiError, api } from "@/lib/api/client";
import { friendlyError } from "@/lib/api/messages";
import { useOrgs } from "@/lib/api/hooks";
import type { Visibility } from "@/lib/api/types";
import { VISIBILITY_OPTIONS } from "@/lib/visibility";

const NEXT_YEAR_LIMIT = new Date().getFullYear() + 6;

function OnboardingForm() {
  const router = useRouter();
  const qc = useQueryClient();
  const welcome = useSearchParams().get("welcome") === "1";
  const schools = useOrgs("school");

  const [fullName, setFullName] = useState("");
  const [schoolId, setSchoolId] = useState("");
  const [year, setYear] = useState("");
  const [country, setCountry] = useState("Kenya");
  const [profession, setProfession] = useState("");
  const [company, setCompany] = useState("");
  const [bio, setBio] = useState("");
  const [visibility, setVisibility] = useState<Visibility>("members_only");
  const [skills, setSkills] = useState<string[]>([]);
  const [interests, setInterests] = useState<string[]>([]);
  const [fields, setFields] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const issues: Record<string, string> = {};
    if (!fullName.trim()) issues.full_name = "Enter your full name.";
    if (year && (Number(year) < 1950 || Number(year) > NEXT_YEAR_LIMIT)) {
      issues.graduation_year = `Enter a year between 1950 and ${NEXT_YEAR_LIMIT}.`;
    }
    setFields(issues);
    if (Object.keys(issues).length) return;

    setBusy(true);
    try {
      await api("alumni/profile", {
        method: "POST",
        body: {
          full_name: fullName.trim(),
          school_id: schoolId || null,
          graduation_year: year ? Number(year) : null,
          country: country.trim() || null,
          profession: profession.trim() || null,
          company: company.trim() || null,
          bio: bio.trim() || null,
          profile_visibility: visibility,
        },
      });
    } catch (err) {
      if (err instanceof ApiError) setFields(err.fieldErrors());
      setError(friendlyError(err));
      setBusy(false);
      return;
    }

    // The profile exists now. Skills and interests are extras: if one fails, say so, but carry on.
    const failed: string[] = [];
    for (const [path, names, label] of [
      ["alumni/profile/skills", skills, "skills"],
      ["alumni/profile/interests", interests, "interests"],
    ] as const) {
      if (names.length === 0) continue;
      try {
        await api(path, { method: "PUT", body: { names } });
      } catch {
        failed.push(label);
      }
    }
    await qc.invalidateQueries({ queryKey: ["profile"] });
    router.replace(failed.length ? `/profile?saved=partial&missing=${failed.join(",")}` : "/home");
  }

  return (
    <form onSubmit={submit} className="space-y-6" noValidate>
      <div>
        <h1 className="text-title">Set up your alumni profile</h1>
        <p className="mt-1 text-small text-muted">This is what other members will see. You can change it any time.</p>
      </div>
      {welcome && <Alert tone="ok">Your account is ready. Check your email to verify your address.</Alert>}
      {error && <Alert>{error}</Alert>}

      <Field label="Full name" htmlFor="full_name" error={fields.full_name}>
        <Input id="full_name" autoComplete="name" required value={fullName} onChange={(e) => setFullName(e.target.value)} />
      </Field>

      <Field
        label="School"
        htmlFor="school_id"
        hint={schools.isError ? "We couldn’t load the schools. You can choose your school later from your profile." : "What you choose here is checked later by your school or by other alumni."}
      >
        <Select id="school_id" value={schoolId} onChange={(e) => setSchoolId(e.target.value)} disabled={schools.isLoading}>
          <option value="">{schools.isLoading ? "Loading schools…" : "Select your school"}</option>
          {schools.data?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
        </Select>
      </Field>

      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Graduation year" htmlFor="graduation_year" error={fields.graduation_year}>
          <Input id="graduation_year" type="number" inputMode="numeric" min={1950} max={NEXT_YEAR_LIMIT} value={year} onChange={(e) => setYear(e.target.value)} />
        </Field>
        <Field label="Country" htmlFor="country" error={fields.country}>
          <Input id="country" autoComplete="country-name" value={country} onChange={(e) => setCountry(e.target.value)} />
        </Field>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Profession" htmlFor="profession" error={fields.profession}>
          <Input id="profession" value={profession} onChange={(e) => setProfession(e.target.value)} />
        </Field>
        <Field label="Company" htmlFor="company" error={fields.company}>
          <Input id="company" autoComplete="organization" value={company} onChange={(e) => setCompany(e.target.value)} />
        </Field>
      </div>

      <Field label="About you" htmlFor="bio" error={fields.bio} hint="A sentence or two is plenty.">
        <Textarea id="bio" rows={3} value={bio} onChange={(e) => setBio(e.target.value)} />
      </Field>

      <TagInput id="skills" label="Skills (optional)" value={skills} onChange={setSkills} hint="For example: accounting, nursing, coding. Type one and press Enter." />
      <TagInput id="interests" label="Interests (optional)" value={interests} onChange={setInterests} hint="For example: golf, football, photography." />

      <RadioCards legend="Who can see your profile" name="visibility" options={VISIBILITY_OPTIONS} value={visibility} onChange={setVisibility} />

      <Button type="submit" className="w-full" loading={busy}>Create my profile</Button>
    </form>
  );
}

export default function Onboarding() {
  return <Suspense><OnboardingForm /></Suspense>;
}
