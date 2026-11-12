import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { api } from "../api";
import { registerUrl, useAuth, userManager } from "../auth";
import GameCard from "../components/GameCard";
import { ErrorNotice, Notice } from "../components/ui";
import { useAsync } from "../hooks";

/** Rauthy sends the browser back here with a one-time code; trade it for tokens. */
export function Callback() {
  const navigate = useNavigate();
  const [error, setError] = useState<Error>();
  const started = useRef(false);

  useEffect(() => {
    // StrictMode runs effects twice in development; the code can only be redeemed once.
    if (started.current) return;
    started.current = true;
    userManager()
      .signinRedirectCallback()
      .then((user) => {
        const returnTo = (user.state as { returnTo?: string } | undefined)?.returnTo;
        navigate(returnTo && returnTo !== "/callback" ? returnTo : "/", { replace: true });
      })
      .catch(setError);
  }, [navigate]);

  if (!error) return <div className="skeleton" style={{ minHeight: 240 }} aria-label="Signing you in" />;
  return (
    <div className="empty">
      <h1>Sign-in didn't finish</h1>
      <p className="subtle">{error.message}</p>
      <Link to="/login" className="button">
        Try again
      </Link>
    </div>
  );
}

/** A plain address that starts sign-in, for links and bookmarks. */
export function Login() {
  const { account, ready, signIn } = useAuth();
  const navigate = useNavigate();
  useEffect(() => {
    if (!ready) return;
    if (account) navigate("/favorites", { replace: true });
    else signIn("/favorites");
  }, [account, ready, signIn, navigate]);
  return <div className="skeleton" style={{ minHeight: 240 }} aria-label="Opening sign-in" />;
}

function SignInPrompt() {
  const { signIn } = useAuth();
  return (
    <div className="empty">
      <h1>Your favourites</h1>
      <p className="subtle">Sign in to keep a list of games you care about.</p>
      <div className="empty-actions">
        <button className="button" onClick={() => signIn("/favorites")}>
          Sign in
        </button>
        <a href={registerUrl}>Create an account</a>
      </div>
    </div>
  );
}

export function Favorites() {
  const { account, ready } = useAuth();
  const favorites = useAsync(() => (account ? api.favorites() : Promise.resolve([])), [account]);

  if (!ready) return null;
  if (!account) return <SignInPrompt />;
  return (
    <>
      <header className="page-head">
        <h1>Favourites</h1>
        <p>Games you saved, newest additions last.</p>
      </header>
      {favorites.error && <ErrorNotice error={favorites.error} onRetry={favorites.reload} />}
      {favorites.data?.length === 0 && (
        <Notice>
          Nothing saved yet. Open any game and choose <em>Save to favourites</em>.
        </Notice>
      )}
      <div className="grid">
        {favorites.data?.map((game) => (
          <GameCard game={game} key={game.id} />
        ))}
      </div>
    </>
  );
}
