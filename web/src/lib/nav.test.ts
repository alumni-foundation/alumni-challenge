import { describe, expect, it } from "vitest";
import type { Membership, Role } from "@/lib/api/types";
import { navGroupsFor } from "./nav";

const SCHOOL_A = "11111111-1111-4111-8111-111111111111";
const SCHOOL_B = "22222222-2222-4222-8222-222222222222";
const PARTNER = "33333333-3333-4333-8333-333333333333";
const NAMES: Record<string, string> = { [SCHOOL_A]: "Alliance High", [SCHOOL_B]: "Mang'u High", [PARTNER]: "Acme Partners" };

let n = 0;
const m = (role: Role, organization_id: string | null = null): Membership => ({ id: `m-${n++}`, user_id: "u-1", organization_id, role });
const groups = (ms: Membership[]) => navGroupsFor(ms, (id) => NAMES[id]);
const titles = (ms: Membership[]) => groups(ms).map((g) => g.title);
const hrefs = (ms: Membership[]) => groups(ms).flatMap((g) => g.items.map((i) => i.href));

describe("navGroupsFor", () => {
  it("gives everyone the Member group and nothing else when they hold no staff role", () => {
    expect(titles([])).toEqual(["Member"]);
    expect(titles([m("alumni")])).toEqual(["Member"]);
    expect(titles([m("sports_manager", SCHOOL_A)])).toEqual(["Member"]);
  });

  it("shows admins the Platform group and the reports link, super admins the same", () => {
    for (const role of ["admin", "super_admin"] as const) {
      expect(titles([m(role)])).toEqual(["Member", "Platform", "Moderation"]);
      expect(hrefs([m(role)])).toEqual(expect.arrayContaining(["/admin", "/admin/users", "/admin/organizations", "/admin/events", "/admin/roles", "/admin/activity", "/admin/reports"]));
    }
  });

  it("shows a moderator the dashboard and reports under Moderation, without Platform pages", () => {
    const g = groups([m("moderator")]);
    expect(g.map((x) => x.title)).toEqual(["Member", "Platform", "Moderation"]);
    expect(g[2].items.map((i) => i.href)).toEqual(["/admin", "/admin/reports"]);
    // The only Platform link a moderator gets is their own work log.
    expect(g[1].items.map((i) => i.href)).toEqual(["/admin/work-log"]);
    expect(hrefs([m("moderator")])).not.toContain("/admin/users");
  });

  it("gives each school or partner a group titled with its name", () => {
    const g = groups([m("school_admin", SCHOOL_A), m("school_admin", SCHOOL_B), m("partner_admin", PARTNER)]);
    expect(g.map((x) => x.title)).toEqual(["Member", "Alliance High", "Mang'u High", "Acme Partners"]);
    expect(g[1].items.map((i) => i.label)).toEqual(["Overview", "Alumni", "Team", "Activity", "Edit", "Email domains"]);
    expect(g[3].items.map((i) => i.label)).toEqual(["Overview", "Team", "Activity", "Edit"]);
    expect(g[3].items[0].href).toBe(`/partner/${PARTNER}`);
  });

  it("puts an event manager's dashboard in their organization's group, merged with the admin links", () => {
    expect(groups([m("event_manager", SCHOOL_A)])[1].items.map((i) => i.href)).toEqual([`/organizer/${SCHOOL_A}`]);
    const both = groups([m("school_admin", SCHOOL_A), m("event_manager", SCHOOL_A)]);
    expect(both).toHaveLength(2);
    expect(both[1].items.at(-1)).toMatchObject({ label: "Event dashboard", href: `/organizer/${SCHOOL_A}` });
  });

  it("falls back to a plain title until organization names have loaded", () => {
    expect(navGroupsFor([m("school_admin", SCHOOL_A)])[1].title).toBe("Your school");
  });

  it("keeps every staff landing page reachable from the sidebar", () => {
    const cases: Membership[][] = [
      [m("super_admin")], [m("admin")], [m("moderator")], [m("school_admin", SCHOOL_A)], [m("partner_admin", PARTNER)],
      [m("event_manager", SCHOOL_A)], [m("sports_manager", SCHOOL_A)],
    ];
    for (const ms of cases) expect(hrefs(ms).length).toBeGreaterThan(0);
    expect(hrefs([m("sports_manager", SCHOOL_A)])).toContain("/events");
  });

  describe("work log links", () => {
    const WORK = ["/admin/work-log", "/admin/team-work-log"];
    const workLinks = (ms: Membership[]) => hrefs(ms).filter((h) => WORK.includes(h));
    const platformItems = (ms: Membership[]) => groups(ms).find((g) => g.key === "platform")?.items.map((i) => i.label) ?? [];

    it("gives an admin 'My work log' in Platform, and no team view", () => {
      expect(workLinks([m("admin")])).toEqual(["/admin/work-log"]);
      expect(platformItems([m("admin")])).toContain("My work log");
    });

    it("gives a moderator 'My work log' in Platform", () => {
      expect(workLinks([m("moderator")])).toEqual(["/admin/work-log"]);
    });

    it("gives a super admin 'Team work log' only: they read, they do not keep one", () => {
      expect(workLinks([m("super_admin")])).toEqual(["/admin/team-work-log"]);
      expect(platformItems([m("super_admin")])).toContain("Team work log");
      expect(platformItems([m("super_admin")])).not.toContain("My work log");
      // Holding admin as well does not give a super admin a log of their own.
      expect(workLinks([m("super_admin"), m("admin")])).toEqual(["/admin/team-work-log"]);
    });

    it("shows neither link to anyone else", () => {
      const others: Membership[][] = [
        [], [m("alumni")], [m("school_admin", SCHOOL_A)], [m("partner_admin", PARTNER)],
        [m("event_manager", SCHOOL_A)], [m("sports_manager", SCHOOL_A)],
        // Admin at an organization is not the platform admin role.
        [m("admin", SCHOOL_A)],
      ];
      for (const ms of others) expect(workLinks(ms)).toEqual([]);
    });
  });
});
