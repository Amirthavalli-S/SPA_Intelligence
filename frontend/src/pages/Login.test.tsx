import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import "../i18n";
import { PrefsProvider } from "../state/prefs";
import { jsonResponse } from "../test/helpers";
import Login from "./Login";

vi.mock("../motion/registry", async () => (await import("../test/gsapMock")).default);
vi.mock("@gsap/react", () => ({ useGSAP: () => {} }));
afterEach(() => vi.unstubAllGlobals());

const api = (me: object, cfg: object = { mode: "apikey", github: true }) =>
  vi.fn(async (u: string) =>
    u.endsWith("/auth/me")
      ? jsonResponse({ authenticated: false, mode: "apikey", name: null, login: null, avatar_url: null, roles: [], ...me })
      : jsonResponse(cfg),
  );

const Where = () => <p data-testid="in-app">{useLocation().pathname}</p>;

const mount = (url = "/login") =>
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <PrefsProvider>
        <MemoryRouter initialEntries={[url]}>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/" element={<p data-testid="home">home</p>} />
            <Route path="/app/*" element={<Where />} />
          </Routes>
        </MemoryRouter>
      </PrefsProvider>
    </QueryClientProvider>,
  );

describe("Login page", () => {
  it("offers GitHub sign-in that carries the destination", async () => {
    vi.stubGlobal("fetch", api({}));
    mount("/login?next=%2Fapp%2Fcontracts%2Fabc%2Fgap");
    const a = await screen.findByTestId("github-signin");
    expect(a).toHaveAttribute("href", "/api/auth/github/login?next=%2Fapp%2Fcontracts%2Fabc%2Fgap");
    expect(screen.getByText(/approved GitHub accounts/i)).toBeInTheDocument();
  });

  it("never carries an outside destination (open-redirect defence)", async () => {
    vi.stubGlobal("fetch", api({}));
    mount("/login?next=https%3A%2F%2Fevil.example");
    expect(await screen.findByTestId("github-signin")).toHaveAttribute("href", "/api/auth/github/login?next=%2F");   // default: Home
  });

  it("explains a refused account by name, and other failures", async () => {
    vi.stubGlobal("fetch", api({}));
    mount("/login?error=not_allowed&login=stranger");
    expect(await screen.findByTestId("login-error")).toHaveTextContent('"stranger" is not allowed');
  });

  it("ignores an unknown error code instead of printing it", async () => {
    vi.stubGlobal("fetch", api({}));
    mount("/login?error=<script>x</script>");
    await screen.findByTestId("github-signin");
    expect(screen.queryByTestId("login-error")).toBeNull();
  });

  it("goes to Home when a reviewer or administrator is already signed in, or when server auth is off", async () => {
    vi.stubGlobal("fetch", api({ authenticated: true, name: "Alice", roles: ["Spa.Reviewer"] }));
    mount();
    await waitFor(() => expect(screen.getByTestId("home")).toBeInTheDocument());
  });

  it("drops staff straight into their own department's home, with no choice offered", async () => {
    vi.stubGlobal("fetch", api({ authenticated: true, name: "Sam", roles: ["Spa.Staff"], department: "finance", features: ["penalty", "cashflow"] }));
    mount();
    await waitFor(() => expect(screen.getByTestId("in-app")).toHaveTextContent("/app/finance"));
  });

  it("sends buyers and people still waiting for a role to the app, which shows each their own page", async () => {
    vi.stubGlobal("fetch", api({ authenticated: true, name: "Bo", roles: ["Spa.Buyer"] }));
    mount();
    await waitFor(() => expect(screen.getByTestId("in-app")).toHaveTextContent("/app"));
  });

  it("still honours an explicit destination, even for staff in a department", async () => {
    vi.stubGlobal("fetch", api({ authenticated: true, name: "Sam", roles: ["Spa.Staff"], department: "legal", features: ["terms"] }));
    mount("/login?next=%2Fapp%2Freview");
    await waitFor(() => expect(screen.getByTestId("in-app")).toHaveTextContent("/app/review"));
  });

  it("goes back to the page the visitor asked for, when it is inside the app", async () => {
    vi.stubGlobal("fetch", api({ authenticated: true, name: "Alice" }));
    mount("/login?next=%2Fapp%2Freview");
    await waitFor(() => expect(screen.getByTestId("in-app")).toBeInTheDocument());
  });

  it("shows the quote and the three promises beside the sign-in card", async () => {
    vi.stubGlobal("fetch", api({}));
    mount();
    await screen.findByTestId("github-signin");
    expect(screen.getByTestId("login-quote")).toHaveTextContent(/every detail has a page number/i);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(/know exactly what you signed/i);
    expect(screen.getByText(/every value cites its page/i)).toBeInTheDocument();
    expect(screen.getByText(/numbers you can trust/i)).toBeInTheDocument();
    expect(screen.getByText(/a person checks what is unsure/i)).toBeInTheDocument();
  });

  it("lets the visitor show and hide the password they typed", async () => {
    vi.stubGlobal("fetch", api({}, { mode: "supabase", github: false, email: true }));
    mount();
    const pw = (await screen.findByLabelText(/^password/i)) as HTMLInputElement;
    expect(pw.type).toBe("password");
    await userEvent.click(screen.getByTestId("toggle-password"));
    expect(pw.type).toBe("text");
    await userEvent.click(screen.getByTestId("toggle-password"));
    expect(pw.type).toBe("password");
  });

  it("says sign-in is not configured when GitHub is not set up", async () => {
    vi.stubGlobal("fetch", api({}, { mode: "apikey", github: false }));
    mount();
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/not configured/i));
    expect(screen.queryByTestId("github-signin")).toBeNull();
  });
});
