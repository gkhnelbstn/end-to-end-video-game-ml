import { Link, useSearchParams } from "react-router-dom";

import { api } from "../api";
import { Cover, Notice, Score, year } from "../components/ui";
import { useAsync, useDebounced } from "../hooks";
import type { GameQuery } from "../types";

const PAGE_SIZE = 24;
const SORTS: { value: string; label: string }[] = [
  { value: "metacritic:desc", label: "Metacritic, high to low" },
  { value: "rating:desc", label: "User rating, high to low" },
  { value: "released:desc", label: "Newest first" },
  { value: "released:asc", label: "Oldest first" },
  { value: "name:asc", label: "Name, A to Z" },
];

export default function Games() {
  // Filters live in the URL so a filtered view can be shared and survives reloads.
  const [params, setParams] = useSearchParams();
  const search = params.get("q") ?? "";
  const genre = params.get("genre") ?? "";
  const platform = params.get("platform") ?? "";
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
        sort_by: sortBy,
        sort_order: sortOrder,
        skip: (page - 1) * PAGE_SIZE,
        limit: PAGE_SIZE,
      }),
    [debouncedSearch, genre, platform, sort, page],
  );

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Games</h1>
          <p className="subtle" style={{ margin: 0 }}>
            Browse the catalogue. Open a game to see what the model predicts for it.
          </p>
        </div>
      </div>

      <div className="filters">
        <label className="field search">
          Search
          <input
            type="search"
            placeholder="Game name"
            value={search}
            onChange={(e) => update({ q: e.target.value })}
          />
        </label>
        <label className="field">
          Genre
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
          Platform
          <select value={platform} onChange={(e) => update({ platform: e.target.value })}>
            <option value="">All platforms</option>
            {platforms.data?.map((p) => (
              <option key={p.id} value={p.slug}>
                {p.name}
              </option>
            ))}
          </select>
        </label>
        <label className="field" style={{ gridColumn: "span 2" }}>
          Sort
          <select value={sort} onChange={(e) => update({ sort: e.target.value })}>
            {SORTS.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      {games.error && <Notice kind="error">Could not load games: {games.error.message}</Notice>}
      {games.loading && !games.data && (
        <div className="game-grid">
          {Array.from({ length: 8 }, (_, i) => (
            <div className="skeleton" key={i} />
          ))}
        </div>
      )}
      {games.data && games.data.length === 0 && <Notice>No games match these filters.</Notice>}
      {games.data && games.data.length > 0 && (
        <div className="game-grid" style={{ opacity: games.loading ? 0.6 : 1 }}>
          {games.data.map((game) => (
            <Link to={`/games/${game.id}`} className="game-card" key={game.id}>
              <Cover game={game} />
              <div className="game-card-body">
                <span className="game-card-title">{game.name}</span>
                <div className="chips">
                  {game.genres.slice(0, 3).map((g) => (
                    <span className="chip" key={g.id}>
                      {g.name}
                    </span>
                  ))}
                </div>
                <div className="meta-row">
                  <span>{year(game.released)}</span>
                  <Score value={game.metacritic} title="Metacritic" />
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}

      <nav className="pager" aria-label="Pages">
        <button disabled={page <= 1} onClick={() => update({ page: String(page - 1) })}>
          Previous
        </button>
        <span>Page {page}</span>
        <button
          disabled={!games.data || games.data.length < PAGE_SIZE}
          onClick={() => update({ page: String(page + 1) })}
        >
          Next
        </button>
      </nav>
    </>
  );
}
