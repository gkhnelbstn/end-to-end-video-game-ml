import { Link, NavLink, Route, Routes } from "react-router-dom";

import { useAuth } from "./auth";
import { Login, Favorites, Register } from "./pages/Account";
import GameDetail from "./pages/GameDetail";
import Games from "./pages/Games";
import Predictor from "./pages/Predictor";
import Stats from "./pages/Stats";

function Logo() {
  return (
    <svg className="brand-mark" viewBox="0 0 32 32" aria-hidden>
      <rect width="32" height="32" rx="9" fill="var(--accent)" />
      <path d="M8 21l5-6 4 4 7-9" fill="none" stroke="var(--on-accent)" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function Header() {
  const { user, signOut } = useAuth();
  return (
    <header className="topbar">
      <div className="topbar-inner">
        <Link to="/" className="brand">
          <Logo />
          <span>
            Game<span className="brand-accent">Insight</span>
          </span>
        </Link>
        <nav className="nav" aria-label="Main">
          <NavLink to="/" end>
            Games
          </NavLink>
          <NavLink to="/stats">Statistics</NavLink>
          <NavLink to="/predict">Predictor</NavLink>
          <NavLink to="/favorites">Favourites</NavLink>
        </nav>
        <div className="account">
          {user ? (
            <>
              <span className="avatar" title={user.email}>
                {user.email[0].toUpperCase()}
              </span>
              <button className="ghost small" onClick={signOut}>
                Sign out
              </button>
            </>
          ) : (
            <Link to="/login" className="button ghost small">
              Sign in
            </Link>
          )}
        </div>
      </div>
    </header>
  );
}

export default function App() {
  return (
    <>
      <Header />
      <main>
        <Routes>
          <Route path="/" element={<Games />} />
          <Route path="/games/:id" element={<GameDetail />} />
          <Route path="/stats" element={<Stats />} />
          <Route path="/predict" element={<Predictor />} />
          <Route path="/favorites" element={<Favorites />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route
            path="*"
            element={
              <div className="empty">
                <h1>Page not found</h1>
                <Link to="/">Back to games</Link>
              </div>
            }
          />
        </Routes>
      </main>
      <footer className="footer">
        Data from RAWG, Steam and IGDB · predictions from the MLflow <code>champion</code> model
      </footer>
    </>
  );
}
