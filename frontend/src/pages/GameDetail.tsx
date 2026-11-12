import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api, ApiError } from "../api";
import { useAuth } from "../auth";
import { ErrorNotice, fmt, Notice, Score, ScoreScale } from "../components/ui";
import { useAsync } from "../hooks";
import type { Game } from "../types";

function Chips({ items }: { items: { id: number; name: string }[] }) {
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

function ScorePanel({ game }: { game: Game }) {
  const prediction = useAsync(() => api.predictedMetacritic(game.id), [game.id]);
  const model = useAsync(api.model, []);
  const p = prediction.data;
  const mae = model.data?.metrics.test_mae;
  const diff = p && game.metacritic !== null ? p.predicted_metacritic - game.metacritic : null;

  return (
    <div className="panel">
      <h2>Scores</h2>
      <div className="score-pair">
        <div className="score-item">
          <Score value={game.metacritic} size="lg" title="Metacritic" />
          <div>
            <strong>Metacritic</strong>
            <small>{game.metacritic === null ? "not scored" : "critics' score"}</small>
          </div>
        </div>
        <div className="score-item">
          {p ? (
            <Score value={p.predicted_metacritic} size="lg" title="Predicted Metacritic" />
          ) : (
            <span className="score none lg">{prediction.loading ? "…" : "–"}</span>
          )}
          <div>
            <strong>Predicted</strong>
            <small>
              {p
                ? `model v${p.model_version}${diff !== null ? ` · ${diff > 0 ? "+" : ""}${diff.toFixed(1)} vs actual` : ""}`
                : prediction.loading
                  ? "asking the model…"
                  : "unavailable"}
            </small>
          </div>
        </div>
      </div>
      {(game.metacritic !== null || p) && (
        <ScoreScale actual={game.metacritic} predicted={p?.predicted_metacritic} spread={p ? mae : null} />
      )}
      {prediction.error &&
        (prediction.error instanceof ApiError && prediction.error.status === 503 ? (
          <Notice>No trained model is available yet.</Notice>
        ) : (
          <ErrorNotice error={prediction.error} onRetry={prediction.reload} prefix="Prediction failed" />
        ))}
      {game.critic_rating !== null && (
        <p className="subtle small">
          IGDB critics average: <strong>{Math.round(game.critic_rating)}</strong>
        </p>
      )}
      {p && (
        <p className="subtle small">
          The model only sees the title, release date, ESRB rating, genres, platforms, stores and tags, not reviews or
          sales.{mae !== undefined && ` The shaded band is ± its average miss (${mae.toFixed(1)} points).`}{" "}
          <Link to="/predict">How it works</Link>
        </p>
      )}
    </div>
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
      <Link to="/login" className="button ghost">
        ☆ Sign in to save
      </Link>
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
      <button className={isFavorite ? "ghost" : "primary"} disabled={isFavorite === null} onClick={toggle}>
        {isFavorite ? "★ Remove from favourites" : "☆ Add to favourites"}
      </button>
      {error && <Notice kind="error">{error}</Notice>}
    </>
  );
}

export default function GameDetail() {
  const id = Number(useParams().id);
  const game = useAsync(() => api.game(id), [id]);

  if (game.loading) return <div className="skeleton" style={{ minHeight: 360 }} />;
  if (game.error) {
    if (game.error instanceof ApiError && game.error.status === 404) {
      return (
        <div className="empty">
          <h1>Game not found</h1>
          <Link to="/">Back to games</Link>
        </div>
      );
    }
    return <ErrorNotice error={game.error} onRetry={game.reload} />;
  }
  const g = game.data!;
  const steamUrl = g.steam_appid ? `https://store.steampowered.com/app/${g.steam_appid}` : null;
  const released = g.released
    ? new Date(g.released).toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" })
    : "TBA";

  return (
    <>
      <section className="detail-hero" style={g.background_image ? { ["--hero" as string]: `url("${g.background_image}")` } : undefined}>
        <div className="detail-hero-inner">
          <Link to="/" className="back">
            ← All games
          </Link>
          <h1>{g.name}</h1>
          <p className="detail-sub">
            {released}
            {g.esrb_rating && <span className="pill">ESRB {g.esrb_rating}</span>}
          </p>
          <div className="detail-actions">
            <FavoriteButton gameId={g.id} />
            {steamUrl && (
              <a className="button ghost" href={steamUrl} target="_blank" rel="noreferrer">
                Steam store ↗
              </a>
            )}
          </div>
        </div>
      </section>

      <div className="detail">
        <div className="stack-lg">
          {g.clip && g.clip.endsWith(".mp4") && (
            <div className="panel">
              <h2>Trailer</h2>
              <video src={g.clip} controls preload="none" poster={g.background_image ?? undefined} className="video" />
            </div>
          )}
          <div className="panel">
            <h2>Details</h2>
            <dl className="facts">
              <dt>Genres</dt>
              <dd>
                <Chips items={g.genres} />
              </dd>
              <dt>Platforms</dt>
              <dd>
                <Chips items={g.platforms} />
              </dd>
              <dt>Stores</dt>
              <dd>
                <Chips items={g.stores} />
              </dd>
              {g.rating !== null && g.rating > 0 && (
                <>
                  <dt>User rating</dt>
                  <dd>
                    {g.rating.toFixed(2)} / 5
                    {g.ratings_count ? <span className="subtle"> · {fmt(g.ratings_count)} ratings</span> : null}
                  </dd>
                </>
              )}
              {g.playtime ? (
                <>
                  <dt>Average playtime</dt>
                  <dd>{g.playtime} h</dd>
                </>
              ) : null}
            </dl>
          </div>
          {g.tags.length > 0 && (
            <div className="panel">
              <h2>Tags</h2>
              <Chips items={g.tags} />
            </div>
          )}
        </div>
        <aside className="stack-lg sticky">
          <ScorePanel game={g} />
        </aside>
      </div>
    </>
  );
}
