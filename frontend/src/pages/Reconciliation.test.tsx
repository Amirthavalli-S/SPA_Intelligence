import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import "../i18n";
import { AgreementBox } from "../components/AgreementBox";
import { PrefsProvider } from "../state/prefs";
import { jsonResponse } from "../test/helpers";
import Reconciliation from "./Reconciliation";

vi.mock("../motion/registry", async () => (await import("../test/gsapMock")).default);
vi.mock("@gsap/react", () => ({ useGSAP: () => {} }));
afterEach(() => vi.unstubAllGlobals());

const result = (over = {}) => ({
  agreement_id: "AGR-1105", currency: "INR", pending_review: 0, problems: [], missing: ["penalty_cap"],
  documents: [
    { doc_id: "a".repeat(64), name: "AGR-1105 SPA", doc_type: "SPA", date_signed: "2025-01-14", open_reviews: 0 },
    { doc_id: "b".repeat(64), name: "Addendum 1", doc_type: "Addendum", date_signed: "2026-03-10", open_reviews: 2 },
  ],
  current: { price: 9500000, possession_date: "2029-06-30", payment_schedule: [{}, {}], payment_plan_version: 1,
             penalty_rate: { rate: 10, basis: "fixed_per_sqft_per_month" }, grace_period_days: 0 },
  sources: { price: { doc_id: "b", name: "Addendum 1", doc_type: "Addendum", date_signed: "2026-03-10" },
             possession_date: { doc_id: "c", name: "Extension Letter", doc_type: "Extension Letter", date_signed: "2026-07-18" } },
  timeline: [
    { date: "2025-01-14", doc_type: "SPA", doc_id: "a", name: "AGR-1105 SPA", changes: [{ field: "price", kind: "set", from: null, to: 10000000 }] },
    { date: "2026-03-10", doc_type: "Addendum", doc_id: "b", name: "Addendum 1", changes: [{ field: "price", kind: "changed", from: 10000000, to: 9500000 }] },
    { date: "2026-07-18", doc_type: "Extension Letter", doc_id: "c", name: "Extension Letter", changes: [] },
  ],
  ...over,
});

const mount = (path: string, fetchImpl: (u: string) => Response | Promise<Response>) => {
  vi.stubGlobal("fetch", vi.fn(async (u: string) => fetchImpl(String(u))));
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <PrefsProvider>
        <MemoryRouter initialEntries={[path]}>
          <Routes>
            <Route path="/app/agreements" element={<Reconciliation />} />
            <Route path="/app/agreements/:id" element={<Reconciliation />} />
          </Routes>
        </MemoryRouter>
      </PrefsProvider>
    </QueryClientProvider>,
  );
};
const api = (r: object | null) => (u: string) =>
  u.endsWith("/agreements") ? jsonResponse([{ agreement_id: "AGR-1105", documents: 3, latest_signed: "2026-07-18" }])
  : r ? jsonResponse(r) : jsonResponse({ error: { code: "not_found", message: "No document belongs to this agreement." } }, 404);

describe("Agreements page", () => {
  it("shows the current terms with the document each one came from, in the contract's own currency", async () => {
    mount("/app/agreements/AGR-1105", api(result()));
    const cur = await screen.findByTestId("agreement-current");
    expect(within(cur).getByTestId("ag-price")).toHaveTextContent(/INR\s*9,500,000/);
    expect(within(cur).getByTestId("ag-price")).toHaveTextContent(/Set by Addendum 1, signed .*2026/);
    expect(within(cur).getByTestId("ag-possession_date")).toHaveTextContent(/30 Jun 2029/);
    expect(within(cur).getByTestId("ag-possession_date")).toHaveTextContent(/Extension Letter/);
    expect(within(cur).getByTestId("ag-penalty_rate")).toHaveTextContent(/INR\s*10\.00 per sq ft per month/);
    expect(within(cur).getByTestId("ag-penalty_cap")).toHaveTextContent(/Not stated in any document/);
    expect(screen.getByText("Payment plan version 1")).toBeInTheDocument();
  });

  it("lists what each document changed, oldest first, and says when a document changed nothing", async () => {
    mount("/app/agreements/AGR-1105", api(result()));
    const tl = await screen.findByTestId("agreement-timeline");
    const nodes = within(tl).getAllByRole("listitem").filter((li) => li.classList.contains("ag-node"));
    expect(nodes.map((n) => n.textContent)).toEqual([expect.stringContaining("AGR-1105 SPA"), expect.stringContaining("Addendum 1"), expect.stringContaining("Extension Letter")]);
    expect(nodes[1]).toHaveTextContent(/Price:.*10,000,000.*→.*9,500,000/);
    expect(nodes[2]).toHaveTextContent("Nothing changed by this document.");
  });

  it("warns when values still need a person's review and reports documents that could not be merged", async () => {
    mount("/app/agreements/AGR-1105", api(result({ pending_review: 2, problems: ["Undated: no signing date, so its place in the order is unknown and it is not merged."] })));
    expect(await screen.findByTestId("agreement-pending")).toHaveTextContent("2 values in these documents still need a person's review");
    expect(screen.getByText(/no signing date/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "AGR-1105 SPA" })).toHaveAttribute("href", `/app/contracts/${"a".repeat(64)}/terms`);
  });

  it("says plainly when no document belongs to the agreement, and lists the known agreements to pick from", async () => {
    mount("/app/agreements/NOPE", api(null));
    expect(await screen.findByText("No document belongs to this agreement")).toBeInTheDocument();
    expect(await screen.findByTestId("agreement-list")).toHaveTextContent("AGR-1105 · 3 documents");
  });

  it("opens an agreement from the search box", async () => {
    mount("/app/agreements", api(result()));
    await userEvent.type(await screen.findByLabelText(/Agreement ID/), "AGR-1105");
    await userEvent.click(screen.getByRole("button", { name: "Show" }));
    expect(await screen.findByTestId("agreement-current")).toBeInTheDocument();
  });
});

describe("AgreementBox", () => {
  it("saves the agreement, type and date, and shows the server's refusal when the person may not change it", async () => {
    const f = vi.fn(async (_u: string, init?: RequestInit) => init?.method === "PUT"
      ? jsonResponse({ error: { code: "forbidden", message: "This action needs the Reviewer role." } }, 403) : jsonResponse({}));
    vi.stubGlobal("fetch", f);
    render(
      <QueryClientProvider client={new QueryClient()}>
        <PrefsProvider>
          <MemoryRouter>
            <AgreementBox contractId={"a".repeat(64)} />
          </MemoryRouter>
        </PrefsProvider>
      </QueryClientProvider>,
    );
    await userEvent.click(screen.getByText("Agreement"));
    await userEvent.type(screen.getByLabelText("Agreement ID"), "AGR-9");
    await userEvent.selectOptions(screen.getByLabelText("Document type"), "Addendum");
    await userEvent.type(screen.getByLabelText("Date signed"), "2026-03-10");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    const put = f.mock.calls.find((c) => c[1]?.method === "PUT")!;
    expect(String(put[0])).toMatch(/\/contracts\/a{64}\/agreement$/);
    expect(JSON.parse(String(put[1]?.body))).toEqual({ agreement_id: "AGR-9", doc_type: "Addendum", date_signed: "2026-03-10" });
    expect(await screen.findByText(/needs the Reviewer role/)).toBeInTheDocument();
  });
});
