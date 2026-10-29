import { describe, expect, it } from "vitest";
import type { Membership, Role } from "@/lib/api/types";
import { grantablePlatformRoles, isSuperAdmin, landingFor, orgIdsWithRole } from "./roles";

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

  it("sends a manager with both event and sports roles to whichever is listed first", () => {
    expect(landingFor([m("sports_manager", SCHOOL_A), m("event_manager", SCHOOL_B)])).toBe("/events");
    expect(landingFor([m("event_manager", SCHOOL_B), m("sports_manager", SCHOOL_A)])).toBe(`/organizer/${SCHOOL_B}`);
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

describe("orgIdsWithRole", () => {
  it("lists each organization once, in membership order", () => {
    expect(orgIdsWithRole([m("school_admin", SCHOOL_B), m("school_admin", SCHOOL_A), m("school_admin", SCHOOL_B), m("partner_admin", PARTNER)], "school_admin")).toEqual([SCHOOL_B, SCHOOL_A]);
    expect(orgIdsWithRole([m("admin")], "admin")).toEqual([]);
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
