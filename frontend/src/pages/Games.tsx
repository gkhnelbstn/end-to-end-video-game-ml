import { useSearchParams } from "react-router-dom";

import { api } from "../api";
import GameCard from "../components/GameCard";
import { ErrorNotice, fmt, Notice } from "../components/ui";
import { useAsync, useDebounced } from "../hooks";
import type { Game, GameQuery } from "../types";

const PAGE_SIZE = 24;
const SORTS: { value: string; label: string }[] = [
  { value: "metacritic:desc", label: "Highest rated" },
  { value: "released:desc", label: "Newest" },
  { value: "released:asc", label: "Oldest" },
  { value: "rating:desc", label: "Player rating" },
  { value: "name:asc", label: "A to Z" },
];

const isoDate = (d: Date) => d.toISOString().slice(0, 10);

function Shelf({ title, note, load, deps }: { title: string; note: string; load: () => Promise<Game[]>; deps: unknown[] }) {
  const games = useAsync(load, deps);
  if (games.error || (games.data && games.data.length === 0)) return null;
  return (
    <section className="shelf" aria-label={title}>
      <header className="shelf-head">
        <h2>{title}</h2>
        <p>{note}</p>
      </header>
      <div className="shelf-row">
        {games.data
          ? games.data.map((game) => <GameCard game={game} key={game.id} />)
          : Array.from({ length: 5 }, (_, i) => <div className="skeleton card-skeleton" key={i} />)}
      </div>
    </section>
  );
}

// Shelves ask for more than they show: only games the model has enough data on carry an estimate.
const withEstimate = (games: Game[]) => games.filter((g) => g.expected).slice(0, 12);

const upcoming = async () =>
  withEstimate(
    await api.games({ released_from: isoDate(new Date()), scored: false, sort_by: "released", sort_order: "asc", limit: 60 }),
  );

/** Games players know (most ratings) that critics never scored, from the last few years of data. */
const awaitingVerdict = async () => {
  const from = new Date();
  from.setFullYear(from.getFullYear() - 4);
  return withEstimate(
    await api.games({
      released_from: isoDate(from),
      released_to: isoDate(new Date()),
      scored: false,
      sort_by: "ratings_count",
      sort_order: "desc",
      limit: 60,
    }),
  );
};

const recentlyReviewed = () =>
  api.games({ scored: true, released_to: isoDate(new Date()), sort_by: "released", sort_order: "desc", limit: 12 });

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

  const summary = useAsync(api.summary, []);
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
      <div className="finder">
        <label className="finder-search">
          <span className="sr-only">Search games</span>
          <input
            type="search"
            placeholder={summary.data ? `Search ${fmt(summary.data.games)} games by title` : "Search games by title"}
            value={search}
            onChange={(e) => update({ q: e.target.value })}
          />
        </label>
        <div className="genre-rail" role="group" aria-label="Genre">
          <button className={`rail-chip${genre ? "" : " on"}`} aria-pressed={!genre} onClick={() => update({ genre: "" })}>
            All
          </button>
          {genres.data?.map((g) => (
            <button
              key={g.id}
              className={`rail-chip${genre === g.slug ? " on" : ""}`}
              aria-pressed={genre === g.slug}
              onClick={() => update({ genre: genre === g.slug ? "" : g.slug })}
            >
              {g.name}
            </button>
          ))}
        </div>
      </div>

      {!filtered && page === 1 && (
        <>
          <Shelf
            title="Coming up"
            note="The hatched range is the reception critics are likely to give, judged from what is known so far."
            load={upcoming}
            deps={[]}
          />
          <Shelf
            title="Waiting for a verdict"
            note="Recent games players rate a lot that critics never scored, with the reception they would likely have had."
            load={awaitingVerdict}
            deps={[]}
          />
          <Shelf title="Recently reviewed" note="The latest games with a Metacritic score." load={recentlyReviewed} deps={[]} />
        </>
      )}

      <section className="catalogue" aria-label="All games">
        <header className="catalogue-head">
          <h2>{filtered ? "Results" : "All games"}</h2>
          <div className="catalogue-controls">
            <label>
              <span className="sr-only">Platform</span>
              <select value={platform} onChange={(e) => update({ platform: e.target.value })}>
                <option value="">Any platform</option>
                {platforms.data?.map((p) => (
                  <option key={p.id} value={p.slug}>
                    {p.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span className="sr-only">Sort by</span>
              <select value={sort} onChange={(e) => update({ sort: e.target.value })}>
                {SORTS.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="check">
              <input type="checkbox" checked={scored} onChange={(e) => update({ scored: e.target.checked ? "1" : "" })} />
              Reviewed only
            </label>
            {filtered && (
              <button className="link-button" onClick={() => setParams({}, { replace: true })}>
                Clear filters
              </button>
            )}
          </div>
        </header>

        {games.error && <ErrorNotice error={games.error} onRetry={games.reload} prefix="Could not load games" />}
        {games.loading && !games.data && (
          <div className="grid">
            {Array.from({ length: 12 }, (_, i) => (
              <div className="skeleton card-skeleton" key={i} />
            ))}
          </div>
        )}
        {games.data && games.data.length === 0 && (
          <Notice>Nothing matches. Try a shorter title, or clear the genre and platform.</Notice>
        )}
        {games.data && games.data.length > 0 && (
          <div className={`grid${games.loading ? " is-loading" : ""}`}>
            {games.data.map((game) => (
              <GameCard game={game} key={game.id} />
            ))}
          </div>
        )}

        {games.data && (page > 1 || games.data.length === PAGE_SIZE) && (
          <nav className="pager" aria-label="Pages">
            <button disabled={page <= 1} onClick={() => update({ page: String(page - 1) })}>
              Previous
            </button>
            <span>Page {page}</span>
            <button disabled={games.data.length < PAGE_SIZE} onClick={() => update({ page: String(page + 1) })}>
              Next
            </button>
          </nav>
        )}
      </section>
    </>
  );
}
