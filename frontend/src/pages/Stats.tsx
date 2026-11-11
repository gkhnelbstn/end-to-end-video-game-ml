import { api } from "../api";
import { Bars, Notice } from "../components/ui";
import { useAsync } from "../hooks";

function GamesPerYear() {
  const data = useAsync(api.gamesPerYear, []);
  if (data.error) return <Notice kind="error">{data.error.message}</Notice>;
  if (!data.data) return <div className="skeleton" style={{ minHeight: 180 }} />;
  const rows = data.data.filter((r) => r.year >= 1990);
  if (rows.length === 0) return <Notice>No release dates yet.</Notice>;
  const max = Math.max(...rows.map((r) => r.count));
  return (
    <>
      <div className="columns" role="img" aria-label="Games released per year">
        {rows.map((r) => (
          <div
            key={r.year}
            className="column"
            style={{ height: `${(r.count / max) * 100}%` }}
            title={`${r.year}: ${r.count.toLocaleString()} games`}
          />
        ))}
      </div>
      <div className="axis">
        <span>{rows[0].year}</span>
        <span>{rows[rows.length - 1].year}</span>
      </div>
    </>
  );
}

export default function Stats() {
  const genres = useAsync(() => api.topGenres(12), []);
  const platforms = useAsync(() => api.topPlatforms(12), []);
  const ratings = useAsync(api.avgRatingByGenre, []);

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Statistics</h1>
          <p className="subtle" style={{ margin: 0 }}>
            Computed live from the database.
          </p>
        </div>
      </div>

      <div className="card section">
        <h2>Games released per year</h2>
        <GamesPerYear />
      </div>

      <div className="grid-2 section" style={{ marginTop: "1rem" }}>
        <div className="card">
          <h2>Top genres</h2>
          {genres.error && <Notice kind="error">{genres.error.message}</Notice>}
          {genres.data && <Bars rows={genres.data.map((r) => ({ label: r.name, value: r.count }))} />}
        </div>
        <div className="card">
          <h2>Top platforms</h2>
          {platforms.error && <Notice kind="error">{platforms.error.message}</Notice>}
          {platforms.data && <Bars rows={platforms.data.map((r) => ({ label: r.name, value: r.count }))} />}
        </div>
        <div className="card">
          <h2>Average user rating by genre</h2>
          {ratings.error && <Notice kind="error">{ratings.error.message}</Notice>}
          {ratings.data && (
            <Bars
              rows={[...ratings.data]
                .sort((a, b) => b.avg_rating - a.avg_rating)
                .map((r) => ({ label: r.genre, value: r.avg_rating }))}
              format={(v) => v.toFixed(2)}
            />
          )}
        </div>
      </div>
    </>
  );
}
