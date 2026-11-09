import { describe, expect, it } from "vitest";
import { DEPARTMENTS, homeRouteFor, kindOf, navFor, tabsFor } from "./roles";
import type { Me } from "./useAuth";

const me = (over: Partial<Me>): Me => ({ authenticated: true, mode: "supabase", name: "x", login: "x@y.co", avatar_url: null, roles: [], ...over });

describe("roles", () => {
  it("maps server roles to one kind, highest first", () => {
    expect(kindOf(undefined)).toBe("anon");
    expect(kindOf(me({ mode: "off", authenticated: false }))).toBe("off");
    expect(kindOf(me({ authenticated: false }))).toBe("anon");
    expect(kindOf(me({ roles: [] }))).toBe("pending");
    expect(kindOf(me({ roles: ["Spa.Buyer"] }))).toBe("buyer");
    expect(kindOf(me({ roles: ["Spa.Staff"] }))).toBe("staff");
    expect(kindOf(me({ roles: ["Spa.Reviewer"] }))).toBe("reviewer");
    expect(kindOf(me({ roles: ["Spa.Reviewer", "Spa.Admin"] }))).toBe("admin");
  });

  it("shows each role only the links it may use", () => {
    expect(navFor("buyer", true)).toMatchObject({ mine: true, app: false, review: false, buyers: false, users: false, accuracy: false, agreements: false });
    expect(navFor("staff", true)).toMatchObject({ app: true, watch: true, review: false, buyers: false, users: false, mine: false, agreements: true });
    expect(navFor("reviewer", true)).toMatchObject({ review: true, buyers: true, users: false });
    expect(navFor("admin", true)).toMatchObject({ review: true, buyers: true, users: true });
    expect(Object.values(navFor("pending", true)).some(Boolean)).toBe(false);
  });

  it("keeps the full menu while the account is still loading or when the server does not enforce sign-in", () => {
    expect(navFor("anon", false)).toMatchObject({ app: true, review: true, users: false });
    expect(navFor("off", true)).toMatchObject({ app: true, review: true, buyers: true });
  });
});

const FEATURES = {
  legal: ["terms", "gap", "playbook", "crosscheck", "obligations", "agreements", "bilingual"],
  finance: ["penalty", "cashflow"],
  sales: ["terms"],
  management: ["accuracy", "obligations"],
};

describe("departments", () => {
  it("lands each department on its own home, and everyone else where they belong", () => {
    expect(DEPARTMENTS.map((d) => homeRouteFor("staff", d))).toEqual(["/app/legal", "/app/finance", "/app/sales", "/app/management"]);
    expect(homeRouteFor("staff", null)).toBe("/");          // staff with no department: Home, as before
    expect(homeRouteFor("staff", "marketing")).toBe("/");   // an unknown department is never trusted
    expect(homeRouteFor("reviewer", "legal")).toBe("/");    // reviewers and administrators are cross-cutting: no department home
    expect(homeRouteFor("admin", "finance")).toBe("/");
    expect(homeRouteFor("buyer")).toBe("/app");
    expect(homeRouteFor("pending")).toBe("/app");
    expect(homeRouteFor("off")).toBe("/");
  });

  it("shows each department only its own links", () => {
    expect(navFor("staff", true, FEATURES.legal)).toMatchObject({ app: true, watch: true, crosscheck: true, agreements: true, bilingual: true, accuracy: false, review: false, buyers: false, users: false });
    expect(navFor("staff", true, FEATURES.finance)).toMatchObject({ app: true, watch: false, crosscheck: false, agreements: false, accuracy: false, bilingual: false });
    expect(navFor("staff", true, FEATURES.sales)).toMatchObject({ app: true, watch: false, crosscheck: false, agreements: false, accuracy: false });
    expect(navFor("staff", true, FEATURES.management)).toMatchObject({ app: false, watch: true, accuracy: true, crosscheck: false, agreements: false });
  });

  it("shows each department only the contract pages it may open", () => {
    expect(tabsFor("staff", FEATURES.legal)).toEqual(["terms", "gap", "obligations", "playbook"]);
    expect(tabsFor("staff", FEATURES.finance)).toEqual(["penalty", "cashflow"]);
    expect(tabsFor("staff", FEATURES.sales)).toEqual(["terms"]);
    expect(tabsFor("staff", FEATURES.management)).toEqual(["obligations"]);
    expect(tabsFor("staff", null)).toHaveLength(7);          // no department: every page, as before
    expect(tabsFor("reviewer", ["terms"])).toHaveLength(7);  // a department never narrows a reviewer
  });

  it("never offers a person a link into another department, whichever department they are in", () => {
    for (const [dept, feats] of Object.entries(FEATURES)) {
      const links = navFor("staff", true, feats);
      expect(links.users || links.review || links.buyers || links.mine, `${dept}`).toBe(false);
    }
  });
});

