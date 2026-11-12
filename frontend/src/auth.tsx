import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { api, ApiError } from "./api";
import type { User } from "./types";

const STORAGE_KEY = "game-insight-user";

interface AuthState {
  user: User | null;
  signIn: (user: User) => void;
  signOut: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

function stored(): User | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as User) : null;
  } catch {
    return null;
  }
}

/**
 * Demo-grade sign-in, matching the backend: after login the API is told who the user
 * is through the X-User-Id header. There are no tokens.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(stored);
  const signIn = useCallback((next: User) => {
    setUser(next);
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    } catch {
      /* storage unavailable: stay signed in for this tab only */
    }
  }, []);
  const signOut = useCallback(() => {
    setUser(null);
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {
      /* ignore */
    }
  }, []);
  // A remembered user can outlive the database (e.g. after `docker compose down -v`).
  useEffect(() => {
    if (!user) return;
    api.favorites(user.id).catch((error) => {
      if (error instanceof ApiError && error.status === 404) signOut();
    });
  }, [user, signOut]);
  const value = useMemo(() => ({ user, signIn, signOut }), [user, signIn, signOut]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
