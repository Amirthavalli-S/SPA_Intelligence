import { describe, expect, it } from "vitest";
import { safeNext } from "./useAuth";

describe("safeNext (where sign-in lands)", () => {
  it("defaults to Home and accepts Home and paths inside the app", () => {
    expect(safeNext(null)).toBe("/");
    expect(safeNext("/")).toBe("/");
    expect(safeNext("/app")).toBe("/app");
    expect(safeNext("/app/contracts/abc/gap")).toBe("/app/contracts/abc/gap");
  });
  it("refuses anything that could leave the site", () => {
    for (const bad of ["https://evil.example", "//evil.example", "/other", "/app/../x", "/app//x", "javascript:1", ""]) {
      expect(safeNext(bad), bad).toBe("/");
    }
  });
});
