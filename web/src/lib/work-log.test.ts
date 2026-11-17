import { describe, expect, it } from "vitest";
import type { TeamWorkLogEntry, WorkLogEntry } from "@/lib/api/types";
import { formatCompleted, formatDay, groupByDay, groupByPerson, isTodayGroup } from "./work-log";

let n = 0;
const mine = (entry_date: string, created_at: string, over: Partial<WorkLogEntry> = {}): WorkLogEntry => ({
  id: `e-${n++}`,
  kind: "planned",
  text: `line ${n}`,
  entry_date,
  created_at,
  completed_at: null,
  editable: false,
  ...over,
});
const team = (author: string, name: string, entry_date: string, created_at: string): TeamWorkLogEntry => ({
  id: `t-${n++}`,
  author_user_id: author,
  author_name: name,
  author_email: `${author}@example.com`,
  kind: "done",
  text: `line ${n}`,
  entry_date,
  created_at,
  completed_at: created_at,
});

describe("groupByDay", () => {
  it("puts the newest day first and keeps each day's lines in the order they were added", () => {
    const a = mine("2026-11-16", "2026-11-16T08:00:00+03:00");
    const b = mine("2026-11-17", "2026-11-17T11:00:00+03:00");
    const c = mine("2026-11-17", "2026-11-17T09:00:00+03:00");
    const d = mine("2026-11-14", "2026-11-14T09:00:00+03:00");

    const groups = groupByDay([a, b, c, d]);

    expect(groups.map((g) => g.date)).toEqual(["2026-11-17", "2026-11-16", "2026-11-14"]);
    expect(groups[0].entries).toEqual([c, b]);
  });

  it("groups by the server's date string, so a line from just after midnight in Nairobi stays on its own day", () => {
    // 00:30 on 18 Nov in Nairobi is 21:30 on 17 Nov in UTC; the browser's zone must not matter.
    const late = mine("2026-11-18", "2026-11-17T21:30:00Z");
    const earlier = mine("2026-11-17", "2026-11-17T20:59:00Z");

    expect(groupByDay([earlier, late]).map((g) => g.date)).toEqual(["2026-11-18", "2026-11-17"]);
  });

  it("returns nothing for no entries", () => {
    expect(groupByDay([])).toEqual([]);
  });

  it("calls a day today only when the server says its lines are still editable", () => {
    const [open] = groupByDay([mine("2026-11-17", "2026-11-17T09:00:00Z", { editable: true })]);
    const [locked] = groupByDay([mine("2026-11-16", "2026-11-16T09:00:00Z")]);
    expect(isTodayGroup(open)).toBe(true);
    expect(isTodayGroup(locked)).toBe(false);
  });
});

describe("groupByPerson", () => {
  it("lists people A to Z, then each person's days newest first", () => {
    const zed1 = team("u-z", "Zed Okello", "2026-11-17", "2026-11-17T09:00:00Z");
    const amy1 = team("u-a", "amy Njeri", "2026-11-15", "2026-11-15T09:00:00Z");
    const amy2 = team("u-a", "amy Njeri", "2026-11-17", "2026-11-17T10:00:00Z");
    const amy3 = team("u-a", "amy Njeri", "2026-11-17", "2026-11-17T08:00:00Z");

    const people = groupByPerson([zed1, amy1, amy2, amy3]);

    expect(people.map((p) => p.name)).toEqual(["amy Njeri", "Zed Okello"]);
    expect(people[0].days.map((d) => d.date)).toEqual(["2026-11-17", "2026-11-15"]);
    expect(people[0].days[0].entries).toEqual([amy3, amy2]);
    expect(people[1].email).toBe("u-z@example.com");
  });

  it("keeps two people with the same name apart", () => {
    const people = groupByPerson([
      team("u-1", "Sam Kamau", "2026-11-17", "2026-11-17T09:00:00Z"),
      team("u-2", "Sam Kamau", "2026-11-17", "2026-11-17T09:05:00Z"),
    ]);
    expect(people).toHaveLength(2);
  });
});

describe("dates", () => {
  it("writes a day heading from the date text alone", () => {
    expect(formatDay("2026-11-17")).toBe("Tuesday 17 November 2026");
    expect(formatDay("2026-01-01")).toBe("Thursday 1 January 2026");
    expect(formatDay("nonsense")).toBe("nonsense");
  });

  it("shows the time in Nairobi, adding the day when it was finished on a later one", () => {
    // 11:20 UTC is 14:20 in Nairobi.
    expect(formatCompleted("2026-11-17T11:20:00Z", "2026-11-17")).toBe("14:20");
    // 21:30 UTC on the 17th is 00:30 on the 18th in Nairobi, so it needs its day.
    expect(formatCompleted("2026-11-17T21:30:00Z", "2026-11-17")).toBe("18 Nov, 00:30");
  });
});
