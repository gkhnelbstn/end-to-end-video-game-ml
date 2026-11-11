import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api, ApiError } from "../api";
import { useAuth } from "../auth";
import { Notice, Score } from "../components/ui";
import { useAsync } from "../hooks";
import type { Game } from "../types";

function Names({ items }: { items: { id: number; name: string }[] }) {
  if (items.length === 0) return <span className="subtle">–</span>;
  return (
    <div className="chips">
      {items.map((item) => (
        <span className="chip" key={item.id}>
          {item.name}
        </span>
      ))}
    </div>
  );
}

function Prediction({ game }: { game: Game }) {
  const prediction = useAsync(() => api.predictedMetacritic(game.id), [game.id]);
  if (prediction.loading) return <p className="subtle">Asking the model…</p>;
  if (prediction.error) {
    const unavailable = prediction.error instanceof ApiError && prediction.error.status === 503;
    return (
      <p className="subtle">
        {unavailable ? "No trained model is available yet." : `Prediction failed: ${prediction.error.message}`}
      </p>
    );
  }
  const p = prediction.data!;
  const diff = game.metacritic !== null ? p.predicted_metacritic - game.metacritic : null;
  return (
    <>
      <div className="score-block">
        <Score value={p.predicted_metacritic} big title="Predicted Metacritic" />
        <div>
          <strong>Predicted</strong>
          <small>
            model v{p.model_version}
            {diff !== null && ` · ${diff > 0 ? "+" : ""}${diff.toFixed(1)} vs actual`}
          </small>
        </div>
      </div>
      <p className="subtle" style={{ fontSize: "0.85rem", margin: "0.6rem 0 0" }}>
        Estimated from release year, genres, platforms and tags only. See the{" "}
        <Link to="/predict">Score predictor</Link> for how accurate that is.
      </p>
    </>
  );
}

function FavoriteButton({ gameId }: { gameId: number }) {
  const { user } = useAuth();
  const [isFavorite, setIsFavorite] = useState<boolean | null>(null);
  const [error, setError] = useState<string>();

  useEffect(() => {
    if (!user) return;
    api.favorites(user.id).then(
      (games) => setIsFavorite(games.some((g) => g.id === gameId)),
      () => setIsFavorite(false),
    );
  }, [user, gameId]);

  if (!user) {
    return (
      <p className="subtle">
        <Link to="/login">Sign in</Link> to save favourites.
      </p>
    );
  }
  const toggle = async () => {
    setError(undefined);
    try {
      if (isFavorite) await api.removeFavorite(user.id, gameId);
      else await api.addFavorite(user.id, gameId);
      setIsFavorite(!isFavorite);
    } catch (e) {
      setError((e as Error).message);
    }
  };
  return (
    <>
      <button className={isFavorite ? "" : "primary"} disabled={isFavorite === null} onClick={toggle}>
        {isFavorite ? "Remove from favourites" : "Add to favourites"}
      </button>
      {error && <Notice kind="error">{error}</Notice>}
    </>
  );
}

export default function GameDetail() {
  const id = Number(useParams().id);
  const game = useAsync(() => api.game(id), [id]);

  if (game.loading) return <div className="skeleton" style={{ minHeight: 320 }} />;
  if (game.error) {
    return (
      <Notice kind="error">
        {game.error instanceof ApiError && game.error.status === 404 ? "Game not found." : game.error.message}{" "}
        <Link to="/">Back to games</Link>
      </Notice>
    );
  }
  const g = game.data!;
  const steamUrl = g.steam_appid ? `https://store.steampowered.com/app/${g.steam_appid}` : null;

  return (
    <>
      <p style={{ margin: "0 0 0.75rem" }}>
        <Link to="/">← All games</Link>
      </p>
      {g.background_image && (
        <div className="hero">
          <img src={g.background_image} alt="" />
        </div>
      )}
      <div className="page-head">
        <h1 style={{ margin: 0 }}>{g.name}</h1>
      </div>

      <div className="detail">
        <div>
          <div className="card section">
            <dl className="facts">
              <dt>Released</dt>
              <dd>{g.released ? g.released.slice(0, 10) : "TBA"}</dd>
              <dt>Genres</dt>
              <dd>
                <Names items={g.genres} />
              </dd>
              <dt>Platforms</dt>
              <dd>
                <Names items={g.platforms} />
              </dd>
              <dt>Stores</dt>
              <dd>
                <Names items={g.stores} />
              </dd>
              {g.rating !== null && (
                <>
                  <dt>User rating</dt>
                  <dd>
                    {g.rating.toFixed(2)} / 5{g.ratings_count ? ` (${g.ratings_count.toLocaleString()} ratings)` : ""}
                  </dd>
                </>
              )}
              {g.playtime ? (
                <>
                  <dt>Average playtime</dt>
                  <dd>{g.playtime} h</dd>
                </>
              ) : null}
              {steamUrl && (
                <>
                  <dt>Steam</dt>
                  <dd>
                    <a href={steamUrl} target="_blank" rel="noreferrer">
                      Store page
                    </a>
                  </dd>
                </>
              )}
            </dl>
          </div>
          {g.tags.length > 0 && (
            <div className="card section">
              <h2>Tags</h2>
              <Names items={g.tags} />
            </div>
          )}
          {g.clip && g.clip.endsWith(".mp4") && (
            <div className="card section">
              <h2>Trailer</h2>
              <video src={g.clip} controls style={{ width: "100%", borderRadius: 8 }} />
            </div>
          )}
        </div>

        <div>
          <div className="card section">
            <h2>Scores</h2>
            <div className="scores">
              <div className="score-block">
                <Score value={g.metacritic} big title="Metacritic" />
                <div>
                  <strong>Metacritic</strong>
                  <small>{g.metacritic === null ? "not scored" : "actual"}</small>
                </div>
              </div>
              {g.critic_rating !== null && (
                <div className="score-block">
                  <Score value={g.critic_rating} big title="IGDB critic rating" />
                  <div>
                    <strong>IGDB critics</strong>
                    <small>average</small>
                  </div>
                </div>
              )}
            </div>
            <Prediction game={g} />
          </div>
          <div className="card section">
            <h2>Favourites</h2>
            <FavoriteButton gameId={g.id} />
          </div>
        </div>
      </div>
    </>
  );
}
