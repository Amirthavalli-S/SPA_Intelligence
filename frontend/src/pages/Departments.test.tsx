import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import "../i18n";
import { TopBar } from "../components/TopBar";
import { ContractSummary } from "../components/ContractSummary";
import { PrefsProvider } from "../state/prefs";
import { detail, jsonResponse, renderApp, sourced } from "../test/helpers";
import DepartmentHome from "./DepartmentHome";
import Terms from "./Terms";

vi.mock("../motion/registry", async () => (await import("../test/gsapMock")).default);
vi.mock("@gsap/react", () => ({ useGSAP: () => {} }));
afterEach(() => vi.unstubAllGlobals());
beforeEach(() => {
  localStorage.clear();
  Object.defineProperty(window, "matchMedia", { writable: true, value: (q: string) => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {}, onchange: null, dispatchEvent: () => false }) });
});

const FEATURES = { legal: ["terms", "gap", "playbook", "crosscheck", "obligations", "agreements", "bilingual"], finance: ["penalty", "cashflow"], sales: ["terms"], management: ["accuracy", "obligations"] } as const;
const me = (dept: keyof typeof FEATURES | null, roles = ["Spa.Staff"]) =>
  vi.fn(async () => jsonResponse({ authenticated: true, mode: "supabase", name: "Sam", login: "sam@x.co", avatar_url: null, roles, department: dept, features: dept ? FEATURES[dept] : null, redacted: dept === "sales" }));
const qc = () => new QueryClient({ defaultOptions: { queries: { retry: false } } });
const Where = () => <p data-testid="where">{useLocation().pathname}</p>;

describe("department home", () => {
  const home = (path: string) =>
    render(
      <QueryClientProvider client={qc()}>
        <PrefsProvider>
          <MemoryRouter initialEntries={[path]}>
            <Routes>
              <Route path="/app/finance" element={<DepartmentHome dept="finance" />} />
              <Route path="/app/legal" element={<DepartmentHome dept="legal" />} />
              <Route path="/app" element={<Where />} />
            </Routes>
          </MemoryRouter>
        </PrefsProvider>
      </QueryClientProvider>,
    );

  it("shows the department only the tools it has", async () => {
    vi.stubGlobal("fetch", me("finance"));
    home("/app/finance");
    const tools = await screen.findByTestId("dept-tools");
    expect(Array.from(tools.children).map((li) => li.getAttribute("data-testid"))).toEqual(["tool-penalty", "tool-cashflow"]);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Finance workspace");
  });

  it("sends a person who opens another department's address to where they belong, never showing that page", async () => {
    vi.stubGlobal("fetch", me("finance"));
    home("/app/legal");
    await waitFor(() => expect(screen.queryByTestId("dept-home-legal")).toBeNull());
    expect(screen.queryByText("Legal workspace")).toBeNull();
  });

  it("does not let reviewers or staff without a department browse a department's home", async () => {
    vi.stubGlobal("fetch", me(null, ["Spa.Reviewer"]));
    home("/app/legal");
    expect(await screen.findByTestId("where")).toHaveTextContent("/app");
  });
});

describe("no department picker, ever", () => {
  const bar = () =>
    render(
      <QueryClientProvider client={qc()}>
        <PrefsProvider>
          <MemoryRouter initialEntries={["/app/legal"]}>
            <TopBar />
          </MemoryRouter>
        </PrefsProvider>
      </QueryClientProvider>,
    );

  for (const dept of Object.keys(FEATURES) as (keyof typeof FEATURES)[]) {
    it(`${dept}: the header links only to that department's own pages and never names another department`, async () => {
      vi.stubGlobal("fetch", me(dept));
      bar();
      const nav = await screen.findByRole("navigation", { name: /main/i });
      await waitFor(() => expect(within(nav).getAllByRole("link").length).toBeGreaterThan(0));
      const links = within(nav).getAllByRole("link");
      expect(links[0]).toHaveAttribute("href", `/app/${dept}`);        // the first link IS the department's own home
      const hrefs = links.map((l) => l.getAttribute("href"));
      for (const other of Object.keys(FEATURES).filter((d) => d !== dept)) expect(hrefs, `${dept} -> ${other}`).not.toContain(`/app/${other}`);
      expect(hrefs).not.toContain("/");                                // no general Home page for department staff
      expect(hrefs).not.toContain("/app/review");
      expect(hrefs).not.toContain("/app/buyers");
      expect(hrefs).not.toContain("/app/users");
      expect(screen.queryByRole("combobox")).toBeNull();               // and no dropdown or switcher of any kind
    });
  }

  it("finance cannot even see that Cross-check, Agreements or Accuracy exist", async () => {
    vi.stubGlobal("fetch", me("finance"));
    bar();
    const nav = await screen.findByRole("navigation", { name: /main/i });
    await waitFor(() => expect(within(nav).getByText("Finance")).toBeInTheDocument());
    for (const name of ["Cross-check", "Agreements", "Accuracy", "Obligations", "Review queue", "Buyers", "Users"]) expect(within(nav).queryByText(name)).toBeNull();
  });
});

describe("what Sales sees where values are withheld", () => {
  const restricted = ["price", "delay_rate", "delay_basis", "delay_cap", "plan_amounts"];

  it("shows 'Restricted' (not 'Not stated') on the summary and the terms table, and no trust badge for withheld values", () => {
    const d = detail({ price: sourced(null, null, null) as never, delay_rate: sourced(null, null, null) as never, delay_cap: sourced(null, null, null) as never, delay_basis: sourced(null, null, null) as never });
    d.restricted_fields = restricted;
    d.plan = [{ milestone: "Booking", percent: 20, amount: null, due_date: "2025-03-15", trigger: "On signing", type: "time_based", at_risk: false, source_page: 1, source_quote: "-" }];
    renderApp(<Terms />, d);
    expect(screen.getByTestId("value-price")).toHaveTextContent("Restricted");
    expect(screen.getByTestId("row-price")).not.toHaveTextContent("Not stated");
    expect(within(screen.getByTestId("row-price")).queryByTestId("grounding-chip")).toBeNull();
    expect(screen.getByTestId("value-buyer")).toHaveTextContent("Layla");                            // the rest is shown normally
    expect(within(screen.getByTestId("plan-row")).getByText("Restricted")).toBeInTheDocument();       // amount withheld, the due date is not
    expect(screen.getByTestId("plan-row")).toHaveTextContent("15 Mar 2025");
  });

  it("the at-a-glance card for the price says Restricted too", () => {
    renderApp(<ContractSummary c={detail({ price: sourced(null, null, null) as never }).contract} restricted={restricted} />);
    expect(screen.getByTestId("kpi-price")).toHaveTextContent("Restricted");
  });
});
