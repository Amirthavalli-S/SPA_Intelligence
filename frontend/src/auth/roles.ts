import type { Me } from "./useAuth";

/** What kind of person is signed in. "off" means the server does not enforce sign-in (local development). */
export type Kind = "off" | "anon" | "pending" | "buyer" | "staff" | "reviewer" | "admin";

/** Teams. Only an administrator puts a STAFF account in one; nobody chooses their own, and there is no picker anywhere. */
export const DEPARTMENTS = ["legal", "finance", "sales", "management"] as const;
export type Department = (typeof DEPARTMENTS)[number];
export const isDepartment = (d: unknown): d is Department => typeof d === "string" && (DEPARTMENTS as readonly string[]).includes(d);

/** The pages of a contract, in order. A department sees only the ones its features include. */
export const ALL_TABS = ["terms", "gap", "penalty", "cashflow", "obligations", "playbook", "assistant"] as const;
export type Tab = (typeof ALL_TABS)[number];

export function kindOf(me?: Me): Kind {
  if (!me) return "anon";
  if (me.mode === "off") return "off";
  if (!me.authenticated) return "anon";
  const r = me.roles;
  if (r.includes("Spa.Admin")) return "admin";
  if (r.includes("Spa.Reviewer")) return "reviewer";
  if (r.includes("Spa.Staff")) return "staff";
  if (r.includes("Spa.Buyer")) return "buyer";
  return "pending";
}

export interface Nav {
  app: boolean;
  watch: boolean;
  crosscheck: boolean;
  review: boolean;
  buyers: boolean;
  accuracy: boolean;
  agreements: boolean;
  bilingual: boolean;
  users: boolean;
  mine: boolean;
}

/**
 * Which main-navigation links to show. The server enforces access; this only avoids showing links that would be refused.
 * `features` is what the server says this account's DEPARTMENT may use (null = no department). A department sees its own links and
 * nothing else, so a person in Legal has no way to find out a Finance section exists.
 */
export function navFor(kind: Kind, loaded: boolean, features?: string[] | null): Nav {
  const everything: Nav = { app: true, watch: true, crosscheck: true, review: true, buyers: true, accuracy: true, agreements: true, bilingual: true, users: false, mine: false };
  const nothing: Nav = { app: false, watch: false, crosscheck: false, review: false, buyers: false, accuracy: false, agreements: false, bilingual: false, users: false, mine: false };
  if (!loaded || kind === "off") return everything;
  if (kind === "buyer") return { ...nothing, mine: true };
  if (kind === "staff" && features) {
    const has = (f: string) => features.includes(f);
    return {
      ...nothing,
      app: ALL_TABS.some((t) => t !== "obligations" && has(t)),          // a contract workspace needs at least one contract page
      watch: has("obligations"),
      crosscheck: has("crosscheck"),
      accuracy: has("accuracy"),
      agreements: has("agreements"),
      bilingual: has("bilingual"),
    };
  }
  if (kind === "staff") return { ...everything, review: false, buyers: false };
  if (kind === "reviewer") return everything;
  if (kind === "admin") return { ...everything, users: true };
  return nothing;
}

/** The contract pages this account may open, in order. */
export function tabsFor(kind: Kind, features?: string[] | null): Tab[] {
  return kind === "staff" && features ? ALL_TABS.filter((t) => features.includes(t)) : [...ALL_TABS];
}

/**
 * Where a person lands right after signing in, with no choice to make. Staff go straight to their department's home;
 * buyers and people waiting for a role go to the app (which shows them their own world); reviewers and administrators, who work
 * across teams, land on Home.
 */
export function homeRouteFor(kind: Kind, department?: string | null): string {
  if (kind === "staff" && isDepartment(department)) return `/app/${department}`;
  if (kind === "buyer" || kind === "pending") return "/app";
  return "/";
}
