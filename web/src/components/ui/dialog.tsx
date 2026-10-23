"use client";

import { X } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
import { ApiError } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import { Alert, Button, Field, Textarea } from "./index";

/**
 * A modal built on the native <dialog>, which gives us a focus trap, Escape to close and an
 * inert background for free. On phones it fills the screen like a sheet; from 640px up it is a
 * centred card.
 */
export function Dialog({ open, onClose, title, children, footer, busy = false }: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
  /** While true the dialog can't be dismissed, so a save in flight isn't abandoned. */
  busy?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (open && !el.open) el.showModal();
    if (!open && el.open) el.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      onCancel={(e) => {
        e.preventDefault();
        if (!busy) onClose();
      }}
      onClick={(e) => {
        if (e.target === ref.current && !busy) onClose();
      }}
      className={cn(
        "m-0 h-dvh max-h-none w-full max-w-none bg-surface p-0 text-ink backdrop:bg-scrim",
        "sm:m-auto sm:h-auto sm:max-h-[85dvh] sm:max-w-md sm:rounded-sheet sm:border sm:border-line sm:shadow-lifted",
        "open:flex open:flex-col open:motion-rise",
      )}
    >
      {open && (
        <>
          <div className="flex items-start justify-between gap-4 px-5 pb-2 pt-5">
            <h2 id={titleId} className="text-heading">{title}</h2>
            <button
              type="button"
              onClick={onClose}
              disabled={busy}
              aria-label="Close"
              className="-mr-2 -mt-1 inline-flex size-11 items-center justify-center rounded-full text-muted hover:bg-sunken hover:text-ink disabled:opacity-50"
            >
              <X className="size-5" aria-hidden />
            </button>
          </div>
          <div className="flex-1 overflow-y-auto px-5 pb-4">{children}</div>
          {footer && (
            <div className="flex flex-col-reverse gap-2 border-t border-line px-5 py-4 pb-[max(1rem,env(safe-area-inset-bottom))] sm:flex-row sm:justify-end">
              {footer}
            </div>
          )}
        </>
      )}
    </dialog>
  );
}

const errorText = (e: unknown) => (e instanceof ApiError ? e.message : "Something went wrong. Please try again.");

/** Ask before doing something that is hard to undo. Shows the server's reply if it refuses. */
export function ConfirmDialog({ open, title, body, confirmLabel, danger = false, onConfirm, onClose }: {
  open: boolean;
  title: string;
  body: React.ReactNode;
  confirmLabel: string;
  danger?: boolean;
  onConfirm: () => Promise<unknown>;
  onClose: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function close() {
    setError(null);
    onClose();
  }
  async function confirm() {
    setBusy(true);
    setError(null);
    try {
      await onConfirm();
      close();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog
      open={open}
      onClose={close}
      title={title}
      busy={busy}
      footer={
        <>
          <Button variant="secondary" onClick={close} disabled={busy}>Cancel</Button>
          <Button variant={danger ? "danger" : "primary"} onClick={confirm} loading={busy}>{confirmLabel}</Button>
        </>
      }
    >
      <div className="space-y-3 text-small text-muted">
        <div>{body}</div>
        {error && <Alert>{error}</Alert>}
      </div>
    </Dialog>
  );
}

const REASON_MAX = 500;

/** A required reason of 1 to 500 characters (reports, suspend, reactivate). */
export function ReasonDialog({ open, title, body, label = "Reason", confirmLabel, danger = false, onSubmit, onClose }: {
  open: boolean;
  title: string;
  body?: React.ReactNode;
  label?: string;
  confirmLabel: string;
  danger?: boolean;
  onSubmit: (reason: string) => Promise<unknown>;
  onClose: () => void;
}) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const id = useId();
  const trimmed = reason.trim();

  function close() {
    setReason("");
    setError(null);
    onClose();
  }
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!trimmed) return;
    setBusy(true);
    setError(null);
    try {
      await onSubmit(trimmed);
      close();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog
      open={open}
      onClose={close}
      title={title}
      busy={busy}
      footer={
        <>
          <Button variant="secondary" onClick={close} disabled={busy}>Cancel</Button>
          <Button type="submit" form={`${id}-form`} variant={danger ? "danger" : "primary"} loading={busy} disabled={!trimmed}>
            {confirmLabel}
          </Button>
        </>
      }
    >
      <form id={`${id}-form`} onSubmit={submit} className="space-y-4">
        {body && <div className="text-small text-muted">{body}</div>}
        <Field label={label} htmlFor={`${id}-reason`} hint={`${trimmed.length} of ${REASON_MAX} characters`}>
          <Textarea
            id={`${id}-reason`}
            value={reason}
            maxLength={REASON_MAX}
            required
            onChange={(e) => setReason(e.target.value)}
          />
        </Field>
        {error && <Alert>{error}</Alert>}
      </form>
    </Dialog>
  );
}
