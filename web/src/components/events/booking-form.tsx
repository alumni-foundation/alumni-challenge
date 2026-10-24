"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useRef, useState } from "react";
import { Alert, Button, Card, Input, Select, Textarea } from "@/components/ui";
import { api } from "@/lib/api/client";
import { useOrgs } from "@/lib/api/hooks";
import type { AnswerInput, Booking, BookingCreate, EventDetail, EventQuestion, ParticipantInput } from "@/lib/api/types";
import { bookingProblem, type BookingProblem } from "@/lib/booking-problem";
import { newIdempotencyKey, priceText } from "@/lib/events";
import { cn } from "@/lib/utils";
import { SlotPicker } from "./slot-picker";

type AnswerValue = string | number | boolean | string[];
type Errors = Record<string, string>;

const MAX_PARTY = 4;

function CheckRow({ id, checked, onChange, children, invalid, describedBy }: { id: string; checked: boolean; onChange: (v: boolean) => void; children: React.ReactNode; invalid?: boolean; describedBy?: string }) {
  return (
    <label htmlFor={id} className="flex min-h-11 cursor-pointer items-start gap-3 py-1.5 text-small text-ink">
      <input
        id={id}
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        aria-invalid={invalid || undefined}
        aria-describedby={describedBy}
        className="mt-0.5 size-5 shrink-0 rounded border-2 border-[#857b6d] accent-[#1b1713] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
      />
      <span>{children}</span>
    </label>
  );
}

function FieldBlock({ id, label, hint, error, children }: { id: string; label: React.ReactNode; hint?: string; error?: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="block text-small font-medium text-ink">{label}</label>
      {children}
      {error ? <p id={`${id}-msg`} className="text-small text-brand-ink" role="alert">{error}</p> : hint ? <p id={`${id}-msg`} className="text-caption text-muted">{hint}</p> : null}
    </div>
  );
}

/**
 * The booking panel: session, party, named players, the event's own questions, consents and the total.
 * One button sends it. The price is only shown: the server works it out.
 */
