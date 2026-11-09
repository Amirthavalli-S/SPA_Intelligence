import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import "../i18n";
import { PrefsProvider } from "../state/prefs";
import { jsonResponse } from "../test/helpers";
import Enterprise from "./Enterprise";

vi.mock("../motion/registry", async () => (await import("../test/gsapMock")).default);
vi.mock("@gsap/react", () => ({ useGSAP: () => {} }));
afterEach(() => vi.unstubAllGlobals());

const evalResults = (acc: number, checks = 48) => ({
  generated_at: "2026-11-06T09:28:55+00:00", model: "m", files: ["a", "b", "c"], fields: {}, per_file: {}, penalty_tests: {},
  overall: { value_accuracy: acc, checks, quote_accuracy: 1, quotes_checked: 32 },
});
const contract = (name: string, warnings: number) => ({ id: name.padEnd(64, "0"), name, source: "sample", size_bytes: 1, pages: 1, scanned_suspect: false, status: "extracted", warnings_count: warnings });

interface Server { eval?: object | null; contracts?: object[] | null; agreements?: object[] | null; db?: object }
const serve = (s: Server) =>
  vi.stubGlobal("fetch", vi.fn(async (u: string) => {
    const url = String(u);
    const missing = jsonResponse({ error: { code: "not_found", message: "no" } }, 404);
    if (url.endsWith("/eval/results")) return s.eval ? jsonResponse(s.eval) : missing;
    if (url.endsWith("/agreements")) return s.agreements ? jsonResponse(s.agreements) : jsonResponse({ error: { code: "forbidden", message: "no" } }, 403);
    if (url.endsWith("/contracts")) return s.contracts ? jsonResponse(s.contracts) : jsonResponse({ error: { code: "forbidden", message: "no" } }, 403);
    if (url.endsWith("/health")) return jsonResponse({ status: "ok", llm_configured: true, model: "m", llm_calls_made: 0, llm_call_cap: 40, auth_mode: "off", database: s.db ?? { enabled: false }, ocr: { enabled: false } });
    return jsonResponse({});
  }));
const open = () =>
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <PrefsProvider>
        <MemoryRouter>
          <Enterprise />
        </MemoryRouter>
      </PrefsProvider>
    </QueryClientProvider>,
  );
const tile = (id: string) => screen.findByTestId(id);

describe("Enterprise page: every number is read from the server", () => {
  const full = { eval: evalResults(0.9792), contracts: [contract("a", 0), contract("b", 2), contract("c", 5)], agreements: [{ agreement_id: "AGR-1" }, { agreement_id: "AGR-2" }], db: { enabled: true, ok: true, rls_on: true, tables: ["t1", "t2", "t3", "t4", "t5", "t6"] } };

  const has = (id: string, text: string | RegExp) => vi.waitFor(() => expect(screen.getByTestId(id)).toHaveTextContent(text));

  it("shows accuracy, quotes, agreements, row-level security and the portfolio's own warnings", async () => {
    serve(full);
    open();
    await has("stat-accuracy", "97.9%");
    await has("stat-accuracy", /48 value checks on 3 labelled sample contracts/);
    await has("stat-quotes", "100%");
    await has("stat-agreements", "2");
    await has("stat-rls", "On");
    await has("stat-rls", "6 tables");
    await has("stat-contracts", "3");
    await has("stat-flagged", "2 / 3");        // two of three contracts carry a warning
    await has("stat-warnings", "7");
  });

  it("changes when the server's numbers change, so none of them is typed into the page", async () => {
    serve({ ...full, eval: evalResults(0.5, 10), agreements: [{ agreement_id: "AGR-1" }], db: { enabled: true, ok: true, rls_on: false, tables: ["t1"] } });
    open();
    await has("stat-accuracy", "50.0%");
    await has("stat-accuracy", "10 value checks");
    await has("stat-rls", "Off");
    await has("stat-agreements", "1");
  });

  it("says so, instead of inventing a figure, when nothing can be read", async () => {
    serve({ eval: null, contracts: null, agreements: null, db: { enabled: false } });
    open();
    for (const id of ["stat-accuracy", "stat-quotes", "stat-agreements", "stat-rls", "stat-contracts", "stat-flagged", "stat-warnings"]) {
      const t = await tile(id);
      await vi.waitFor(() => expect(t).toHaveTextContent("Not available yet, or not for your account"));
      expect(within(t).getByText("–")).toBeInTheDocument();
    }
  });
});

describe("Enterprise page: content", () => {
  it("names the five teams, shows eight capabilities with three proof points each, and the controls built in", async () => {
    serve({});
    open();
    const teams = await screen.findByTestId("teams");
    expect(Array.from(teams.children).map((c) => c.getAttribute("data-testid"))).toEqual(["team-legal", "team-finance", "team-sales", "team-management", "team-buyers"]);
    const caps = screen.getByTestId("capabilities");
    expect(caps.children).toHaveLength(8);
    for (const c of Array.from(caps.children)) expect(c.querySelectorAll(".badge")).toHaveLength(3);
    expect(within(screen.getByTestId("controls")).getByText("Row-level security")).toBeInTheDocument();
  });

  it("does not claim compliance it cannot back: the rule packs are marked unreviewed and it is decision support", async () => {
    serve({});
    open();
    await screen.findByTestId("controls");
    const text = document.body.textContent ?? "";
    expect(text).not.toMatch(/compliant/i);
    expect(text).toMatch(/unreviewed until your lawyer signs them off/);
    expect(text).toMatch(/not legal advice/);
  });
});
