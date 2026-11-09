import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import "./i18n";
import { PrefsProvider } from "./state/prefs";
import { jsonResponse } from "./test/helpers";

vi.mock("./motion/registry", async () => (await import("./test/gsapMock")).default);
vi.mock("@gsap/react", () => ({ useGSAP: () => {} }));
afterEach(() => vi.unstubAllGlobals());

const server = (me: object) =>
  vi.fn(async (u: string) =>
    u.endsWith("/auth/me")
      ? jsonResponse({ authenticated: false, mode: "supabase", name: null, login: null, avatar_url: null, roles: [], ...me })
      : jsonResponse({ mode: "supabase", github: false, email: true }),
  );

const open = (url: string) =>
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <PrefsProvider>
        <MemoryRouter initialEntries={[url]}>
          <App />
        </MemoryRouter>
      </PrefsProvider>
    </QueryClientProvider>,
  );

describe("App entry", () => {
  it("opens on the login page when sign-in is required, even at the front door", async () => {
    vi.stubGlobal("fetch", server({}));
    open("/");
    expect(await screen.findByTestId("login-page")).toBeInTheDocument();
    expect(screen.getByTestId("login-quote")).toBeInTheDocument();
  });

  it("the login page header has no app navigation to click before signing in", async () => {
    vi.stubGlobal("fetch", server({}));
    open("/login");
    await screen.findByTestId("login-page");
    expect(screen.queryByRole("navigation", { name: /main/i })).toBeNull();
  });
});

describe("Front pages and departments", () => {
  const dept = (department: string | null, roles: string[]) =>
    vi.fn(async (u: string) =>
      u.endsWith("/auth/me")
        ? jsonResponse({ authenticated: true, mode: "supabase", name: "Sam", login: "s@x.co", avatar_url: null, roles, department, features: department ? ["terms"] : null })
        : u.endsWith("/contracts") ? jsonResponse([]) : jsonResponse({ mode: "supabase", github: false, email: true }),
    );

  it("a reviewer can open the enterprise page from the front page", async () => {
    vi.stubGlobal("fetch", dept(null, ["Spa.Reviewer"]));
    open("/enterprise");
    expect(await screen.findByTestId("enterprise")).toBeInTheDocument();
  });

  it("department staff never see the five-teams page (it would reveal the other departments); it sends them home", async () => {
    vi.stubGlobal("fetch", dept("sales", ["Spa.Staff"]));
    open("/enterprise");
    expect(await screen.findByTestId("dept-home-sales")).toBeInTheDocument();
    expect(screen.queryByTestId("enterprise")).toBeNull();
    expect(screen.queryByTestId("teams")).toBeNull();
  });

  it("department staff who open the front page land on their own home instead", async () => {
    vi.stubGlobal("fetch", dept("legal", ["Spa.Staff"]));
    open("/");
    expect(await screen.findByTestId("dept-home-legal")).toBeInTheDocument();
  });
});
