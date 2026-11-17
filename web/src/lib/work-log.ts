import type { TeamWorkLogEntry, WorkLogEntry } from "./api/types";

/**
 * The work log's days are Nairobi calendar days chosen by the server and sent as "YYYY-MM-DD". They are grouped
 * and shown as text and never go through the browser's clock or time zone.
 */
export type DayGroup<T> = { date: string; entries: T[] };

type Dated = { entry_date: string; created_at: string };

/** Newest day first; inside a day, the order the lines were added. */
export function groupByDay<T extends Dated>(entries: T[]): DayGroup<T>[] {
  const byDate = new Map<string, T[]>();
  for (const e of entries) {
    const day = byDate.get(e.entry_date);
    if (day) day.push(e);
    else byDate.set(e.entry_date, [e]);
  }
  return [...byDate.entries()]
    .sort(([a], [b]) => (a < b ? 1 : a > b ? -1 : 0))
    .map(([date, list]) => ({ date, entries: [...list].sort((a, b) => Date.parse(a.created_at) - Date.parse(b.created_at)) }));
}

export type PersonGroup = {
  userId: string;
  name: string;
  email: string;
  days: DayGroup<TeamWorkLogEntry>[];
};

/** People A to Z, then each person's days newest first. */
export function groupByPerson(entries: TeamWorkLogEntry[]): PersonGroup[] {
  const byPerson = new Map<string, TeamWorkLogEntry[]>();
  for (const e of entries) {
    const list = byPerson.get(e.author_user_id);
    if (list) list.push(e);
    else byPerson.set(e.author_user_id, [e]);
  }
  return [...byPerson.entries()]
    .map(([userId, list]) => ({ userId, name: list[0].author_name, email: list[0].author_email, days: groupByDay(list) }))
    .sort((a, b) => a.name.localeCompare(b.name, "en", { sensitivity: "base" }) || a.userId.localeCompare(b.userId));
}

/** "Tuesday 17 November 2026" from "2026-11-17", computed as plain calendar arithmetic (no local time zone). */
export function formatDay(isoDate: string): string {
  const [y, m, d] = isoDate.split("-").map(Number);
  if (!y || !m || !d) return isoDate;
  return new Intl.DateTimeFormat("en-GB", { weekday: "long", day: "numeric", month: "long", year: "numeric", timeZone: "UTC" })
    .format(new Date(Date.UTC(y, m - 1, d)))
    .replace(",", "");
}

const NAIROBI = "Africa/Nairobi";
const dayInNairobi = (iso: string) => new Intl.DateTimeFormat("en-CA", { timeZone: NAIROBI }).format(new Date(iso));

/** "14:20", or "18 Nov, 09:10" when it was finished on a later day than the line belongs to. Always Nairobi time. */
export function formatCompleted(completedAt: string, entryDate: string): string {
  const time = new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit", hourCycle: "h23", timeZone: NAIROBI }).format(new Date(completedAt));
  if (dayInNairobi(completedAt) === entryDate) return time;
  const day = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", timeZone: NAIROBI }).format(new Date(completedAt));
  return `${day}, ${time}`;
}

/** A day heading: "Today" is whatever the server said is still editable, so the browser clock is never used. */
export const isTodayGroup = (group: DayGroup<WorkLogEntry>) => group.entries.some((e) => e.editable);
