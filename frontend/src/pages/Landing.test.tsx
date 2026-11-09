import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import "../i18n";
import { PrefsProvider } from "../state/prefs";
import Landing from "./Landing";

vi.mock("../motion/registry", async () => (await import("../test/gsapMock")).default);
vi.mock("@gsap/react", () => ({ useGSAP: () => {} }));

const open = () =>
  render(
    <QueryClientProvider client={new QueryClient()}>
      <PrefsProvider>
        <MemoryRouter>
          <Landing />
        </MemoryRouter>
      </PrefsProvider>
    </QueryClientProvider>,
  );

describe("Landing gallery", () => {
  it("lists what the app does today, and only what is genuinely still to come", () => {
    open();
    const cards = screen.getAllByTestId("roadmap-card");
    expect(cards).toHaveLength(10);
    expect(screen.getAllByTestId("gallery-available")).toHaveLength(9);
    expect(screen.getAllByTestId("gallery-coming")).toHaveLength(1);
    // built features appear as available
    for (const t of ["Scanned contracts", "Cross-document check", "Statute and playbook check", "Human review queue", "Obligations and deadlines", "Accuracy dashboard", "Roles and buyer access", "Arabic vs English check", "Buyer chat"])
      expect(screen.getByText(t, { exact: false })).toBeInTheDocument();
    // only the unbuilt ones are still "coming next"
    const coming = cards.filter((c) => c.querySelector("[data-testid=gallery-coming]")).map((c) => c.textContent);
    expect(coming.join(" ")).not.toMatch(/Arabic/);
    expect(coming.join(" ")).not.toMatch(/WhatsApp/);
    expect(coming.join(" ")).toMatch(/Real evaluation set/);
    // the old "coming next" cards for things that now exist are gone
    expect(screen.queryByText("Document Intelligence parsing")).toBeNull();
    expect(screen.queryByText("Rulebook check")).toBeNull();
    expect(screen.queryByText(/ERP/)).toBeNull();                       // the ERP feature was removed from the app
  });

  it("keeps the cinematic front page and only adds a way into the business page", () => {
    open();
    expect(screen.getByTestId("for-teams")).toHaveTextContent("For teams");
    expect(screen.getAllByTestId("roadmap-card").length).toBeGreaterThan(0);          // the gallery and the rest of the story are untouched
  });
});
