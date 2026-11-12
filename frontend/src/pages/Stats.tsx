import { api } from "../api";
import { Bars, ErrorNotice, fmt, Stat } from "../components/ui";
import { useAsync, type Async } from "../hooks";

/** Loading skeleton, error with retry, or the content once the data is in. */
function Load<T>({ state, height = 220, children }: { state: Async<T>; height?: number; children: (data: T) => JSX.Element }) {
  if (state.error) return <ErrorNotice error={state.error} onRetry={state.reload} />;
  if (state.data === undefined) return <div className="skeleton" style={{ minHeight: height }} />;
  return children(state.data);
}

function Columns({
  rows,
  label,
  tick,
  colour,
}: {
  rows: { key: number; count: number }[];
  label: (key: number) => string;
  tick: (key: number) => boolean;
  colour?: (key: number) => string;
}) {
  const max = Math.max(...rows.map((r) => r.count), 1);
  return (
    <div className="column-chart">
      <div className="columns" role="list">
        {rows.map((r) => (
          <div className="column-slot" key={r.key} role="listitem" aria-label={`${label(r.key)}: ${fmt(r.count)}`}>
            <div className={`column ${colour?.(r.key) ?? ""}`} style={{ height: `${(r.count / max) * 100}%` }} />
            <span className="column-tip">
              {label(r.key)}
              <strong>{fmt(r.count)}</strong>
            </span>
          </div>
        ))}
      </div>
      <div className="column-axis">
        {rows.map((r) => (
          <span key={r.key}>{tick(r.key) ? label(r.key) : ""}</span>
        ))}
      </div>
    </div>
  );
}

export default function Stats() {
  const summary = useAsync(api.summary, []);
  const perYear = useAsync(api.gamesPerYear, []);
  const scores = useAsync(api.metacriticDistribution, []);
  const genres = useAsync(() => api.topGenres(12), []);
  const platforms = useAsync(() => api.topPlatforms(12), []);
  const ratings = useAsync(api.avgRatingByGenre, []);

  return (
    <>
      <section className="page-intro">
        <p className="eyebrow">Statistics</p>
        <h1>The catalogue in numbers</h1>
        <p className="lede">Computed live from the database every time you open this page.</p>
      </section>

      <Load state={summary} height={90}>
        {(s) => (
          <div className="stats-row big">
            <Stat label="Games" value={fmt(s.games)} />
            <Stat
              label="With a Metacritic score"
              value={fmt(s.with_metacritic)}
              hint={s.games ? `${((s.with_metacritic / s.games) * 100).toFixed(1)}% of all games` : undefined}
            />
            <Stat label="Average Metacritic" value={s.avg_metacritic ?? "–"} />
            <Stat label="Genres · platforms" value={`${s.genres} · ${s.platforms}`} />
          </div>
        )}
      </Load>

      <div className="panel">
        <h2>Games released per year</h2>
        <Load state={perYear}>
          {(data) => {
            const rows = data.filter((r) => r.year >= 1980 && r.year <= new Date().getFullYear()).map((r) => ({ key: r.year, count: r.count }));
            return <Columns rows={rows} label={String} tick={(y) => y % 5 === 0} />;
          }}
        </Load>
      </div>

      <div className="grid-2">
        <div className="panel">
          <h2>Metacritic scores</h2>
          <p className="subtle small">How many scored games fall into each 10-point band.</p>
          <Load state={scores}>
            {(data) => (
              <Columns
                rows={data.map((r) => ({ key: r.band, count: r.count }))}
                label={(b) => (b === 90 ? "90–100" : `${b}–${b + 9}`)}
                tick={() => true}
                colour={(b) => (b >= 75 ? "good" : b >= 50 ? "mid" : "bad")}
              />
            )}
          </Load>
        </div>
        <div className="panel">
          <h2>Average user rating by genre</h2>
          <p className="subtle small">RAWG user ratings out of 5; unrated games are left out.</p>
          <Load state={ratings}>
            {(data) => (
              <Bars
                rows={[...data]
                  .sort((a, b) => b.avg_rating - a.avg_rating)
                  .slice(0, 12)
                  .map((r) => ({ label: r.genre, value: r.avg_rating }))}
                format={(v) => v.toFixed(2)}
                max={5}
              />
            )}
          </Load>
        </div>
        <div className="panel">
          <h2>Top genres</h2>
          <Load state={genres}>{(data) => <Bars rows={data.map((r) => ({ label: r.name, value: r.count }))} />}</Load>
        </div>
        <div className="panel">
          <h2>Top platforms</h2>
          <Load state={platforms}>
            {(data) => <Bars rows={data.map((r) => ({ label: r.name, value: r.count }))} />}
          </Load>
        </div>
      </div>
    </>
  );
}
