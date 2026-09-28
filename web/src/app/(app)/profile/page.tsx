"use client";

import { useState } from "react";
import { Avatar, Alert, Button, Field, Input, PageHeader, Select, Spinner, Textarea, VerifiedMark } from "@/components/ui";
import { api, ApiError } from "@/lib/api/client";
import { useMyProfile, useOrgs, useWrite } from "@/lib/api/hooks";
import type { Profile, Visibility } from "@/lib/api/types";

export default function EditProfile() {
  const profile = useMyProfile();
  const schools = useOrgs("school");
  const p = profile.data;
  // Keyed remount pattern instead of an effect: when the fetched profile's id first
  // appears, React mounts a fresh <ProfileForm> with it as the initial state. No
  // setState-in-effect, no cascading render.
  const [saved, setSaved] = useState(false);

  if (profile.isLoading || !p) return <Spinner label="Loading your profile" />;

  return <ProfileForm key={p.id} initial={p} saved={saved} onSaved={setSaved} schools={schools.data} />;
}

function ProfileForm({
  initial,
  saved,
  onSaved,
  schools,
}: {
  initial: Profile;
  saved: boolean;
  onSaved: (v: boolean) => void;
  schools: ReturnType<typeof useOrgs>["data"];
}) {
  const [form, setForm] = useState<Partial<Profile>>(initial);
  const [skillsText, setSkillsText] = useState(initial.skills.join(", "));
  const [interestsText, setInterestsText] = useState(initial.interests.join(", "));
  const save = useWrite(
    (body: Partial<Profile>) => api("alumni/profile", { method: "PATCH", body }),
    [["profile", "me"]],
  );
  const saveSkills = useWrite((names: string[]) => api("alumni/profile/skills", { method: "PUT", body: { names } }), [["profile", "me"]]);
  const saveInterests = useWrite((names: string[]) => api("alumni/profile/interests", { method: "PUT", body: { names } }), [["profile", "me"]]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    onSaved(false);
    const list = (s: string) => s.split(",").map((x) => x.trim()).filter(Boolean);
    await Promise.all([
      save.mutateAsync({
        full_name: form!.full_name,
        bio: form!.bio || null,
        graduation_year: form!.graduation_year ?? null,
        school_id: form!.school_id ?? null,
        country: form!.country || null,
        profession: form!.profession || null,
        company: form!.company || null,
        profile_visibility: form!.profile_visibility,
      }),
      saveSkills.mutateAsync(list(skillsText)),
      saveInterests.mutateAsync(list(interestsText)),
    ]);
    onSaved(true);
  }

  const err = save.error ?? saveSkills.error ?? saveInterests.error;

  return (
    <div className="mx-auto max-w-2xl">
      <PageHeader title="Edit profile" subtitle="This is what other members see about you." />
      <form onSubmit={submit} className="space-y-5">
        <div className="flex items-center gap-4">
          <Avatar name={form.full_name ?? ""} id={initial.id} size={56} />
          <div>
            <p className="font-semibold">{form.full_name} {initial.verification_status === "verified" && <VerifiedMark />}</p>
            <p className="text-sm text-muted">{initial.verification_status === "verified" ? "Verified alumnus" : `${initial.vouch_count}/3 vouches toward verification`}</p>
          </div>
        </div>
        {err && <Alert>{err instanceof ApiError ? err.message : "Couldn't save. Try again."}</Alert>}
        {saved && !err && <Alert tone="ok">Profile saved.</Alert>}

        <Field label="Full name" htmlFor="full_name">
          <Input id="full_name" required value={form.full_name ?? ""} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
        </Field>
        <Field label="School" htmlFor="school_id">
          <Select id="school_id" value={form.school_id ?? ""} onChange={(e) => setForm({ ...form, school_id: e.target.value || null })}>
            <option value="">Not set</option>
            {schools?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </Select>
        </Field>
        <div className="grid grid-cols-2 gap-4">
          <Field label="Graduation year" htmlFor="year">
            <Input id="year" type="number" min={1950} max={2035} value={form.graduation_year ?? ""} onChange={(e) => setForm({ ...form, graduation_year: e.target.value ? Number(e.target.value) : null })} />
          </Field>
          <Field label="Country" htmlFor="country">
            <Input id="country" value={form.country ?? ""} onChange={(e) => setForm({ ...form, country: e.target.value })} />
          </Field>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <Field label="Profession" htmlFor="profession">
            <Input id="profession" value={form.profession ?? ""} onChange={(e) => setForm({ ...form, profession: e.target.value })} />
          </Field>
          <Field label="Company" htmlFor="company" hint="Hidden from anonymous viewers.">
            <Input id="company" value={form.company ?? ""} onChange={(e) => setForm({ ...form, company: e.target.value })} />
          </Field>
        </div>
        <Field label="Bio" htmlFor="bio">
          <Textarea id="bio" rows={4} value={form.bio ?? ""} onChange={(e) => setForm({ ...form, bio: e.target.value })} />
        </Field>
        <Field label="Skills" htmlFor="skills" hint="Comma separated.">
          <Input id="skills" value={skillsText} onChange={(e) => setSkillsText(e.target.value)} />
        </Field>
        <Field label="Interests" htmlFor="interests" hint="Comma separated.">
          <Input id="interests" value={interestsText} onChange={(e) => setInterestsText(e.target.value)} />
        </Field>
        <Field label="Who can see your profile" htmlFor="vis">
          <Select id="vis" value={form.profile_visibility} onChange={(e) => setForm({ ...form, profile_visibility: e.target.value as Visibility })}>
            <option value="public">Public — anyone</option>
            <option value="members_only">Members only</option>
            <option value="connections_only">Connections only</option>
            <option value="private">Private</option>
          </Select>
        </Field>
        <Button type="submit" loading={save.isPending || saveSkills.isPending || saveInterests.isPending}>Save changes</Button>
      </form>
    </div>
  );
}
