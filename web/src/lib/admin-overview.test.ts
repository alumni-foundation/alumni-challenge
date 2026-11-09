import { describe, expect, it } from "vitest";
import { attentionRows, bucketSignups, auditSentence, changeOf, chartableSignups, dropOffSentence, firstNameOf, funnelRows, greetingFor, overviewPath, percentOf, type OverviewFunnelStep } from "./admin-overview";

describe("greetingFor (Nairobi time, UTC+3)", () => {
  it("switches at 12:00 and 17:00 Nairobi", () => {
    expect(greetingFor(new Date("2026-10-24T08:59:00Z"))).toBe("Good morning");
    expect(greetingFor(new Date("2026-10-24T09:00:00Z"))).toBe("Good afternoon");
    expect(greetingFor(new Date("2026-10-24T13:59:00Z"))).toBe("Good afternoon");
    expect(greetingFor(new Date("2026-10-24T14:00:00Z"))).toBe("Good evening");
  });
  it("uses Nairobi, not the viewer's clock, across midnight UTC", () => {
    expect(greetingFor(new Date("2026-10-24T21:30:00Z"))).toBe("Good morning");
  });
});

describe("firstNameOf", () => {
  it("capitalises the first word and copes with no name", () => {
    expect(firstNameOf("  jordan ellis ")).toBe("Jordan");
    expect(firstNameOf("")).toBeNull();
    expect(firstNameOf(undefined)).toBeNull();
  });
});

describe("changeOf", () => {
  it("is null when the API had nothing to compare with", () => {
    expect(changeOf({ value: 5, previous: 0, change_percent: null }, "x")).toBeNull();
    expect(changeOf(undefined, "x")).toBeNull();
  });
  it("shows direction and a readable label", () => {
    expect(changeOf({ value: 12, previous: 10, change_percent: 20 }, "the last 30 days")).toMatchObject({ text: "+20%", direction: "up" });
    expect(changeOf({ value: 8, previous: 10, change_percent: -20.4 }, "x")).toMatchObject({ text: "−20%", direction: "down" });
    expect(changeOf({ value: 10, previous: 10, change_percent: 0 }, "x")).toMatchObject({ text: "0%", direction: "flat" });
  });
});

const steps = (...counts: number[]): OverviewFunnelStep[] =>
  ["signed_up", "profile_complete", "verified", "connected", "booked_an_event"].slice(0, counts.length).map((step, i) => ({ step, count: counts[i], percent_of_previous: null }));

describe("percentOf", () => {
  it("never divides by zero", () => {
    expect(percentOf(0, 0)).toBe(0);
    expect(percentOf(5, 0)).toBe(0);
  });
  it("keeps 'a few' off 0% and 'almost all' off 100%", () => {
    expect(percentOf(1, 1000)).toBe(1);
    expect(percentOf(999, 1000)).toBe(99);
    expect(percentOf(1000, 1000)).toBe(100);
    expect(percentOf(0, 10)).toBe(0);
  });
  it("caps a part larger than its whole", () => {
    expect(percentOf(12, 10)).toBe(100);
  });
});

describe("funnelRows", () => {
  it("measures bars and percents against Signed up, and conversion against the step before", () => {
    const r = funnelRows(steps(412, 300, 150, 90, 30));
    expect(r.map((x) => x.percentOfFirst)).toEqual([100, 73, 36, 22, 7]);
    expect(r[1].share).toBeCloseTo(300 / 412);
    expect(r.map((x) => x.lost)).toEqual([0, 112, 150, 60, 60]);
    expect(r.map((x) => x.continued)).toEqual([null, 73, 50, 60, 33]);
  });
  it("gives a zero step a zero share but still a row and a percent", () => {
    const r = funnelRows(steps(2, 0, 0, 0, 0));
    expect(r[1]).toMatchObject({ count: 0, share: 0, percentOfFirst: 0, lost: 2, continued: 0 });
    expect(r[2].continued).toBeNull();
  });
  it("copes with a Signed up of 0 (no NaN, no Infinity)", () => {
    const r = funnelRows(steps(0, 0, 0, 0, 0));
    for (const x of r) {
      expect(x.share).toBe(0);
      expect(x.percentOfFirst).toBe(0);
      expect(x.lost).toBe(0);
    }
    expect(JSON.stringify(r)).not.toMatch(/NaN|null.*Infinity/);
  });
  it("is empty for no steps, and never reports a negative drop", () => {
    expect(funnelRows([])).toEqual([]);
    expect(funnelRows(steps(10, 12))[1]).toMatchObject({ lost: 0, continued: 100, share: 1 });
  });
});

