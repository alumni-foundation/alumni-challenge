"use client";

import { Camera, Trash2 } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { Alert, Avatar, Button, useToast } from "@/components/ui";
import { ApiError, api, apiUpload } from "@/lib/api/client";
import { friendlyError } from "@/lib/api/messages";
import type { Profile } from "@/lib/api/types";

const MAX_BYTES = 5 * 1024 * 1024;
const TYPES = ["image/jpeg", "image/png", "image/webp"];

/**
 * Photo upload is still being finished on the backend, so every step can fail and says so
 * plainly. The photo link the API gives us lasts an hour; if the image doesn't load, we ask
 * for the profile again to get a fresh one.
 */
export function AvatarEditor({ profile }: { profile: Profile }) {
  const qc = useQueryClient();
  const toast = useToast();
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState<"upload" | "remove" | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [brokenSrc, setBrokenSrc] = useState<string | null>(null);

  const refresh = () => qc.invalidateQueries({ queryKey: ["profile"] });

  function describe(e: unknown): string {
    // 404, 501 and 503 all mean the upload service isn't there (yet) rather than that the person did something wrong.
    if (e instanceof ApiError && [404, 501, 503].includes(e.status)) {
      return "Photo upload isn’t available right now. Please try again later.";
    }
    if (e instanceof ApiError && e.status === 413) return "That photo is too large. Choose one under 5 MB.";
    return friendlyError(e);
  }

  async function onPick(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = ""; // so picking the same file again still triggers a change
    if (!file) return;
    setProblem(null);
    if (!TYPES.includes(file.type)) return setProblem("Choose a JPEG, PNG or WebP photo.");
    if (file.size > MAX_BYTES) return setProblem("That photo is too large. Choose one under 5 MB.");

    setBusy("upload");
    try {
      const form = new FormData();
      form.set("purpose", "avatar");
      form.set("file", file);
      const uploaded = await apiUpload<{ id: string }>("files", form);
      await api("alumni/profile/avatar", { method: "PUT", body: { file_id: uploaded.id } });
      await refresh();
      toast("Photo saved.");
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
      await api("alumni/profile/avatar", { method: "DELETE" });
      await refresh();
      toast("Photo removed.");
    } catch (err) {
      setProblem(describe(err));
    } finally {
      setBusy(null);
    }
  }

  const src = profile.avatar_url && profile.avatar_url !== brokenSrc ? profile.avatar_url : null;

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-4">
        {src ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={src}
            alt="Your photo"
            width={80}
            height={80}
            className="size-20 rounded-full object-cover"
            onError={() => {
              // The link expired. Remember it failed so we don't loop, and fetch a fresh one.
              setBrokenSrc(src);
              void refresh();
            }}
          />
        ) : (
          <Avatar name={profile.full_name} id={profile.id} size={80} />
        )}
        <div className="flex flex-wrap gap-2">
          <input ref={input} type="file" accept={TYPES.join(",")} className="sr-only" id="avatar-file" onChange={onPick} tabIndex={-1} />
          <Button variant="secondary" loading={busy === "upload"} onClick={() => input.current?.click()}>
            <Camera className="size-4" aria-hidden /> {profile.avatar_url ? "Change photo" : "Add a photo"}
          </Button>
          {profile.avatar_url && (
            <Button variant="ghost" loading={busy === "remove"} onClick={onRemove}>
              <Trash2 className="size-4" aria-hidden /> Remove photo
            </Button>
          )}
        </div>
      </div>
      <p className="text-caption text-muted">JPEG, PNG or WebP, up to 5 MB.</p>
      {problem && <Alert>{problem}</Alert>}
    </div>
  );
}
