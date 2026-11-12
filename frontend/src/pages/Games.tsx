import { useSearchParams } from "react-router-dom";

import { api } from "../api";
import GameCard from "../components/GameCard";
import { ErrorNotice, fmt, Notice } from "../components/ui";
import { useAsync, useDebounced } from "../hooks";
import type { GameQuery } from "../types";

const PAGE_SIZE = 24;
const SORTS: { value: string; label: string }[] = [
  { value: "metacritic:desc", label: "Metacritic, high to low" },
  { value: "metacritic:asc", label: "Metacritic, low to high" },
  { value: "released:desc", label: "Newest first" },
  { value: "released:asc", label: "Oldest first" },
  { value: "rating:desc", label: "User rating" },
  { value: "name:asc", label: "Name, A to Z" },
];

function Summary() {
  const summary = useAsync(api.summary, []);
  const s = summary.data;
  if (!s) return null;
  return (
    <div className="hero-stats">
      <div>
        <strong>{fmt(s.games)}</strong>
        <span>games</span>
      </div>
      <div>
        <strong>{fmt(s.with_metacritic)}</strong>
        <span>with a Metacritic score</span>
      </div>
      {s.avg_metacritic !== null && (
        <div>
          <strong>{s.avg_metacritic}</strong>
          <span>average score</span>
        </div>
      )}
      {s.first_year && s.last_year && (
        <div>
          <strong>
            {s.first_year}–{s.last_year}
          </strong>
          <span>release years</span>
        </div>
      )}
    </div>
  );
}

export default function Games() {
  // Filters live in the URL so a filtered view can be shared and survives reloads.
  const [params, setParams] = useSearchParams();
  const search = params.get("q") ?? "";
  const genre = params.get("genre") ?? "";
  const platform = params.get("platform") ?? "";
  const scored = params.get("scored") === "1";
  const sort = params.get("sort") ?? SORTS[0].value;
  const page = Math.max(1, Number(params.get("page") ?? 1));
  const debouncedSearch = useDebounced(search);

  const update = (changes: Record<string, string>) => {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(changes)) {
      if (value) next.set(key, value);
      else next.delete(key);
    }
    if (!("page" in changes)) next.delete("page");
    setParams(next, { replace: true });
  };

  const genres = useAsync(api.genres, []);
  const platforms = useAsync(api.platforms, []);
  const [sortBy, sortOrder] = sort.split(":") as [GameQuery["sort_by"], GameQuery["sort_order"]];
  const games = useAsync(
    () =>
      api.games({
        search: debouncedSearch || undefined,
        genre: genre || undefined,
        platform: platform || undefined,
        scored: scored || undefined,
        sort_by: sortBy,
        sort_order: sortOrder,
        skip: (page - 1) * PAGE_SIZE,
        limit: PAGE_SIZE,
      }),
    [debouncedSearch, genre, platform, scored, sort, page],
  );
  const filtered = Boolean(search || genre || platform || scored);

  return (
    <>
      <section className="hero">
        <div>
          <p className="eyebrow">Video game catalogue</p>
          <h1>What do critics think, and what would a model guess?</h1>
          <p className="lede">
            Browse games from RAWG, Steam and IGDB. Every game page shows its Metacritic score next to the score a
            model predicts from what was known before release.
          </p>
        </div>
        <Summary />
      </section>

      <div className="toolbar">
        <label className="field search">
          <span className="sr-only">Search</span>
          <input
            type="search"
            placeholder="Search games…"
            value={search}
            onChange={(e) => update({ q: e.target.value })}
          />
        </label>
        <label className="field">
          <span className="sr-only">Genre</span>
          <select value={genre} onChange={(e) => update({ genre: e.target.value })}>
            <option value="">All genres</option>
            {genres.data?.map((g) => (
              <option key={g.id} value={g.slug}>
                {g.name}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span className="sr-only">Platform</span>
          <select value={platform} onChange={(e) => update({ platform: e.target.value })}>
            <option value="">All platforms</option>
            {platforms.data?.map((p) => (
              <option key={p.id} value={p.slug}>
                {p.name}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span className="sr-only">Sort</span>
          <select value={sort} onChange={(e) => update({ sort: e.target.value })}>
            {SORTS.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </label>
        <label className="toggle">
          <input type="checkbox" checked={scored} onChange={(e) => update({ scored: e.target.checked ? "1" : "" })} />
          Scored only
        </label>
        {filtered && (
          <button className="ghost small" onClick={() => setParams({}, { replace: true })}>
            Clear
          </button>
        )}
      </div>

      {games.error && <ErrorNotice error={games.error} onRetry={games.reload} prefix="Could not load games" />}
      {games.loading && !games.data && (
        <div className="game-grid">
          {Array.from({ length: 12 }, (_, i) => (
            <div className="skeleton card-skeleton" key={i} />
          ))}
        </div>
      )}
      {games.data && games.data.length === 0 && <Notice>No games match these filters.</Notice>}
      {games.data && games.data.length > 0 && (
        <div className={`game-grid${games.loading ? " is-loading" : ""}`}>
          {games.data.map((game) => (
            <GameCard game={game} key={game.id} />
          ))}
        </div>
      )}

      {games.data && (page > 1 || games.data.length === PAGE_SIZE) && (
        <nav className="pager" aria-label="Pages">
          <button disabled={page <= 1} onClick={() => update({ page: String(page - 1) })}>
            ← Previous
          </button>
          <span>Page {page}</span>
          <button disabled={games.data.length < PAGE_SIZE} onClick={() => update({ page: String(page + 1) })}>
            Next →
          </button>
        </nav>
      )}
    </>
  );
}
