import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { detail, renderApp, sourced } from "../test/helpers";
import { ContractSummary } from "./ContractSummary";
import { GroundingChip } from "./GroundingChip";
import { countOpenReviews } from "./termDisplay";
import { WarningsPanel } from "./WarningsPanel";

vi.mock("../motion/registry", async () => (await import("../test/gsapMock")).default);
vi.mock("@gsap/react", () => ({ useGSAP: () => {} }));

describe("WarningsPanel", () => {
  it("says everything is fine when there are no warnings", () => {
    renderApp(<WarningsPanel warnings={[]} />);
    expect(screen.getByText(/No warnings/i)).toBeInTheDocument();
    expect(screen.queryByTestId("warnings-panel")).toBeNull();
  });

  it("puts what needs a person first and the plain 'not stated' messages under 'for your information'", () => {
    renderApp(
      <WarningsPanel
        warnings={[
          "Payment plan percentages sum to 99%, not 100%.",
          "'delay_rate' is not stated in the contract.",
          "No cancellation clause found in the contract.",
          "Grounding: 'price' needs review (confidence 0.88).",
        ]}
      />,
    );
    expect(screen.getByText("2 to check")).toBeInTheDocument();
    expect(screen.getByText("2 for information")).toBeInTheDocument();
    const alerts = screen.getAllByRole("alert").map((e) => e.textContent);
    expect(alerts).toHaveLength(2);                                     // only the two that need a person are alerts
    expect(alerts.join(" ")).toMatch(/sum to 99%/);
    expect(alerts.join(" ")).toMatch(/needs review/);
    expect(screen.getAllByRole("status")).toHaveLength(2);              // the notes are polite status messages
    expect(screen.getByText(/'delay_rate' is not stated/)).toBeInTheDocument();   // nothing is hidden
  });
});

describe("GroundingChip wording", () => {
  const word = (item: object) => {
    renderApp(<GroundingChip item={item} />);
    return screen.getByTestId("grounding-chip").textContent;
  };
  it("uses plain words instead of 'grounded'", () => {
    expect(word({ grounding: { status: "grounded" }, confidence: 1 })).toMatch(/Verified in the PDF.*100%/);
  });
  it("says partly matched, not confirmed, checked by a person and not stated", () => {
    expect(word({ grounding: { status: "partial" }, confidence: 0.88 })).toMatch(/Partly matched.*88%/);
  });
  it("says not confirmed", () => {
    expect(word({ grounding: { status: "ungrounded" }, confidence: 0 })).toMatch(/Not confirmed/);
  });
  it("says checked by a person, which wins over the grounding result", () => {
    expect(word({ human_verified: true, grounding: { status: "ungrounded" } })).toMatch(/Checked by a person/);
  });
  it("says not stated when there is nothing to check", () => {
    expect(word({ grounding: null })).toMatch(/Not stated/);
  });
});

describe("countOpenReviews", () => {
  it("counts flagged values that no person has reviewed yet, across fields, rows and clauses", () => {
    const c = detail().contract;
    expect(countOpenReviews(c)).toBe(0);
    const flagged = { ...c, price: { ...c.price, needs_review: true }, buyer: { ...c.buyer, needs_review: true, human_verified: true } };
    expect(countOpenReviews(flagged)).toBe(1);                          // the reviewed buyer does not count
    const withRows = { ...flagged, payment_plan: [{ needs_review: true }], ungrounded_rows: [{ needs_review: true }], dated_clauses: [{ needs_review: true }] };
    expect(countOpenReviews(withRows as never)).toBe(4);
  });
});

describe("ContractSummary", () => {
  it("shows who, what, how much, when, the plan total and that nothing is waiting for review", () => {
    renderApp(<ContractSummary c={detail().contract} />);
    expect(screen.getByTestId("kpi-buyer")).toHaveTextContent("Layla");
    expect(screen.getByTestId("kpi-price")).toHaveTextContent(/2,450,000/);
    expect(screen.getByTestId("kpi-plan")).toHaveTextContent("100%");
    expect(screen.getByTestId("summary-review")).toHaveTextContent(/Everything has been checked/);
    expect(screen.queryByRole("link", { name: /review queue/i })).toBeNull();
  });

  it("links to the review queue when values wait for a person", () => {
    const c = detail().contract;
    renderApp(<ContractSummary c={{ ...c, price: { ...c.price, needs_review: true } }} />);
    expect(screen.getByTestId("summary-review")).toHaveTextContent(/1 value needs a person to review it/);
    expect(screen.getByRole("link", { name: /open the review queue/i })).toHaveAttribute("href", "/app/review");
  });

  it("when the contract mentions a value that could not be confirmed, quotes what it says instead of a bare 'Not stated'", () => {
    const c = detail().contract;
    renderApp(<ContractSummary c={{ ...c, handover_date: sourced(null, 2, "Anticipated Completion Date: June-2025") as never }} />);
    const k = screen.getByTestId("kpi-handover_date");
    expect(k).toHaveTextContent(/Not stated/);
    expect(k).toHaveTextContent(/The contract says: “Anticipated Completion Date: June-2025”/);
  });

  it("flags a payment plan that does not add up to 100%", () => {
    renderApp(<ContractSummary c={{ ...detail().contract, payment_plan_percent_sum: 104 }} />);
    expect(screen.getByTestId("kpi-plan")).toHaveTextContent(/104%.*does not add up to 100%/);
  });
});
