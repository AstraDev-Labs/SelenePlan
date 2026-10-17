/**
 * In-Memory Authentication Store
 *
 * Strict Security Rules:
 * 1. Tokens exist ONLY in Javascript memory variables within this module closure.
 * 2. NEVER persist tokens, refresh tokens, or secrets to localStorage or sessionStorage.
 * 3. Role-based access control flags for Analyst, Operator, Approver, Steward, Admin, Auditor.
 */

import { create } from "zustand";

export type UserRole = "analyst" | "operator" | "approver" | "steward" | "admin" | "auditor";

export interface UserProfile {
  sub: string;
  name: string;
  email: string;
  roles: UserRole[];
  projects: string[];
}

interface AuthState {
  // Stored purely in-memory
  accessToken: string | null;
  idToken: string | null;
  user: UserProfile | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  activeProjectId: string;

  // Actions
  login: (token: string, user: UserProfile) => void;
  logout: () => void;
  setActiveProject: (projectId: string) => void;
  hasRole: (role: UserRole) => boolean;
  hasAnyRole: (roles: UserRole[]) => boolean;
}

// In-Memory state: NO localStorage persistence
export const useAuthStore = create<AuthState>((set, get) => ({
  accessToken: null,
  idToken: null,
  user: null,
  isAuthenticated: false,
  isLoading: false,
  activeProjectId: "00000000-0000-0000-0000-000000000001",

  login: (token: string, user: UserProfile) => {
    // Assert strictly that localStorage is NEVER touched with tokens
    if (typeof window !== "undefined" && window.localStorage) {
      window.localStorage.removeItem("token");
      window.localStorage.removeItem("accessToken");
      window.localStorage.removeItem("refresh_token");
    }

    set({
      accessToken: token,
      user,
      isAuthenticated: true,
      isLoading: false,
      activeProjectId: user.projects[0] || get().activeProjectId,
    });
  },

  logout: () => {
    set({
      accessToken: null,
      idToken: null,
      user: null,
      isAuthenticated: false,
      isLoading: false,
    });
  },

  setActiveProject: (projectId: string) => {
    set({ activeProjectId: projectId });
  },

  hasRole: (role: UserRole) => {
    const roles = get().user?.roles || [];
    return roles.includes(role) || roles.includes("admin");
  },

  hasAnyRole: (roles: UserRole[]) => {
    const userRoles = get().user?.roles || [];
    if (userRoles.includes("admin")) return true;
    return roles.some((r) => userRoles.includes(r));
  },
}));
