import { describe, expect, it } from "vitest";
import { attentionRows, bucketSignups, auditSentence, changeOf, chartableSignups, firstNameOf, funnelShares, greetingFor, overviewPath } from "./admin-overview";

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

describe("funnelShares", () => {
  it("scales to the biggest step and keeps a sliver for a non-zero count", () => {
    const s = funnelShares([
      { step: "signed_up", count: 200, percent_of_previous: null },
      { step: "verified", count: 50, percent_of_previous: 25 },
      { step: "connected", count: 1, percent_of_previous: 2 },
      { step: "booked_an_event", count: 0, percent_of_previous: 0 },
    ]);
    expect(s).toEqual([1, 0.25, 0.04, 0]);
  });
  it("is all zero for an empty funnel", () => {
    expect(funnelShares([{ step: "signed_up", count: 0, percent_of_previous: null }])).toEqual([0]);
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
