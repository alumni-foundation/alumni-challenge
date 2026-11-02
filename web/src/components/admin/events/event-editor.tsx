"use client";

import { useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ExternalLink } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import {
  Alert, Badge, Button, Card, ConfirmDialog, Field, Input, RadioCards, ReasonDialog, Select, Textarea, useToast,
} from "@/components/ui";
import { ApiError } from "@/lib/api/client";
import { eventCalls, useOrgs, useRoles } from "@/lib/api/hooks";
import type { EventCategory, EventDetail } from "@/lib/api/types";
import {
  actionsFor, CAPACITY_MAX, CANCEL_REASON_MIN, CATEGORY_OPTIONS, DESCRIPTION_MAX, EMPTY_VALUES, PARTY_SIZE_MAX, slotChanges,
  toCreate, toUpdate, validateEventForm, valuesFromEvent, VISIBILITY_OPTIONS, type EventFormValues, type FormErrors,
} from "@/lib/event-form";
import { priceText } from "@/lib/events";
import { PosterEditor } from "./poster-editor";
import { canManageOrg, isPlatformAdmin } from "@/lib/roles";

const FIELD_ORDER: (keyof EventFormValues)[] = [
  "title", "description", "category", "visibility", "organizationId", "startsAt", "endsAt", "registrationOpensAt",
  "registrationClosesAt", "venueName", "venueAddress", "capacity", "maxPartySize", "contactEmail", "contactPhone",
];

/** The API names a field in snake_case; the form uses its own names. */
const FROM_SERVER: Record<string, keyof EventFormValues> = {
  title: "title", description: "description", category: "category", visibility: "visibility", organization_id: "organizationId",
  starts_at: "startsAt", ends_at: "endsAt", venue_name: "venueName", venue_address: "venueAddress",
  registration_opens_at: "registrationOpensAt", registration_closes_at: "registrationClosesAt", capacity: "capacity",
  max_party_size: "maxPartySize", contact_email: "contactEmail", contact_phone: "contactPhone",
};

const STATUS_BADGE: Record<string, { label: string; tone: "neutral" | "ok" | "warn" | "danger" | "blue" }> = {
  draft: { label: "Draft", tone: "neutral" },
  published: { label: "Published", tone: "ok" },
  closed: { label: "Registration closed", tone: "warn" },
  cancelled: { label: "Cancelled", tone: "danger" },
  completed: { label: "Completed", tone: "blue" },
};

const fieldId = (k: keyof EventFormValues) => `ev-${k}`;

function focusFirst(errors: FormErrors) {
  const first = FIELD_ORDER.find((k) => errors[k]);
  if (first) window.requestAnimationFrame(() => document.getElementById(fieldId(first))?.focus());
}

const errorMessage = (e: unknown) => (e instanceof ApiError ? e.message : "Something went wrong. Please try again.");

type Pending = "save" | "reopen" | null;
type Dialog = "publish" | "close" | "cancel" | "delete" | null;

/**
 * The create and edit screen for one event. `initial` is null for a new event. The editor keeps the event it last
 * saved, so a second save on a screen that just created one edits it rather than making another.
 */
