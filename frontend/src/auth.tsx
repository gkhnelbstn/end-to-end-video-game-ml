import { UserManager, WebStorageStateStore, type User as OidcUser } from "oidc-client-ts";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { setAccessToken } from "./api";

/**
 * Sign-in goes through Rauthy, the OpenID Connect provider in the compose stack
 * (authorization code + PKCE). nginx serves it under /auth/ on the dashboard's own
 * origin. With `npm run dev`, point VITE_OIDC_AUTHORITY at the compose frontend, e.g.
 * http://localhost:8080/auth/v1/.
 */
const authority = import.meta.env.VITE_OIDC_AUTHORITY ?? `${window.location.origin}/auth/v1/`;
const CLIENT_ID = "game-insight";

/** Where the account pages live: registration, password reset, profile. */
export const accountUrl = new URL("account", authority).toString();
export const registerUrl = `${new URL("users/register", authority)}?redirect_uri=${encodeURIComponent(
  `${window.location.origin}/`,
)}`;

let manager: UserManager | undefined;

export function userManager(): UserManager {
  manager ??= new UserManager({
    authority,
    client_id: CLIENT_ID,
    redirect_uri: `${window.location.origin}/callback`,
    post_logout_redirect_uri: `${window.location.origin}/`,
    scope: "openid email profile",
    // Tokens stay in this tab's session storage, and are renewed with the refresh token.
    userStore: new WebStorageStateStore({ store: window.sessionStorage }),
    automaticSilentRenew: true,
  });
  return manager;
}

export interface Account {
  email?: string;
  name?: string;
}

interface AuthState {
  account: Account | null;
  /** False until the stored session has been read; avoids flashing "Sign in". */
  ready: boolean;
  signIn: (returnTo?: string) => void;
  signOut: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

function toAccount(user: OidcUser | null): Account | null {
  if (!user || user.expired) return null;
  const { email, name, preferred_username } = user.profile;
  return { email, name: name ?? preferred_username };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [account, setAccount] = useState<Account | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const um = userManager();
    const apply = (user: OidcUser | null) => {
      setAccessToken(user && !user.expired ? user.access_token : undefined);
      setAccount(toAccount(user));
    };
    um.getUser()
      .then(apply)
      .catch(() => apply(null))
      .finally(() => setReady(true));
    const clear = () => apply(null);
    um.events.addUserLoaded(apply);
    um.events.addUserUnloaded(clear);
    um.events.addSilentRenewError(clear);
    um.events.addAccessTokenExpired(clear);
    return () => {
      um.events.removeUserLoaded(apply);
      um.events.removeUserUnloaded(clear);
      um.events.removeSilentRenewError(clear);
      um.events.removeAccessTokenExpired(clear);
    };
  }, []);

  const signIn = useCallback((returnTo?: string) => {
    void userManager().signinRedirect({
      state: { returnTo: returnTo ?? window.location.pathname + window.location.search },
    });
  }, []);
  const signOut = useCallback(() => {
    const um = userManager();
    void um.getUser().then((user) =>
      // Ends the Rauthy session too, then comes back to the home page.
      user ? um.signoutRedirect({ id_token_hint: user.id_token }) : um.removeUser(),
    );
  }, []);

  const value = useMemo(() => ({ account, ready, signIn, signOut }), [account, ready, signIn, signOut]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
