import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { api } from "../api";
import { useAuth } from "../auth";
import { Cover, Notice, Score, year } from "../components/ui";
import { useAsync } from "../hooks";

function Credentials({ mode }: { mode: "login" | "register" }) {
  const { signIn } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string>();
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
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card narrow">
      <h1>{mode === "login" ? "Sign in" : "Create an account"}</h1>
      <form className="stack" onSubmit={submit}>
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
        {error && <Notice kind="error">{error}</Notice>}
        <button className="primary" type="submit" disabled={busy}>
          {mode === "login" ? "Sign in" : "Create account"}
        </button>
      </form>
      <p className="subtle" style={{ marginBottom: 0 }}>
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
      <Notice>
        <Link to="/login">Sign in</Link> to see your favourite games.
      </Notice>
    );
  }
  return (
    <>
      <div className="page-head">
        <div>
          <h1>Favourites</h1>
          <p className="subtle" style={{ margin: 0 }}>
            Signed in as {user.email}
          </p>
        </div>
      </div>
      {favorites.error && <Notice kind="error">{favorites.error.message}</Notice>}
      {favorites.data?.length === 0 && (
        <Notice>
          No favourites yet. Open a game and press <em>Add to favourites</em>.
        </Notice>
      )}
      <div className="game-grid">
        {favorites.data?.map((game) => (
          <Link to={`/games/${game.id}`} className="game-card" key={game.id}>
            <Cover game={game} />
            <div className="game-card-body">
              <span className="game-card-title">{game.name}</span>
              <div className="meta-row">
                <span>{year(game.released)}</span>
                <Score value={game.metacritic} title="Metacritic" />
              </div>
            </div>
          </Link>
        ))}
      </div>
    </>
  );
}
