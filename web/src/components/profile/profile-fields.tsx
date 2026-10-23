"use client";

import { Field, Input, RadioCards, Select, TagInput, Textarea } from "@/components/ui";
import type { Organization, Profile, Visibility } from "@/lib/api/types";
import { VISIBILITY_OPTIONS } from "@/lib/visibility";

export const MIN_YEAR = 1950;
export const MAX_YEAR = new Date().getFullYear() + 6;

export type ProfileValues = {
  fullName: string;
  schoolId: string;
  year: string;
  country: string;
  profession: string;
  company: string;
  bio: string;
  visibility: Visibility;
  skills: string[];
  interests: string[];
};

export const NEW_PROFILE: ProfileValues = {
  fullName: "",
  schoolId: "",
  year: "",
  country: "Kenya",
  profession: "",
  company: "",
  bio: "",
  visibility: "members_only",
  skills: [],
  interests: [],
};

export const valuesFromProfile = (p: Profile): ProfileValues => ({
  fullName: p.full_name,
  schoolId: p.school_id ?? "",
  year: p.graduation_year ? String(p.graduation_year) : "",
  country: p.country ?? "",
  profession: p.profession ?? "",
  company: p.company ?? "",
  bio: p.bio ?? "",
  visibility: p.profile_visibility,
  skills: p.skills,
  interests: p.interests,
});

/** Messages to show next to the fields. An empty object means the form can be sent. */
export function validateProfile(v: ProfileValues): Record<string, string> {
  const issues: Record<string, string> = {};
  if (!v.fullName.trim()) issues.full_name = "Enter your full name.";
  if (v.year && (Number(v.year) < MIN_YEAR || Number(v.year) > MAX_YEAR)) {
    issues.graduation_year = `Enter a year between ${MIN_YEAR} and ${MAX_YEAR}.`;
  }
  return issues;
}

/** The fields the API takes for creating or updating a profile (skills and interests go separately). */
export const profileBody = (v: ProfileValues) => ({
  full_name: v.fullName.trim(),
  school_id: v.schoolId || null,
  graduation_year: v.year ? Number(v.year) : null,
  country: v.country.trim() || null,
  profession: v.profession.trim() || null,
  company: v.company.trim() || null,
  bio: v.bio.trim() || null,
  profile_visibility: v.visibility,
});

export function ProfileFields({ values, onChange, errors, schools }: {
  values: ProfileValues;
  onChange: (next: ProfileValues) => void;
  errors: Record<string, string>;
  schools: { data?: Organization[]; isLoading: boolean; isError: boolean };
}) {
  const set = <K extends keyof ProfileValues>(key: K, value: ProfileValues[K]) => onChange({ ...values, [key]: value });
  return (
    <div className="space-y-6">
      <Field label="Full name" htmlFor="full_name" error={errors.full_name}>
        <Input id="full_name" autoComplete="name" required value={values.fullName} onChange={(e) => set("fullName", e.target.value)} />
      </Field>

      <Field
        label="School"
        htmlFor="school_id"
        error={errors.school_id}
        hint={schools.isError ? "We couldn’t load the schools. You can choose your school later." : "What you choose here is checked later by your school or by other alumni."}
      >
        <Select id="school_id" value={values.schoolId} onChange={(e) => set("schoolId", e.target.value)} disabled={schools.isLoading}>
          <option value="">{schools.isLoading ? "Loading schools…" : "Select your school"}</option>
          {schools.data?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
        </Select>
      </Field>

      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Graduation year" htmlFor="graduation_year" error={errors.graduation_year}>
          <Input id="graduation_year" type="number" inputMode="numeric" min={MIN_YEAR} max={MAX_YEAR} value={values.year} onChange={(e) => set("year", e.target.value)} />
        </Field>
        <Field label="Country" htmlFor="country" error={errors.country}>
          <Input id="country" autoComplete="country-name" value={values.country} onChange={(e) => set("country", e.target.value)} />
        </Field>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Profession" htmlFor="profession" error={errors.profession}>
          <Input id="profession" value={values.profession} onChange={(e) => set("profession", e.target.value)} />
        </Field>
        <Field label="Company" htmlFor="company" error={errors.company}>
          <Input id="company" autoComplete="organization" value={values.company} onChange={(e) => set("company", e.target.value)} />
        </Field>
      </div>

      <Field label="About you" htmlFor="bio" error={errors.bio} hint="A sentence or two is plenty.">
        <Textarea id="bio" rows={4} value={values.bio} onChange={(e) => set("bio", e.target.value)} />
      </Field>

      <TagInput id="skills" label="Skills (optional)" value={values.skills} onChange={(v) => set("skills", v)} hint="For example: accounting, nursing, coding. Type one and press Enter." />
      <TagInput id="interests" label="Interests (optional)" value={values.interests} onChange={(v) => set("interests", v)} hint="For example: golf, football, photography." />

      <RadioCards legend="Who can see your profile" name="visibility" options={VISIBILITY_OPTIONS} value={values.visibility} onChange={(v) => set("visibility", v)} />
    </div>
  );
}
