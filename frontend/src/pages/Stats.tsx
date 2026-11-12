import { api } from "../api";
import { Bars, ErrorNotice, Figure, fmt } from "../components/ui";
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
      <header className="page-head">
        <h1>The catalogue</h1>
        <p>What's in the database right now, counted when you open this page.</p>
      </header>

      <Load state={summary} height={90}>
        {(s) => (
          <div className="figures">
            <Figure label="games" value={fmt(s.games)} />
            <Figure
              label="reviewed by critics"
              value={fmt(s.with_metacritic)}
              hint={s.games ? `${((s.with_metacritic / s.games) * 100).toFixed(1)}% of all games` : undefined}
            />
            <Figure label="average critics' score" value={s.avg_metacritic ?? "–"} />
            <Figure label="genres · platforms" value={`${s.genres} · ${s.platforms}`} />
          </div>
        )}
      </Load>

      <section className="chart">
        <h2>Games released per year</h2>
        <Load state={perYear}>
          {(data) => {
            const rows = data
              .filter((r) => r.year >= 1980 && r.year <= new Date().getFullYear())
              .map((r) => ({ key: r.year, count: r.count }));
            return <Columns rows={rows} label={String} tick={(y) => y % 5 === 0} />;
          }}
        </Load>
      </section>

      <div className="chart-grid">
        <section className="chart">
          <h2>How critics score</h2>
          <p className="chart-note">Reviewed games in each 10-point band, coloured by Metacritic's wording.</p>
          <Load state={scores}>
            {(data) => (
              <Columns
                rows={data.map((r) => ({ key: r.band, count: r.count }))}
                label={(b) => (b === 90 ? "90–100" : `${b}–${b + 9}`)}
                tick={() => true}
                colour={(b) => (b >= 90 ? "acclaim" : b >= 75 ? "favourable" : b >= 50 ? "mixed" : "unfavourable")}
              />
            )}
          </Load>
        </section>
        <section className="chart">
          <h2>What players think, by genre</h2>
          <p className="chart-note">Average RAWG player rating out of 5. Games nobody rated are left out.</p>
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
        </section>
        <section className="chart">
          <h2>Most common genres</h2>
          <Load state={genres}>{(data) => <Bars rows={data.map((r) => ({ label: r.name, value: r.count }))} />}</Load>
        </section>
        <section className="chart">
          <h2>Most common platforms</h2>
          <Load state={platforms}>{(data) => <Bars rows={data.map((r) => ({ label: r.name, value: r.count }))} />}</Load>
        </section>
      </div>
    </>
  );
}