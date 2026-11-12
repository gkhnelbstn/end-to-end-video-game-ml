import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api, ApiError } from "../api";
import { useAuth } from "../auth";
import {
  CriticScore,
  ErrorNotice,
  fmt,
  HowEstimatesWork,
  Notice,
  RECEPTION_LABEL,
  ReceptionStrip,
  receptionOf,
  releaseDate,
} from "../components/ui";
import { useAsync } from "../hooks";
import type { Expectation, Game } from "../types";

function Names({ items }: { items: { id: number; name: string }[] }) {
  if (items.length === 0) return <span className="subtle">Not listed</span>;
  return <>{items.map((i) => i.name).join(", ")}</>;
}

/** How the real score compares with what the model would have said before launch. */
function hindsight(actual: number, e: Expectation): string {
  const range = `${e.low}–${e.high}`;
  if (actual > e.high) return `From what was known before launch, we'd have put it at ${range}. It beat that by ${actual - e.high}.`;
  if (actual < e.low) return `From what was known before launch, we'd have put it at ${range}. It fell short by ${e.low - actual}.`;
  return `From what was known before launch, we'd have put it at ${range}, and it landed inside that range.`;
}

function Reception({ game }: { game: Game }) {
  const prediction = useAsync(() => api.predictedMetacritic(game.id), [game.id]);
  const expected = prediction.data?.expected;
  const thin = game.genres.length === 0 || game.tags.length === 0;
  const noModel = prediction.error instanceof ApiError && prediction.error.status === 503;

  if (game.metacritic !== null) {
    return (
      <section className="verdict" aria-label="Reception">
        <div className="verdict-head">
          <CriticScore value={game.metacritic} size="lg" />
          <div>
            <p className="verdict-word">{RECEPTION_LABEL[receptionOf(game.metacritic)]}</p>
            <p className="verdict-source">Metacritic critics' score</p>
          </div>
        </div>
        <ReceptionStrip actual={game.metacritic} expected={expected} scale />
        {expected && <p className="verdict-aside">{hindsight(game.metacritic, expected)}</p>}
        {game.critic_rating !== null && (
          <p className="verdict-aside">IGDB's critic average is {Math.round(game.critic_rating)}.</p>
        )}
      </section>
    );
  }

  return (
    <section className="verdict" aria-label="Expected reception">
      {expected ? (
        <>
          <div className="verdict-head">
            <span className={`critic expected ${expected.reception} lg`} aria-hidden>
              ≈{Math.round(expected.score)}
            </span>
            <div>
              <p className="verdict-word">{RECEPTION_LABEL[expected.reception]}</p>
              <p className="verdict-source">
                Expected · likely {expected.low}–{expected.high}
              </p>
            </div>
          </div>
          <ReceptionStrip expected={expected} scale />
          <p className="verdict-aside">
            Critics haven't scored this one. The range is our estimate from its genres, platforms, tags and release
            details.
            {thin && " Little is known about it yet, so read it loosely."}
          </p>
        </>
      ) : prediction.loading ? (
        <div className="skeleton" style={{ minHeight: 120 }} />
      ) : noModel ? (
        <p className="verdict-aside">Critics haven't scored this one, and no estimate is available yet.</p>
      ) : prediction.error ? (
        <ErrorNotice error={prediction.error} onRetry={prediction.reload} prefix="Could not load the estimate" />
      ) : null}
    </section>
  );
}

function SaveButton({ gameId }: { gameId: number }) {
  const { account, ready, signIn } = useAuth();
  const [saved, setSaved] = useState<boolean | null>(null);
  const [error, setError] = useState<string>();

  useEffect(() => {
    if (!account) return;
    api.favorites().then(
      (games) => setSaved(games.some((g) => g.id === gameId)),
      () => setSaved(false),
    );
  }, [account, gameId]);

  if (!ready) return null;
  if (!account) {
    return (
      <button className="button quiet" onClick={() => signIn()}>
        Sign in to save
      </button>
    );
  }
  const toggle = async () => {
    setError(undefined);
    try {
      if (saved) await api.removeFavorite(gameId);
      else await api.addFavorite(gameId);
      setSaved(!saved);
    } catch (e) {
      setError((e as Error).message);
    }
  };
  return (
    <>
      <button className={saved ? "button quiet" : "button"} disabled={saved === null} onClick={toggle} aria-pressed={!!saved}>
        {saved ? "Saved to favourites" : "Save to favourites"}
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
          <h1>No game with this address</h1>
          <Link to="/">Back to all games</Link>
        </div>
      );
    }
    return <ErrorNotice error={game.error} onRetry={game.reload} />;
  }
  const g = game.data!;
  const steamUrl = g.steam_appid ? `https://store.steampowered.com/app/${g.steam_appid}` : null;
  const upcoming = g.released ? new Date(g.released) > new Date() : true;

  return (
    <article className="game">
      <header
        className={`game-hero${g.background_image ? " has-image" : ""}`}
        style={g.background_image ? { ["--hero" as string]: `url("${g.background_image}")` } : undefined}
      >
        <div className="game-hero-inner">
          <Link to="/" className="back">
            All games
          </Link>
          <h1>{g.name}</h1>
          <p className="game-when">
            {upcoming && g.released ? "Out " : ""}
            {releaseDate(g.released)}
            {g.esrb_rating && <span className="rating-mark">ESRB {g.esrb_rating}</span>}
          </p>
          <div className="game-actions">
            <SaveButton gameId={g.id} />
            {steamUrl && (
              <a className="button quiet" href={steamUrl} target="_blank" rel="noreferrer">
                Open on Steam
              </a>
            )}
          </div>
        </div>
      </header>

      <div className="game-body">
        <div className="game-main">
          <Reception game={g} />
          {g.clip && g.clip.endsWith(".mp4") && (
            <video src={g.clip} controls preload="none" poster={g.background_image ?? undefined} className="video" />
          )}
          {g.tags.length > 0 && (
            <section>
              <h2 className="section-title">Tagged as</h2>
              <ul className="tag-list">
                {g.tags.map((t) => (
                  <li key={t.id}>{t.name}</li>
                ))}
              </ul>
            </section>
          )}
          <HowEstimatesWork />
        </div>
        <aside className="game-facts">
          <dl>
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
            {g.rating !== null && g.rating > 0 && (
              <>
                <dt>Players</dt>
                <dd>
                  {g.rating.toFixed(1)} out of 5
                  {g.ratings_count ? <span className="subtle"> from {fmt(g.ratings_count)} ratings</span> : null}
                </dd>
              </>
            )}
            {g.playtime ? (
              <>
                <dt>Typical playtime</dt>
                <dd>{g.playtime} hours</dd>
              </>
            ) : null}
          </dl>
        </aside>
      </div>
    </article>
  );
}
