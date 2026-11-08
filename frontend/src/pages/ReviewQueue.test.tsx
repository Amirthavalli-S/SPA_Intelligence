import { screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { jsonResponse, renderApp } from "../test/helpers";
import ReviewQueue from "./ReviewQueue";

vi.mock("../motion/registry", async () => (await import("../test/gsapMock")).default);
vi.mock("@gsap/react", () => ({ useGSAP: () => {} }));
afterEach(() => vi.unstubAllGlobals());

const item = (field: string, over = {}) => ({
  contract_id: "a".repeat(64), contract_name: "sample_a.pdf", field, value: 1250000, claimed_value: null, status: "partial",
  confidence: 0.88, source_page: 1, source_quote: "The Purchase Price is AED 1,250,000", reasons: ["fuzzy match (score 96)"], ...over,
});

describe("Review queue", () => {
  it("names each value in words, never by its raw field path, and groups items under their contract", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse({ count: 2, items: [item("price"), item("payment_plan.4", { value: { name: "4th Installment", percent: 5 } })] })));
    renderApp(<ReviewQueue />);
    expect(await screen.findByText("Purchase price")).toBeInTheDocument();
    expect(screen.getByText("Payment plan, row 4")).toBeInTheDocument();
    expect(screen.queryByText(/payment_plan\.4/)).toBeNull();
    expect(screen.getByText("2 values need review")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: /sample_a\.pdf/ })).toBeInTheDocument();
    expect(screen.getAllByTestId("review-item")).toHaveLength(2);
  });

  it("shows large numbers with separators and explains what accept, correct and reject do", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse({ count: 1, items: [item("price")] })));
    renderApp(<ReviewQueue />);
    expect(await screen.findByText("1,250,000")).toBeInTheDocument();
    expect(screen.getByText(/Accept: the value matches the PDF/)).toBeInTheDocument();
    expect(screen.getByText(/Reject: treat it as not stated/)).toBeInTheDocument();
  });

  it("says plainly when nothing is waiting", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse({ count: 0, items: [] })));
    renderApp(<ReviewQueue />);
    expect(await screen.findByText("Nothing to review")).toBeInTheDocument();
    expect(screen.getByText("0 values need review")).toBeInTheDocument();
  });
});
