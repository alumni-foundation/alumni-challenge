"use client";

import { ImagePlus, Trash2 } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { OrgLogo } from "@/components/public/org";
import { Alert, Button, useToast } from "@/components/ui";
import { ApiError, api, apiUpload } from "@/lib/api/client";
import { friendlyError } from "@/lib/api/messages";
import type { Organization } from "@/lib/api/types";

const MAX_BYTES = 5 * 1024 * 1024;
const TYPES = ["image/jpeg", "image/png", "image/webp"];

/** Upload, replace or remove an organization's logo. Every step can fail and says so plainly. */
export function LogoEditor({ org }: { org: Organization }) {
  const qc = useQueryClient();
  const toast = useToast();
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState<"upload" | "remove" | null>(null);
  const [problem, setProblem] = useState<string | null>(null);

  const refresh = () => Promise.all([qc.invalidateQueries({ queryKey: ["org", org.id] }), qc.invalidateQueries({ queryKey: ["orgs"] })]);

  function describe(e: unknown): string {
    if (e instanceof ApiError && [404, 501, 503].includes(e.status)) return "Logo upload isn’t available right now. Please try again later.";
    if (e instanceof ApiError && e.status === 413) return "That picture is too large. Choose one under 5 MB.";
    return friendlyError(e);
  }

  async function onPick(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setProblem(null);
    if (!TYPES.includes(file.type)) return setProblem("Choose a JPEG, PNG or WebP picture.");
    if (file.size > MAX_BYTES) return setProblem("That picture is too large. Choose one under 5 MB.");
    setBusy("upload");
    try {
      const form = new FormData();
      form.set("purpose", "organization_logo");
      form.set("organization_id", org.id);
      form.set("file", file);
      const uploaded = await apiUpload<{ id: string }>("files", form);
      await api(`organizations/${org.id}/logo`, { method: "PUT", body: { file_id: uploaded.id } });
      await refresh();
      toast("Logo saved.");
    } catch (err) {
      setProblem(describe(err));
    } finally {
      setBusy(null);
    }
  }

  async function onRemove() {
    setProblem(null);
    setBusy("remove");
    try {
      await api(`organizations/${org.id}/logo`, { method: "DELETE" });
      await refresh();
      toast("Logo removed.");
    } catch (err) {
      setProblem(describe(err));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-4">
        <OrgLogo org={org} size={80} />
        <div className="flex flex-wrap gap-2">
          <input ref={input} type="file" accept={TYPES.join(",")} className="sr-only" id="logo-file" onChange={onPick} tabIndex={-1} />
          <Button variant="secondary" loading={busy === "upload"} onClick={() => input.current?.click()}>
            <ImagePlus className="size-4" aria-hidden /> {org.logo_url ? "Change logo" : "Add a logo"}
          </Button>
          {org.logo_url && (
            <Button variant="ghost" loading={busy === "remove"} onClick={onRemove}>
              <Trash2 className="size-4" aria-hidden /> Remove logo
            </Button>
          )}
        </div>
      </div>
      <p className="text-caption text-muted">JPEG, PNG or WebP, up to 5 MB.</p>
      {problem && <Alert>{problem}</Alert>}
    </div>
  );
}
