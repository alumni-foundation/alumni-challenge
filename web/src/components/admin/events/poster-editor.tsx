"use client";

import { ImagePlus, Trash2 } from "lucide-react";
import Image from "next/image";
import { useRef, useState } from "react";
import { Alert, Button, useToast } from "@/components/ui";
import { ApiError, apiUpload } from "@/lib/api/client";
import { eventCalls } from "@/lib/api/hooks";
import { friendlyError } from "@/lib/api/messages";
import type { EventDetail } from "@/lib/api/types";
import { IMAGE_TYPES, imageProblem } from "@/lib/image-upload";

/**
 * The cover image of a saved event: preview, choose, replace, remove. The server keeps its own copy of the picture
 * (re-encoded), so only the file's bytes matter here, not its name or declared type.
 */
export function PosterEditor({ event, disabled, onChange }: {
  event: EventDetail;
  disabled: boolean;
  onChange: (next: EventDetail) => void;
}) {
  const toast = useToast();
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState<"upload" | "remove" | null>(null);
  const [problem, setProblem] = useState<string | null>(null);

  function describe(e: unknown): string {
    if (e instanceof ApiError && e.status === 413) return "That picture is too large. Choose one under 5 MB.";
    return friendlyError(e);
  }

  async function onPick(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setProblem(null);
    const bad = imageProblem(file);
    if (bad) return setProblem(bad);
    setBusy("upload");
    try {
      const form = new FormData();
      form.set("purpose", "event_poster");
      // A platform event has no organization, so the field is left out.
      if (event.organizer) form.set("organization_id", event.organizer.id);
      form.set("file", file);
      const uploaded = await apiUpload<{ id: string }>("files", form);
      onChange(await eventCalls.setPoster(event.id, uploaded.id));
      toast(event.poster_url ? "Cover image replaced" : "Cover image saved");
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
      onChange(await eventCalls.removePoster(event.id));
      toast("Cover image removed");
    } catch (err) {
      setProblem(describe(err));
    } finally {
      setBusy(null);
    }
  }

  const working = busy !== null;
  return (
    <div className="space-y-3">
      <div className="relative aspect-[16/9] w-full overflow-hidden rounded-card border border-line bg-sunken">
        {event.poster_url ? (
          <Image src={event.poster_url} alt="Cover image preview" fill sizes="(min-width: 768px) 672px, 100vw" quality={75} className="object-cover" />
        ) : (
          <div className="flex size-full items-center justify-center px-4 text-center text-small text-muted">No cover image yet</div>
        )}
      </div>
      <div className="flex flex-wrap gap-2">
        <input ref={input} type="file" accept={IMAGE_TYPES.join(",")} className="sr-only" id="poster-file" onChange={onPick} tabIndex={-1} aria-label="Cover image file" />
        <Button variant="secondary" loading={busy === "upload"} disabled={disabled || working} onClick={() => input.current?.click()}>
          <ImagePlus className="size-4" aria-hidden /> {event.poster_url ? "Replace" : "Choose image"}
        </Button>
        {event.poster_url && (
          <Button variant="ghost" loading={busy === "remove"} disabled={disabled || working} onClick={() => void onRemove()}>
            <Trash2 className="size-4" aria-hidden /> Remove
          </Button>
        )}
      </div>
      <p className="text-caption text-muted">Wide image, 1600 x 900 or larger, looks best on cards. JPEG, PNG or WebP, up to 5 MB.</p>
      {problem && <Alert>{problem}</Alert>}
    </div>
  );
}
