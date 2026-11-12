import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { api } from "../api";
import { useAuth } from "../auth";
import GameCard from "../components/GameCard";
import { ErrorNotice, Notice } from "../components/ui";
import { useAsync } from "../hooks";

function Credentials({ mode }: { mode: "login" | "register" }) {
  const { signIn } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<Error>();
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(undefined);
    try {
      if (mode === "register") await api.register(email, password);
      signIn(await api.login(email, password));
      navigate("/favorites");
    } catch (err) {
      setError(err as Error);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth-card">
      <h1>{mode === "login" ? "Sign in" : "Create an account"}</h1>
      <p className="subtle">Save games to your favourites and find them again later.</p>
      <form className="form" onSubmit={submit}>
        <label className="field">
          Email
          <input type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label className="field">
          Password
          <input
            type="password"
            required
            autoComplete={mode === "login" ? "current-password" : "new-password"}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        {error && <ErrorNotice error={error} />}
        <button className="button" type="submit" disabled={busy}>
          {busy ? "One moment…" : mode === "login" ? "Sign in" : "Create account"}
        </button>
      </form>
      <p className="subtle small">
        {mode === "login" ? (
          <>
            No account? <Link to="/register">Create one</Link>
          </>
        ) : (
          <>
            Already registered? <Link to="/login">Sign in</Link>
          </>
        )}
      </p>
    </div>
  );
}

export const Login = () => <Credentials mode="login" />;
export const Register = () => <Credentials mode="register" />;

export function Favorites() {
  const { user } = useAuth();
  const favorites = useAsync(() => (user ? api.favorites(user.id) : Promise.resolve([])), [user?.id]);

  if (!user) {
    return (
      <div className="empty">
        <h1>Your favourites</h1>
        <p className="subtle">Sign in to keep a list of games you care about.</p>
        <Link to="/login" className="button">
          Sign in
        </Link>
      </div>
    );
  }
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