describe("dropOffSentence", () => {
  it("names the gap that lost the most members", () => {
    expect(dropOffSentence(funnelRows(steps(412, 300, 150, 90, 30)))).toBe("The biggest drop-off is between Profile complete and Verified (150 members).");
  });
  it("takes the earlier gap on a tie and says 'member' for one", () => {
    expect(dropOffSentence(funnelRows(steps(10, 9, 8)))).toContain("between Signed up and Profile complete (1 member)");
  });
  it("says nothing when nobody signed up or nobody dropped", () => {
    expect(dropOffSentence(funnelRows(steps(0, 0, 0)))).toBeNull();
    expect(dropOffSentence(funnelRows(steps(5, 5, 5)))).toBeNull();
    expect(dropOffSentence([])).toBeNull();
  });
});

describe("chartableSignups", () => {
  const month = (withData: number) => Array.from({ length: 30 }, (_, i) => ({ day: `2026-10-${String(i + 1).padStart(2, "0")}`, count: i < withData ? 1 : 0 }));
  it("needs sign-ups on at least three different days, however many zero days the API sends", () => {
    expect(chartableSignups(month(2))).toBeNull();
    expect(chartableSignups(month(0))).toBeNull();
    expect(chartableSignups(month(3))).toHaveLength(30);
    expect(chartableSignups(null)).toBeNull();
  });
});

describe("auditSentence", () => {
  it("is plain and never invents a person", () => {
    expect(auditSentence("alumni_profile.verify", "Amina")).toBe("Amina verified an alumni profile");
    expect(auditSentence("event_question.create", null, "event_question")).toBe("Someone added an event question");
    expect(auditSentence("booking.payment_confirmed")).toBe("Someone confirmed a payment for a booking");
    expect(auditSentence("something.new_thing")).toBe("Someone made a change");
  });
});

describe("attentionRows", () => {
  const all = { reports_open: 2, reports_reviewing: 1, verification_requests_waiting: 3, payments_waiting_confirmation: 4, refunds_due: 0, events_in_draft: 1 };
  it("leaves out numbers the role cannot see", () => {
    const rows = attentionRows({ ...all, reports_open: null, reports_reviewing: null }, { kind: "school", organizationId: "s1" });
    expect(rows.map((r) => r.key)).toEqual(["verification", "payments", "refunds", "drafts"]);
    expect(rows[0].href).toBe("/school/s1/roster");
  });
  it("sends reports to the reports queue", () => {
    expect(attentionRows(all, { kind: "platform", organizationId: null })[0]).toMatchObject({ key: "reports", href: "/admin/reports", count: 2 });
  });
});

describe("overviewPath", () => {
  it("adds the organization only when scoped", () => {
    expect(overviewPath("90d", null)).toBe("admin/overview?period=90d");
    expect(overviewPath("30d", "abc")).toBe("admin/overview?period=30d&organization_id=abc");
  });
});

describe("bucketSignups", () => {
  it("keeps short periods day by day and sums longer ones without losing a sign-up", () => {
    const days = Array.from({ length: 365 }, (_, i) => ({ day: `d${i}`, count: i % 3 }));
    const bars = bucketSignups(days, 52);
    expect(bars.length).toBeLessThanOrEqual(52);
    expect(bars.reduce((n, b) => n + b.count, 0)).toBe(days.reduce((n, d) => n + d.count, 0));
    expect(bucketSignups(days.slice(0, 30))).toHaveLength(30);
  });
});
