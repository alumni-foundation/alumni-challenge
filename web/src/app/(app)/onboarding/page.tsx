"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Alert, Button, Field, Input, Select, Textarea } from "@/components/ui";
import { ApiError, api } from "@/lib/api/client";
import { useOrgs } from "@/lib/api/hooks";
import { useQueryClient } from "@tanstack/react-query";
import type { Visibility } from "@/lib/api/types";

export default function Onboarding() {
  const router = useRouter();
  const qc = useQueryClient();
  const schools = useOrgs("school");
  const [full_name, setName] = useState("");
  const [bio, setBio] = useState("");
  const [graduation_year, setYear] = useState("");
  const [school_id, setSchool] = useState("");
  const [country, setCountry] = useState("Kenya");
  const [profession, setProfession] = useState("");
  const [profile_visibility, setVisibility] = useState<Visibility>("members_only");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api("alumni/profile", {
        method: "POST",
        body: {
          full_name,
          bio: bio || null,
          graduation_year: graduation_year ? Number(graduation_year) : null,
          school_id: school_id || null,
          country: country || null,
          profession: profession || null,
          profile_visibility,
        },
      });
      await qc.invalidateQueries({ queryKey: ["profile"] });
      router.replace("/home");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold">Set up your alumni profile</h1>
        <p className="mt-1 text-sm text-muted">This is what other members will see. You can change it anytime.</p>
      </div>
      {error && <Alert>{error}</Alert>}
      <Field label="Full name" htmlFor="full_name">
        <Input id="full_name" required value={full_name} onChange={(e) => setName(e.target.value)} />
      </Field>
      <Field label="School" htmlFor="school_id" hint="Self-declared. Verified later by your school or peers.">
        <Select id="school_id" value={school_id} onChange={(e) => setSchool(e.target.value)}>
          <option value="">Select your school</option>
          {schools.data?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
        </Select>
      </Field>
      <div className="grid grid-cols-2 gap-4">
        <Field label="Graduation year" htmlFor="year">
          <Input id="year" type="number" min={1950} max={2035} value={graduation_year} onChange={(e) => setYear(e.target.value)} />
        </Field>
        <Field label="Country" htmlFor="country">
          <Input id="country" value={country} onChange={(e) => setCountry(e.target.value)} />
        </Field>
      </div>
      <Field label="Profession" htmlFor="profession">
        <Input id="profession" value={profession} onChange={(e) => setProfession(e.target.value)} />
      </Field>
      <Field label="Bio" htmlFor="bio">
        <Textarea id="bio" rows={3} value={bio} onChange={(e) => setBio(e.target.value)} />
      </Field>
      <Field label="Who can see your profile" htmlFor="vis">
        <Select id="vis" value={profile_visibility} onChange={(e) => setVisibility(e.target.value as Visibility)}>
          <option value="public">Public — anyone</option>
          <option value="members_only">Members only — signed-in alumni</option>
          <option value="connections_only">Connections only</option>
          <option value="private">Private — only you</option>
        </Select>
      </Field>
      <Button type="submit" className="w-full" loading={busy} disabled={!full_name}>Finish setup</Button>
    </form>
  );
}