export function BookingForm({ event, defaultName, email }: { event: EventDetail; defaultName: string; email: string }) {
  const router = useRouter();
  const qc = useQueryClient();
  const schools = useOrgs("school");
  const free = event.price_minor <= 0;
  const open = event.slots.filter((s) => s.availability !== "full" && (s.spots_left === null || s.spots_left > 0));
  const [slotId, setSlotId] = useState(event.slots.length === 1 && open.length === 1 ? open[0].id : "");
  const [party, setParty] = useState(1);
  const [names, setNames] = useState<string[]>([defaultName, "", "", ""]);
  const [emails, setEmails] = useState<string[]>(["", "", "", ""]);
  const [phones, setPhones] = useState<string[]>(["", "", "", ""]);
  const [answers, setAnswers] = useState<Record<string, AnswerValue>>({});
  const [accepted, setAccepted] = useState<Record<string, boolean>>({});
  const [others, setOthers] = useState(false);
  const [errors, setErrors] = useState<Errors>({});
  const [problem, setProblem] = useState<BookingProblem | null>(null);
  const [busy, setBusy] = useState(false);
  const attempt = useRef<{ key: string; body: string } | null>(null);
  const alertRef = useRef<HTMLDivElement>(null);

  const slot = event.slots.find((s) => s.id === slotId);
  const maxParty = Math.max(1, Math.min(event.max_party_size, MAX_PARTY, slot?.spots_left ?? MAX_PARTY));
  const partySize = Math.min(party, maxParty);
  const questions = useMemo(() => [...event.questions].sort((a, b) => a.position - b.position), [event.questions]);
  const total = event.price_minor * partySize;
  const answerKey = (q: EventQuestion, pos: number) => `${q.key}|${pos}`;
  // A message about a field goes away as soon as the person works on that field.
  const clearError = (id: string) => setErrors((e) => (e[id] ? { ...e, [id]: "" } : e));
  const setAnswer = (q: EventQuestion, pos: number, v: AnswerValue | undefined) => {
    clearError(`q-${q.key}-${pos}`);
    setAnswers((a) => {
      const next = { ...a };
      if (v === undefined || v === "" || (Array.isArray(v) && v.length === 0)) delete next[answerKey(q, pos)];
      else next[answerKey(q, pos)] = v;
      return next;
    });
  };
  const positions = (q: EventQuestion) => (q.asked_of === "each_participant" ? Array.from({ length: partySize }, (_, i) => i + 1) : [1]);

  function validate(): Errors {
    const e: Errors = {};
    if (!slotId) e.slot = "Choose a session.";
    for (let i = 0; i < partySize; i++) if (!names[i].trim()) e[`p${i + 1}-name`] = i === 0 ? "Enter your name." : `Enter player ${i + 1}’s name.`;
    for (const q of questions) {
      if (!q.required) continue;
      for (const pos of positions(q)) {
        const v = answers[answerKey(q, pos)];
        const answered = q.kind === "boolean" ? true : v !== undefined && v !== "";
        if (!answered) e[`q-${q.key}-${pos}`] = "This answer is needed.";
      }
    }
    for (const c of event.consents) if (c.required && !accepted[c.key]) e[`consent-${c.key}`] = "Please tick this box to continue.";
    if (partySize > 1 && !others) e.others = "Please confirm this to book for more than one person.";
    return e;
  }

  function focusFirst(e: Errors) {
    const first = Object.keys(e)[0];
    if (!first) return;
    const target = document.getElementById(first === "slot" ? "slot-group" : first === "others" ? "others" : first === "consents" ? "consents-group" : first);
    if (target instanceof HTMLElement) {
      target.scrollIntoView({ block: "center", behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
      target.focus({ preventScroll: true });
    }
  }

  async function submit(ev: React.FormEvent) {
    ev.preventDefault();
    if (busy) return;
    setProblem(null);
    const found = validate();
    setErrors(found);
    if (Object.keys(found).length) {
      window.setTimeout(() => focusFirst(found), 0);
      return;
    }
    const participants: ParticipantInput[] = Array.from({ length: partySize }, (_, i) => ({
      full_name: names[i].trim(),
      // Shown in "who is going" once that exists (the server default); nothing lists people yet.
      listed: true,
      // The booker's email is their account's; the others' are optional and only used to send them their own ticket.
      ...(i > 0 && emails[i].trim() ? { email: emails[i].trim() } : {}),
      ...(phones[i].trim() ? { phone: phones[i].trim() } : {}),
    }));
    const list: AnswerInput[] = [];
    for (const q of questions) for (const pos of positions(q)) {
      const v = answers[answerKey(q, pos)];
      if (v !== undefined) list.push({ question_key: q.key, position: pos, value: v });
      else if (q.kind === "boolean" && q.required) list.push({ question_key: q.key, position: pos, value: false });
    }
    const body: BookingCreate = {
      slot_id: slotId,
      participants,
      answers: list,
      accepted_consents: event.consents.filter((c) => accepted[c.key]).map((c) => c.key),
      others_consent_confirmed: partySize > 1 ? others : false,
    };
    // The same booking, tried again (a double click, a timeout), keeps its key so it can only ever be made once.
    const text = JSON.stringify(body);
    if (attempt.current?.body !== text) attempt.current = { key: newIdempotencyKey(), body: text };
    setBusy(true);
    try {
      const booking = await api<Booking>(`events/${event.id}/bookings`, { method: "POST", body, headers: { "Idempotency-Key": attempt.current.key } });
      attempt.current = null;
      void qc.invalidateQueries({ queryKey: ["event", event.id] });
      void qc.invalidateQueries({ queryKey: ["bookings"] });
      void qc.invalidateQueries({ queryKey: ["tickets"] });
      router.push(`/bookings/${booking.id}?new=1`);
    } catch (err) {
      const p = bookingProblem(err);
      if (!p.keepKey) attempt.current = null;
      if (p.refresh) void qc.invalidateQueries({ queryKey: ["event", event.id] });
      setProblem(p);
      if (p.field) setErrors((cur) => ({ ...cur, [p.field as string]: p.message }));
      setBusy(false);
      window.setTimeout(() => (p.field ? focusFirst({ [p.field]: p.message }) : alertRef.current?.focus()), 0);
    }
  }

  function renderQuestion(q: EventQuestion, pos: number) {
    const id = `q-${q.key}-${pos}`;
    const err = errors[id];
    const label = (
      <>
        {q.label}
        {!q.required && <span className="font-normal text-muted"> (optional)</span>}
        {q.asked_of === "each_participant" && partySize > 1 && <span className="font-normal text-muted"> · {pos === 1 ? "you" : `player ${pos}`}</span>}
      </>
    );
    const v = answers[answerKey(q, pos)];
    const aria = { "aria-invalid": err ? true : undefined, "aria-describedby": err ? `${id}-msg` : undefined } as const;
    const options = (q.options ?? []) as { value: string; label: string }[];
    let control: React.ReactNode;
    switch (q.kind) {
      case "long_text":
        control = <Textarea id={id} rows={3} value={typeof v === "string" ? v : ""} onChange={(e) => setAnswer(q, pos, e.target.value)} {...aria} />;
        break;
      case "number":
        control = <Input id={id} type="number" inputMode="decimal" step="any" value={typeof v === "number" ? String(v) : ""} onChange={(e) => setAnswer(q, pos, e.target.value === "" ? undefined : Number(e.target.value))} {...aria} />;
        break;
      case "boolean":
        return (
          <div key={id}>
            <CheckRow id={id} checked={v === true} onChange={(c) => setAnswer(q, pos, c)}>{label}</CheckRow>
          </div>
        );
      case "choice":
        control = (
          <Select id={id} value={typeof v === "string" ? v : ""} onChange={(e) => setAnswer(q, pos, e.target.value)} {...aria}>
            <option value="">Choose…</option>
            {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </Select>
        );
        break;
      case "multi_choice":
        control = (
          <div role="group" aria-labelledby={`${id}-label`} id={id} tabIndex={-1} className="space-y-0.5 focus:outline-none">
            {options.map((o) => {
              const cur = Array.isArray(v) ? v : [];
              return (
                <CheckRow key={o.value} id={`${id}-${o.value}`} checked={cur.includes(o.value)} onChange={(c) => setAnswer(q, pos, c ? [...cur, o.value] : cur.filter((x) => x !== o.value))}>{o.label}</CheckRow>
              );
            })}
          </div>
        );
        break;
      case "school":
        control = (
          <Select id={id} value={typeof v === "string" ? v : ""} onChange={(e) => setAnswer(q, pos, e.target.value)} {...aria}>
            <option value="">Choose a school…</option>
            {(schools.data ?? []).map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </Select>
        );
        break;
      default:
        control = <Input id={id} type="text" value={typeof v === "string" ? v : ""} onChange={(e) => setAnswer(q, pos, e.target.value)} {...aria} />;
    }
    return (
      <FieldBlock key={id} id={id} label={<span id={`${id}-label`}>{label}</span>} error={err}>{control}</FieldBlock>
    );
  }

  return (
    <Card className="p-5 sm:p-7" elevation="raised">
      <form onSubmit={submit} noValidate className="space-y-7" aria-label={free ? "RSVP" : "Reserve your places"}>
        <h2 className="text-heading">{free ? "RSVP" : "Reserve your places"}</h2>

        {problem && (
          <div ref={alertRef} tabIndex={-1} className="focus:outline-none">
            <Alert>
              <p>{problem.message}</p>
              {problem.link && <Link href={problem.link.href} className="mt-1 inline-flex min-h-11 items-center font-semibold text-brand-ink hover:underline">{problem.link.label}</Link>}
            </Alert>
          </div>
        )}

        <SlotPicker slots={event.slots} value={slotId} onChange={(id) => { setSlotId(id); setErrors((e) => ({ ...e, slot: "" })); }} error={errors.slot} />

        <div className="space-y-4">
          <FieldBlock id="party" label="How many people?" hint={slot?.spots_left != null ? `Up to ${maxParty} in this session.` : `Up to ${maxParty} per booking.`} error={errors.party}>
            <Select id="party" value={String(partySize)} onChange={(e) => setParty(Number(e.target.value))} className="max-w-[10rem]">
              {Array.from({ length: maxParty }, (_, i) => i + 1).map((n) => <option key={n} value={n}>{n}</option>)}
            </Select>
          </FieldBlock>

          <fieldset className="min-w-0 space-y-4">
            <legend className="mb-1 text-small font-semibold text-ink">{partySize > 1 ? "Who is coming" : "Your details"}</legend>
            {Array.from({ length: partySize }, (_, i) => {
              const n = i + 1;
              return (
                <div key={n} className="space-y-3 rounded-2xl border border-line bg-canvas/60 p-4">
                  <p className="text-small font-semibold text-ink">{n === 1 ? "You" : `Player ${n}`}</p>
                  <FieldBlock id={`p${n}-name`} label="Full name" error={errors[`p${n}-name`]}>
                    <Input id={`p${n}-name`} autoComplete={n === 1 ? "name" : "off"} value={names[i]} onChange={(e) => { clearError(`p${n}-name`); setNames((x) => x.map((v, k) => (k === i ? e.target.value : v))); }} aria-invalid={errors[`p${n}-name`] ? true : undefined} aria-describedby={errors[`p${n}-name`] ? `p${n}-name-msg` : undefined} />
                  </FieldBlock>
                  <div className="grid gap-3 sm:grid-cols-2">
                    {n === 1 ? (
                      <p className="min-w-0 self-end pb-2 text-small text-ink [overflow-wrap:anywhere]">Your ticket goes to <strong className="font-semibold">{email}</strong></p>
                    ) : (
                      <FieldBlock id={`p${n}-email`} label={<>Email <span className="font-normal text-muted">(optional)</span></>} hint="Only used to send them their own ticket.">
                        <Input id={`p${n}-email`} type="email" inputMode="email" autoComplete="off" value={emails[i]} onChange={(e) => setEmails((x) => x.map((v, k) => (k === i ? e.target.value : v)))} aria-describedby={`p${n}-email-msg`} />
                      </FieldBlock>
                    )}
                    <FieldBlock id={`p${n}-phone`} label={<>Phone <span className="font-normal text-muted">(optional)</span></>}>
                      <Input id={`p${n}-phone`} type="tel" inputMode="tel" autoComplete={n === 1 ? "tel" : "off"} value={phones[i]} onChange={(e) => setPhones((x) => x.map((v, k) => (k === i ? e.target.value : v)))} />
                    </FieldBlock>
                  </div>
                </div>
              );
            })}
          </fieldset>
        </div>

        {questions.length > 0 && (
          <fieldset className="min-w-0 space-y-4">
            <legend className="mb-1 text-small font-semibold text-ink">A few questions</legend>
            {questions.map((q) => (
              <div key={q.id} className={cn("space-y-4", q.asked_of === "each_participant" && partySize > 1 && "rounded-2xl border border-line bg-canvas/60 p-4")}>
                {positions(q).map((pos) => renderQuestion(q, pos))}
              </div>
            ))}
          </fieldset>
        )}

        {(event.consents.length > 0 || partySize > 1) && (
          <fieldset id="consents-group" tabIndex={-1} className="min-w-0 space-y-1 focus:outline-none">
            <legend className="mb-1 text-small font-semibold text-ink">Before you book</legend>
            {event.consents.map((c) => (
              <div key={c.id}>
                <CheckRow id={`consent-${c.key}`} checked={Boolean(accepted[c.key])} onChange={(v) => { clearError(`consent-${c.key}`); setAccepted((a) => ({ ...a, [c.key]: v })); }} invalid={Boolean(errors[`consent-${c.key}`])} describedBy={errors[`consent-${c.key}`] ? `consent-${c.key}-msg` : undefined}>
                  {c.text}{!c.required && <span className="text-muted"> (optional)</span>}
                </CheckRow>
                {errors[`consent-${c.key}`] && <p id={`consent-${c.key}-msg`} className="pl-8 text-small text-brand-ink" role="alert">{errors[`consent-${c.key}`]}</p>}
              </div>
            ))}
            {partySize > 1 && (
              <div>
                <CheckRow id="others" checked={others} onChange={(v) => { clearError("others"); setOthers(v); }} invalid={Boolean(errors.others)} describedBy={errors.others ? "others-msg" : undefined}>
                  I confirm I may share the other players’ details with the organizers.
                </CheckRow>
                {errors.others && <p id="others-msg" className="pl-8 text-small text-brand-ink" role="alert">{errors.others}</p>}
              </div>
            )}
          </fieldset>
        )}

        <div className="flex flex-col gap-4 border-t border-line pt-5 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-small text-ink">Total</p>
            <p className="font-serif text-[2rem] font-semibold leading-none text-ink [font-variant-numeric:lining-nums]" aria-live="polite">{priceText(total, event.currency)}</p>
            {!free && <p className="mt-1.5 text-caption text-muted">{partySize} × {priceText(event.price_minor, event.currency)}. Your places are held for {event.hold_minutes} minutes while you pay.</p>}
          </div>
          <Button type="submit" variant="dark" loading={busy} className="sm:min-w-44">{free ? "RSVP" : "Reserve"}</Button>
        </div>
      </form>
    </Card>
  );
}