export function EventEditor({ initial, presetOrganizationId }: { initial: EventDetail | null; presetOrganizationId?: string }) {
  const router = useRouter();
  const toast = useToast();
  const qc = useQueryClient();
  const roles = useRoles();
  const schools = useOrgs("school");
  const partners = useOrgs("partner");

  const [saved, setSaved] = useState<EventDetail | null>(initial);
  const [baseline, setBaseline] = useState<EventFormValues>(() =>
    initial ? valuesFromEvent(initial) : { ...EMPTY_VALUES, organizationId: presetOrganizationId ?? "" },
  );
  const [values, setValues] = useState<EventFormValues>(baseline);
  const [errors, setErrors] = useState<FormErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [pending, setPending] = useState<Pending>(null);
  const [dialog, setDialog] = useState<Dialog>(null);

  const platform = isPlatformAdmin(roles.data);
  const orgs = [...(schools.data ?? []), ...(partners.data ?? [])]
    .filter((o) => platform || canManageOrg(roles.data, o.id))
    .sort((a, b) => a.name.localeCompare(b.name));
  // Someone who runs exactly one organization has nothing to choose.
  const onlyOrg = !platform && !saved && orgs.length === 1 ? orgs[0].id : "";
  // A preset organizer (from the link) that this person can't run for is ignored once the lists have loaded.
  const orgsReady = !schools.isLoading && !partners.isLoading;
  const presetKnown = saved !== null || !orgsReady || values.organizationId === "" || orgs.some((o) => o.id === values.organizationId);
  const current: EventFormValues = { ...values, organizationId: (presetKnown ? values.organizationId : "") || onlyOrg };

  const status = saved?.status ?? "draft";
  const actions = actionsFor(status);
  const editable = !saved || actions.save;
  const slotCount = saved?.slots.length ?? 1;
  const capacityEditable = slotCount === 1;
  const dirty = !saved || JSON.stringify(current) !== JSON.stringify(baseline);
  const busy = pending !== null;

  function set<K extends keyof EventFormValues>(key: K, value: EventFormValues[K]) {
    setValues((v) => ({ ...v, [key]: value }));
    if (errors[key]) setErrors((e) => ({ ...e, [key]: undefined }));
  }

  function validate(): boolean {
    const startChanged = !saved || current.startsAt !== baseline.startsAt || current.endsAt !== baseline.endsAt;
    const found = validateEventForm(current, {
      checkPast: startChanged,
      editableCapacity: capacityEditable,
      organizationRequired: !saved && !platform,
    });
    setErrors(found);
    if (Object.keys(found).length) {
      setFormError("Some details need another look. They are marked below.");
      focusFirst(found);
      return false;
    }
    setFormError(null);
    return true;
  }

  function apply(event: EventDetail, keepTyped = false) {
    const next = valuesFromEvent(event);
    setSaved(event);
    setBaseline(next);
    if (!keepTyped) setValues(next);
    void qc.invalidateQueries({ queryKey: ["events"] });
    void qc.invalidateQueries({ queryKey: ["event", event.id] });
  }

  /** Server complaints about a field go on that field; the sentence goes in the alert. */
  function showServerError(e: unknown) {
    setFormError(errorMessage(e));
    if (e instanceof ApiError) {
      const mapped: FormErrors = {};
      for (const [key, msg] of Object.entries(e.fieldErrors())) {
        const k = FROM_SERVER[key];
        if (k && !mapped[k]) mapped[k] = msg;
      }
      if (Object.keys(mapped).length) {
        setErrors(mapped);
        focusFirst(mapped);
      }
    }
  }

  /** Writes the form to the server: creates the draft, or sends what changed. Throws the API's error. */
  async function persist(): Promise<EventDetail> {
    if (!saved) {
      const created = await eventCalls.create(toCreate(current));
      apply(created);
      return created;
    }
    const slot = slotChanges(current, baseline, saved);
    const body = toUpdate(current, baseline);
    // The slot goes first: its server-only rule (places already taken) is the likelier refusal, and it changes nothing when it refuses.
    if (slot) await eventCalls.updateSlot(saved.id, slot.slotId, slot.body);
    try {
      if (Object.keys(body).length) await eventCalls.update(saved.id, body);
    } catch (e) {
      if (slot) apply(await eventCalls.get(saved.id), true);
      throw e;
    }
    const fresh = await eventCalls.get(saved.id);
    apply(fresh);
    return fresh;
  }

  async function onSave(e?: React.SyntheticEvent) {
    e?.preventDefault();
    if (busy || !editable || !validate()) return;
    setPending("save");
    try {
      const wasNew = !saved;
      const event = await persist();
      toast(wasNew ? "Draft saved" : "Changes saved");
      if (wasNew) router.replace(`/admin/events/${event.id}`);
    } catch (err) {
      showServerError(err);
    } finally {
      setPending(null);
    }
  }

  function openPublish() {
    if (validate()) setDialog("publish");
  }

  async function publish() {
    const wasNew = !saved;
    let event = saved;
    if (!event || dirty) event = await persist();
    try {
      const live = await eventCalls.publish(event.id);
      apply(live);
      toast("Event published");
      if (wasNew) router.replace(`/admin/events/${live.id}`);
    } catch (err) {
      // On a new event the draft exists by now, so say so: a retry will publish it, not make another.
      if (wasNew && err instanceof ApiError) {
        throw new ApiError(err.status, err.code, `Your draft was saved, but it could not be published. ${err.message}`, err.details);
      }
      throw err;
    }
  }

  async function transition(call: (id: string) => Promise<EventDetail>, done: string) {
    if (!saved) return;
    const next = await call(saved.id);
    apply(next);
    toast(done);
  }

  async function reopen() {
    setPending("reopen");
    setFormError(null);
    try {
      await transition(eventCalls.reopen, "Registration reopened");
    } catch (err) {
      setFormError(errorMessage(err));
    } finally {
      setPending(null);
    }
  }

  async function remove() {
    if (!saved) return;
    await eventCalls.remove(saved.id);
    void qc.invalidateQueries({ queryKey: ["events"] });
    toast("Draft deleted");
    router.replace("/admin/events");
  }

  const badge = STATUS_BADGE[status];
  const orgLocked = !!saved;
  const orgName = saved?.organizer?.name;

  return (
    <>
    <form onSubmit={onSave} noValidate className="mx-auto max-w-3xl space-y-6" aria-label={saved ? "Edit event" : "New event"}>
      <div>
        <Link href="/admin/events" className="mb-3 inline-flex min-h-11 items-center gap-1.5 text-small text-muted hover:text-ink">
          <ArrowLeft className="size-4" aria-hidden /> All events
        </Link>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="min-w-0 break-words text-title tracking-tight">{saved ? saved.title : "New event"}</h1>
          {saved && <Badge tone={badge.tone}>{badge.label}</Badge>}
        </div>
        <p className="mt-1 text-small text-muted">
          {saved ? "Change the details, then save." : "Start with a draft. Nobody sees it until you publish."} Times are Nairobi time.
        </p>
        {saved && status !== "draft" && (
          <Link href={`/events/${saved.id}`} className="mt-2 inline-flex min-h-11 items-center gap-1.5 text-small font-medium text-brand-ink hover:underline">
            See the public page <ExternalLink className="size-3.5" aria-hidden />
          </Link>
        )}
      </div>

      {!editable && (
        <Alert tone="info">
          {status === "cancelled" ? "This event was cancelled, so it can’t be changed." : "This event is over, so it can’t be changed."}
        </Alert>
      )}
      {saved && saved.price_minor > 0 && (
        <Alert tone="info">
          This event costs {priceText(saved.price_minor, saved.currency)}. Prices can’t be edited here yet, and saving leaves the price as it is.
        </Alert>
      )}
      {!saved && <Alert tone="info">Events here are free for now. Paid events come once payments are set up.</Alert>}

      <fieldset disabled={!editable || busy} className="min-w-0 space-y-6">
        <legend className="sr-only">Event details</legend>

        <Card large className="space-y-4">
          <h2 className="text-lead font-semibold">The basics</h2>
          <Field label="Title" htmlFor={fieldId("title")} error={errors.title} hint={`${current.title.trim().length} of 255 characters`}>
            <Input id={fieldId("title")} value={values.title} maxLength={300} autoComplete="off" onChange={(e) => set("title", e.target.value)} />
          </Field>
          <Field label="Description (optional)" htmlFor={fieldId("description")} error={errors.description} hint={`${values.description.length.toLocaleString("en-KE")} of ${DESCRIPTION_MAX.toLocaleString("en-KE")} characters`}>
            <Textarea id={fieldId("description")} value={values.description} rows={6} onChange={(e) => set("description", e.target.value)} />
          </Field>
          <div className="grid gap-4 sm:grid-cols-2 [&>*]:min-w-0">
            <Field label="Category" htmlFor={fieldId("category")} error={errors.category}>
              <Select id={fieldId("category")} value={values.category} onChange={(e) => set("category", e.target.value as EventCategory | "")}>
                <option value="">Choose a category</option>
                {CATEGORY_OPTIONS.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
              </Select>
            </Field>
            <Field
              label="Run by"
              htmlFor={fieldId("organizationId")}
              error={errors.organizationId}
              hint={orgLocked ? "The organizer can’t be changed once the draft exists." : platform ? "Pick the organization this event belongs to, or run it from the platform." : undefined}
            >
              <Select
                id={fieldId("organizationId")}
                value={current.organizationId}
                disabled={orgLocked}
                onChange={(e) => set("organizationId", e.target.value)}
              >
                {platform && <option value="">Platform (run by us)</option>}
                {!platform && !current.organizationId && <option value="">Choose an organization</option>}
                {orgLocked && saved?.organizer && !orgs.some((o) => o.id === saved.organizer?.id) && (
                  <option value={saved.organizer.id}>{orgName}</option>
                )}
                {orgs.map((o) => <option key={o.id} value={o.id}>{o.name} ({o.type === "school" ? "school" : "partner"})</option>)}
              </Select>
            </Field>
          </div>
          <div id={fieldId("visibility")} tabIndex={-1}>
            <RadioCards
              legend="Who can see it"
              name="visibility"
              options={VISIBILITY_OPTIONS}
              value={values.visibility}
              onChange={(v) => set("visibility", v)}
            />
          </div>
        </Card>

        <Card large className="space-y-4">
          <h2 className="text-lead font-semibold">When</h2>
          <div className="grid gap-4 sm:grid-cols-2 [&>*]:min-w-0">
            <Field label="Starts" htmlFor={fieldId("startsAt")} error={errors.startsAt}>
              <Input id={fieldId("startsAt")} type="datetime-local" value={values.startsAt} onChange={(e) => set("startsAt", e.target.value)} />
            </Field>
            <Field label="Ends" htmlFor={fieldId("endsAt")} error={errors.endsAt}>
              <Input id={fieldId("endsAt")} type="datetime-local" value={values.endsAt} onChange={(e) => set("endsAt", e.target.value)} />
            </Field>
            <Field label="Registration opens (optional)" htmlFor={fieldId("registrationOpensAt")} error={errors.registrationOpensAt} hint="Empty means as soon as it is published.">
              <Input id={fieldId("registrationOpensAt")} type="datetime-local" value={values.registrationOpensAt} onChange={(e) => set("registrationOpensAt", e.target.value)} />
            </Field>
            <Field label="Registration closes (optional)" htmlFor={fieldId("registrationClosesAt")} error={errors.registrationClosesAt} hint="Empty means until the event ends.">
              <Input id={fieldId("registrationClosesAt")} type="datetime-local" value={values.registrationClosesAt} onChange={(e) => set("registrationClosesAt", e.target.value)} />
            </Field>
          </div>
        </Card>

        <Card large className="space-y-4">
          <h2 className="text-lead font-semibold">Where</h2>
          <Field label="Venue name (optional)" htmlFor={fieldId("venueName")} error={errors.venueName}>
            <Input id={fieldId("venueName")} value={values.venueName} maxLength={300} onChange={(e) => set("venueName", e.target.value)} />
          </Field>
          <Field label="Venue address (optional)" htmlFor={fieldId("venueAddress")} error={errors.venueAddress}>
            <Input id={fieldId("venueAddress")} value={values.venueAddress} maxLength={550} onChange={(e) => set("venueAddress", e.target.value)} />
          </Field>
        </Card>

        <Card large className="space-y-4">
          <h2 className="text-lead font-semibold">Places</h2>
          <div className="grid gap-4 sm:grid-cols-2 [&>*]:min-w-0">
            <Field
              label="Capacity (optional)"
              htmlFor={fieldId("capacity")}
              error={errors.capacity}
              hint={capacityEditable ? `Empty means no limit. Up to ${CAPACITY_MAX.toLocaleString("en-KE")}.` : `This event has ${slotCount} time slots, so places are set for each slot. That isn’t editable here yet.`}
            >
              <Input id={fieldId("capacity")} inputMode="numeric" value={values.capacity} disabled={!capacityEditable} onChange={(e) => set("capacity", e.target.value)} />
            </Field>
            <Field label="Largest group per booking" htmlFor={fieldId("maxPartySize")} error={errors.maxPartySize} hint={`From 1 to ${PARTY_SIZE_MAX} people.`}>
              <Input id={fieldId("maxPartySize")} inputMode="numeric" value={values.maxPartySize} onChange={(e) => set("maxPartySize", e.target.value)} />
            </Field>
          </div>
        </Card>

        <Card large className="space-y-4">
          <h2 className="text-lead font-semibold">Contact</h2>
          <div className="grid gap-4 sm:grid-cols-2 [&>*]:min-w-0">
            <Field label="Contact email (optional)" htmlFor={fieldId("contactEmail")} error={errors.contactEmail}>
              <Input id={fieldId("contactEmail")} type="email" autoComplete="off" value={values.contactEmail} onChange={(e) => set("contactEmail", e.target.value)} />
            </Field>
            <Field label="Contact phone (optional)" htmlFor={fieldId("contactPhone")} error={errors.contactPhone}>
              <Input id={fieldId("contactPhone")} type="tel" autoComplete="off" value={values.contactPhone} onChange={(e) => set("contactPhone", e.target.value)} />
            </Field>
          </div>
        </Card>
      </fieldset>

        <Card large className="space-y-4">
          <h2 className="text-lead font-semibold">Cover image</h2>
          {saved ? (
            <PosterEditor event={saved} disabled={!editable || busy} onChange={(next) => setSaved(next)} />
          ) : (
            <p className="text-small text-muted">
              Save the draft first, then you can add a cover image. A picture can only be attached to an event that has been saved.
            </p>
          )}
        </Card>

      {formError && <Alert>{formError}</Alert>}

      <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center">
        {actions.save && (
          <Button type="submit" variant={actions.publish ? "secondary" : "dark"} loading={pending === "save"} disabled={busy || (!!saved && !dirty)}>
            {status === "draft" ? "Save draft" : "Save changes"}
          </Button>
        )}
        {actions.publish && <Button variant="dark" onClick={openPublish} disabled={busy}>Publish</Button>}
        {actions.reopen && <Button variant="dark" onClick={() => void reopen()} loading={pending === "reopen"} disabled={busy}>Reopen registration</Button>}
        {actions.close && <Button variant="secondary" onClick={() => setDialog("close")} disabled={busy}>Close registration</Button>}
        {actions.cancel && <Button variant="danger" onClick={() => setDialog("cancel")} disabled={busy}>Cancel event</Button>}
        {actions.remove && saved && <Button variant="danger" className="sm:ml-auto" onClick={() => setDialog("delete")} disabled={busy}>Delete draft</Button>}
      </div>
      {saved && editable && !dirty && <p className="-mt-3 text-caption text-muted">No unsaved changes.</p>}
    </form>

    {/* Outside the form: the reason dialog has a form of its own, and forms can't nest. */}
      <ConfirmDialog
        open={dialog === "publish"}
        title="Publish this event?"
        body={<>Members{current.visibility === "public" ? " and visitors" : ""} will be able to see “{current.title.trim()}” and book a place{dirty && saved ? ". Your unsaved changes are saved first" : ""}.</>}
        confirmLabel="Publish"
        onConfirm={publish}
        onClose={() => setDialog(null)}
      />
      <ConfirmDialog
        open={dialog === "close"}
        title="Close registration?"
        body="No one new can book. Bookings already made stay as they are, and you can reopen registration later."
        confirmLabel="Close registration"
        onConfirm={() => transition(eventCalls.close, "Registration closed")}
        onClose={() => setDialog(null)}
      />
      <ReasonDialog
        open={dialog === "cancel"}
        title="Cancel this event?"
        body="Every booking is cancelled and the people who booked are told. This can’t be undone. Say why, in a few words."
        label="Reason"
        minLength={CANCEL_REASON_MIN}
        confirmLabel="Cancel event"
        danger
        onSubmit={(reason) => transition((id) => eventCalls.cancel(id, reason), "Event cancelled")}
        onClose={() => setDialog(null)}
      />
      <ConfirmDialog
        open={dialog === "delete"}
        title="Delete this draft?"
        body="The draft is removed for good. Only drafts can be deleted; a published event has to be cancelled instead."
        confirmLabel="Delete draft"
        danger
        onConfirm={remove}
        onClose={() => setDialog(null)}
      />
    </>
  );
}
