import { Link, NavLink, Route, Routes } from "react-router-dom";

import { useAuth } from "./auth";
import { Login, Favorites, Register } from "./pages/Account";
import GameDetail from "./pages/GameDetail";
import Games from "./pages/Games";
import Predictor from "./pages/Predictor";
import Stats from "./pages/Stats";

function Header() {
  const { user, signOut } = useAuth();
  return (
    <header className="topbar">
      <div className="topbar-inner">
        <Link to="/" className="brand">
          <span className="brand-mark" aria-hidden />
          Game Insight
        </Link>
        <nav className="nav">
          <NavLink to="/" end>
            Games
          </NavLink>
          <NavLink to="/stats">Statistics</NavLink>
          <NavLink to="/predict">Score predictor</NavLink>
          <NavLink to="/favorites">Favourites</NavLink>
        </nav>
        <div className="account">
          {user ? (
            <>
              <span>{user.email}</span>
              <button className="link" onClick={signOut}>
                Sign out
              </button>
            </>
          ) : (
            <Link to="/login">Sign in</Link>
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
          <Route path="*" element={<p>Page not found. <Link to="/">Back to games</Link></p>} />
        </Routes>
      </main>
    </>
  );
}
