import { Link, Navigate, NavLink, Route, Routes } from "react-router-dom";

import { accountUrl, registerUrl, useAuth } from "./auth";
import { Callback, Favorites, Login } from "./pages/Account";
import GameDetail from "./pages/GameDetail";
import Games from "./pages/Games";
import Predictor from "./pages/Predictor";
import Stats from "./pages/Stats";

function Header() {
  const { account, ready, signIn, signOut } = useAuth();
  return (
    <header className="topbar">
      <div className="topbar-inner">
        <Link to="/" className="wordmark" aria-label="Game Insight, all games">
          Game<span>Insight</span>
        </Link>
        <nav className="nav" aria-label="Main">
          <NavLink to="/" end>
            Games
          </NavLink>
          <NavLink to="/stats">Catalogue</NavLink>
          <NavLink to="/favorites">Favourites</NavLink>
        </nav>
        <div className="account">
          {!ready ? null : account ? (
            <>
              <a className="account-name" href={accountUrl} title="Your account: e-mail, password, passkeys">
                {account.name ?? account.email}
              </a>
              <button className="link-button" onClick={signOut}>
                Sign out
              </button>
            </>
          ) : (
            <>
              <a href={registerUrl}>Create account</a>
              <button className="link-button" onClick={() => signIn()}>
                Sign in
              </button>
            </>
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
          <Route path="/estimate" element={<Predictor />} />
          <Route path="/predict" element={<Navigate to="/estimate" replace />} />
          <Route path="/favorites" element={<Favorites />} />
          <Route path="/login" element={<Login />} />
          <Route path="/callback" element={<Callback />} />
          <Route
            path="*"
            element={
              <div className="empty">
                <h1>Nothing at this address</h1>
                <Link to="/">Back to all games</Link>
              </div>
            }
          />
        </Routes>
      </main>
      <footer className="footer">
        <span>Game data from RAWG, Steam and IGDB. Scores from Metacritic.</span>
        <Link to="/estimate">Estimate a game that isn't out yet</Link>
      </footer>
    </>
  );
}
