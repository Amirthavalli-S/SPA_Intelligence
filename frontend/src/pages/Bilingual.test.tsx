import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import "../i18n";
import { jsonResponse } from "../test/helpers";
import Bilingual from "./Bilingual";

afterEach(() => vi.unstubAllGlobals());

const result = {
  summary: { match: 1, mismatch: 1, unaligned: 0, total: 2 }, paired_by_number: 2, disclaimer: "Decision support, not legal advice.",
  pairs: [
    { clause_id: "1", english_text: "Price AED 100", arabic_text: "السعر 100", page_en: 1, page_ar: 1, aligned_by: "number", status: "match", differences: [], checked_by: ["figures"] },
    { clause_id: "4", english_text: "Cancel in 30 days", arabic_text: "الإلغاء خلال 15 يوماً", page_en: 1, page_ar: 1, aligned_by: "number", status: "mismatch", differences: ["English states 30; Arabic states 15"], checked_by: ["figures"] },
  ],
};

describe("Bilingual check page", () => {
  it("runs the sample pair and shows the differing clause first-class", async () => {
    const calls: string[] = [];
    vi.stubGlobal("fetch", vi.fn(async (u: string) => {
      const url = String(u);
      calls.push(url);
      if (url.includes("bilingual-check")) return jsonResponse(result);
      if (url.endsWith("/contracts")) return jsonResponse([{ id: "a".repeat(64), name: "spa.pdf", source: "sample", size_bytes: 1, pages: 1, scanned_suspect: false, status: "extracted", warnings_count: 0 }]);
      return jsonResponse({});
    }));
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <MemoryRouter><Bilingual /></MemoryRouter>
      </QueryClientProvider>,
    );
    fireEvent.click(await screen.findByTestId("bi-sample"));
    expect(await screen.findByTestId("bi-summary")).toHaveTextContent("1 differ, 1 agree");
    await waitFor(() => expect(screen.getAllByTestId("bi-mismatch")).toHaveLength(1));
    expect(screen.getByText("English states 30; Arabic states 15")).toBeInTheDocument();
    expect(screen.getByText(/الإلغاء خلال 15/).closest("[dir=rtl]")).not.toBeNull();     // Arabic is rendered right-to-left
    expect(calls.some((c) => c.includes("bilingual-check?sample=pair_1"))).toBe(true);
  });
});
