import { describe, expect, it } from "vitest";
import type { Membership, Role } from "@/lib/api/types";
import { currentViewKey, grantablePlatformRoles, isSuperAdmin, landingFor, viewsFor } from "./roles";

const SCHOOL_A = "11111111-1111-4111-8111-111111111111";
const SCHOOL_B = "22222222-2222-4222-8222-222222222222";
const PARTNER = "33333333-3333-4333-8333-333333333333";

let n = 0;
const m = (role: Role, organization_id: string | null = null): Membership => ({
  id: `m-${n++}`,
  user_id: "u-1",
  organization_id,
  role,
});

describe("landingFor", () => {
  it("sends ordinary members and people with no roles to the member home", () => {
    expect(landingFor([])).toBe("/home");
    expect(landingFor([m("alumni")])).toBe("/home");
  });

  it("sends an event manager to their organization's dashboard and a sports manager to Events", () => {
    expect(landingFor([m("event_manager", SCHOOL_A)])).toBe(`/organizer/${SCHOOL_A}`);
    expect(landingFor([m("sports_manager", SCHOOL_A)])).toBe("/events");
  });

  it("sends admins and super admins to /admin and moderators to the reports queue", () => {
    expect(landingFor([m("admin")])).toBe("/admin");
    expect(landingFor([m("super_admin")])).toBe("/admin");
    expect(landingFor([m("moderator")])).toBe("/admin/reports");
  });

  it("sends a school admin and a partner admin to their own organization", () => {
    expect(landingFor([m("school_admin", SCHOOL_A)])).toBe(`/school/${SCHOOL_A}`);
    expect(landingFor([m("partner_admin", PARTNER)])).toBe(`/partner/${PARTNER}`);
  });

  it("lets the highest role win when someone holds several", () => {
    expect(landingFor([m("school_admin", SCHOOL_A), m("moderator"), m("admin")])).toBe("/admin");
    expect(landingFor([m("school_admin", SCHOOL_A), m("moderator")])).toBe("/admin/reports");
    expect(landingFor([m("partner_admin", PARTNER), m("school_admin", SCHOOL_A)])).toBe(`/school/${SCHOOL_A}`);
  });

  it("shows a picker first when someone runs several schools", () => {
    expect(landingFor([m("school_admin", SCHOOL_A), m("school_admin", SCHOOL_B)])).toBe("/school");
  });

  it("does not treat the same school listed twice as several schools", () => {
    expect(landingFor([m("school_admin", SCHOOL_A), m("school_admin", SCHOOL_A)])).toBe(`/school/${SCHOOL_A}`);
  });
});

describe("viewsFor", () => {
  it("always starts with the member view", () => {
    expect(viewsFor([]).map((v) => v.key)).toEqual(["member"]);
    expect(viewsFor([m("event_manager", SCHOOL_A)]).map((v) => v.key)).toEqual(["member", `organizer:${SCHOOL_A}`]);
    expect(viewsFor([m("sports_manager", SCHOOL_A)]).map((v) => v.key)).toEqual(["member", `sports:${SCHOOL_A}`]);
  });

  it("lists one entry per staff role and organization, highest first", () => {
    const keys = viewsFor([
      m("partner_admin", PARTNER),
      m("school_admin", SCHOOL_B),
      m("school_admin", SCHOOL_A),
      m("moderator"),
      m("admin"),
    ]).map((v) => v.key);
    expect(keys).toEqual(["member", "platform", "moderator", `school:${SCHOOL_B}`, `school:${SCHOOL_A}`, `partner:${PARTNER}`]);
  });

  it("gives someone who is both admin and super admin a single platform view", () => {
    const platform = viewsFor([m("admin"), m("super_admin")]).filter((v) => v.kind === "platform");
    expect(platform).toHaveLength(1);
    expect(platform[0].role).toBe("super_admin");
  });
});

describe("currentViewKey", () => {
  it("gives event and sports managers their own navigation", () => {
    const ev = viewsFor([m("event_manager", SCHOOL_A)]);
    expect(currentViewKey(`/organizer/${SCHOOL_A}`, ev)).toBe(`organizer:${SCHOOL_A}`);
    const sp = viewsFor([m("sports_manager", SCHOOL_A)]);
    expect(currentViewKey("/events/abc", sp)).toBe(`sports:${SCHOOL_A}`);
    expect(currentViewKey("/home", sp)).toBe("member");
    // A school admin who is also a sports manager keeps the school navigation on the events pages.
    expect(currentViewKey("/events", viewsFor([m("school_admin", SCHOOL_A), m("sports_manager", SCHOOL_A)]))).toBe("member");
  });

  it("keeps a platform admin or moderator in their own navigation on school and partner pages", () => {
    const platform = viewsFor([m("admin")]);
    expect(currentViewKey(`/school/${SCHOOL_A}/roster`, platform)).toBe("platform");
    expect(currentViewKey(`/partner/${PARTNER}`, platform)).toBe("platform");
    expect(currentViewKey(`/school/${SCHOOL_A}`, viewsFor([m("moderator")]))).toBe("moderator");
    expect(currentViewKey(`/school/${SCHOOL_A}`, viewsFor([m("alumni")]))).toBe("member");
  });

  const views = viewsFor([m("admin"), m("moderator"), m("school_admin", SCHOOL_A)]);

  it("marks the school view while inside that school", () => {
    expect(currentViewKey(`/school/${SCHOOL_A}/edit`, views)).toBe(`school:${SCHOOL_A}`);
  });
  it("marks the admin area as the platform view", () => {
    expect(currentViewKey("/admin/organizations", views)).toBe("platform");
  });
  it("falls back to the member view everywhere else", () => {
    expect(currentViewKey("/directory", views)).toBe("member");
  });
});

describe("grantablePlatformRoles", () => {
  it("lets a super admin give any platform role", () => {
    expect(grantablePlatformRoles([m("super_admin")])).toEqual(["moderator", "admin", "super_admin"]);
    expect(isSuperAdmin([m("super_admin")])).toBe(true);
  });
  it("lets an admin give the moderator role only", () => {
    expect(grantablePlatformRoles([m("admin")])).toEqual(["moderator"]);
    expect(isSuperAdmin([m("admin")])).toBe(false);
  });
  it("gives moderators, organization admins and members nothing to grant", () => {
    expect(grantablePlatformRoles([m("moderator")])).toEqual([]);
    expect(grantablePlatformRoles([m("school_admin", SCHOOL_A)])).toEqual([]);
    expect(grantablePlatformRoles([])).toEqual([]);
  });
});

describe("currentViewKey for the school and partner pickers", () => {
  it("marks the school view on the bare /school picker", () => {
    const v = viewsFor([m("school_admin", SCHOOL_A), m("school_admin", SCHOOL_B)]);
    expect(currentViewKey("/school", v)).toBe(`school:${SCHOOL_A}`);
  });
});
