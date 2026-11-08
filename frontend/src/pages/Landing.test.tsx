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
    expect(cards).toHaveLength(11);
    expect(screen.getAllByTestId("gallery-available")).toHaveLength(8);
    expect(screen.getAllByTestId("gallery-coming")).toHaveLength(3);
    // built features appear as available
    for (const t of ["Scanned contracts", "Cross-document check", "Statute and playbook check", "Human review queue", "Obligations and deadlines", "Accuracy dashboard", "ERP export", "Roles and buyer access"])
      expect(screen.getByText(t, { exact: false })).toBeInTheDocument();
    // only the unbuilt ones are still "coming next"
    const coming = cards.filter((c) => c.querySelector("[data-testid=gallery-coming]")).map((c) => c.textContent);
    expect(coming.join(" ")).toMatch(/Arabic–English check/);
    expect(coming.join(" ")).toMatch(/WhatsApp assistant/);
    expect(coming.join(" ")).toMatch(/Real evaluation set/);
    // the old "coming next" cards for things that now exist are gone
    expect(screen.queryByText("Document Intelligence parsing")).toBeNull();
    expect(screen.queryByText("Rulebook check")).toBeNull();
  });
});
