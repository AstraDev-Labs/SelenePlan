import { describe, it, expect, beforeEach } from "vitest";
import { useAuthStore } from "../../src/auth/store";

describe("In-Memory Auth Store & Security Constraints", () => {
  beforeEach(() => {
    useAuthStore.getState().logout();
    window.localStorage.clear();
  });

  it("stores token strictly in memory and NEVER in localStorage", () => {
    const testToken = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.test-payload";
    useAuthStore.getState().login(testToken, {
      sub: "user-1",
      name: "Test Analyst",
      email: "test@seleneplan.org",
      roles: ["analyst"],
      projects: ["proj-1"],
    });

    const state = useAuthStore.getState();
    expect(state.isAuthenticated).toBe(true);
    expect(state.accessToken).toBe(testToken);

    // CRITICAL SECURITY ASSERTION: localStorage MUST NOT contain tokens
    expect(window.localStorage.getItem("token")).toBeNull();
    expect(window.localStorage.getItem("accessToken")).toBeNull();
    expect(window.localStorage.getItem("refresh_token")).toBeNull();
    expect(window.localStorage.length).toBe(0);
  });

  it("evaluates role permissions correctly with admin override", () => {
    useAuthStore.getState().login("token-analyst", {
      sub: "analyst-1",
      name: "Analyst",
      email: "a@selene.org",
      roles: ["analyst"],
      projects: ["proj-1"],
    });

    expect(useAuthStore.getState().hasRole("analyst")).toBe(true);
    expect(useAuthStore.getState().hasRole("steward")).toBe(false);
    expect(useAuthStore.getState().hasRole("approver")).toBe(false);

    // Admin has access to all roles
    useAuthStore.getState().login("token-admin", {
      sub: "admin-1",
      name: "Admin",
      email: "adm@selene.org",
      roles: ["admin"],
      projects: ["proj-1"],
    });

    expect(useAuthStore.getState().hasRole("steward")).toBe(true);
    expect(useAuthStore.getState().hasRole("approver")).toBe(true);
    expect(useAuthStore.getState().hasRole("auditor")).toBe(true);
  });
});
