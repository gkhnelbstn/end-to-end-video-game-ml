import { useState, type FormEvent } from "react";

import { api, ApiError } from "../api";
import { Notice, Score } from "../components/ui";
import { useAsync } from "../hooks";
import type { Prediction } from "../types";

function toggle(list: string[], value: string): string[] {
  return list.includes(value) ? list.filter((v) => v !== value) : [...list, value];
}

function ChipPicker({ options, selected, onChange }: { options: string[]; selected: string[]; onChange: (v: string[]) => void }) {
  return (
    <div className="chips">
      {options.map((name) => (
        <button
          type="button"
          key={name}
          className={`chip selectable${selected.includes(name) ? " selected" : ""}`}
          aria-pressed={selected.includes(name)}
          onClick={() => onChange(toggle(selected, name))}
        >
          {name}
        </button>
      ))}
    </div>
  );
}

function ModelCard() {
  const model = useAsync(api.model, []);
  if (model.loading) return <div className="skeleton" style={{ minHeight: 120 }} />;
  if (model.error) {
    const unavailable = model.error instanceof ApiError && model.error.status === 503;
    return <Notice kind={unavailable ? "info" : "error"}>{model.error.message}</Notice>;
  }
  const m = model.data!;
  const mae = m.metrics.test_mae;
  const baseline = m.metrics.baseline_test_mae;
  return (
    <div className="card">
      <h2>Served model</h2>
      <div className="tiles">
        <div className="tile">
          <div className="label">Version</div>
          <div className="value">v{m.model_version}</div>
        </div>
        <div className="tile">
          <div className="label">Test MAE</div>
          <div className="value">{mae?.toFixed(2) ?? "–"}</div>
        </div>
        <div className="tile">
          <div className="label">Baseline MAE</div>
          <div className="value">{baseline?.toFixed(2) ?? "–"}</div>
        </div>
        <div className="tile">
          <div className="label">Test R²</div>
          <div className="value">{m.metrics.test_r2?.toFixed(2) ?? "–"}</div>
        </div>
      </div>
      <p className="subtle" style={{ margin: 0, fontSize: "0.9rem" }}>
        MAE is the average miss in Metacritic points on games the model never saw; the baseline
        always guesses the average score. The model is the version currently promoted to{" "}
        <code>champion</code> in the MLflow registry (<code>{m.model_name}</code>).
      </p>
    </div>
  );
}

export default function Predictor() {
  const genres = useAsync(api.genres, []);
  const platforms = useAsync(() => api.topPlatforms(16), []);
  const [releaseYear, setReleaseYear] = useState(new Date().getFullYear());
  const [chosenGenres, setChosenGenres] = useState<string[]>([]);
  const [chosenPlatforms, setChosenPlatforms] = useState<string[]>(["PC"]);
  const [tags, setTags] = useState("Singleplayer, Story Rich");
  const [result, setResult] = useState<Prediction>();
  const [error, setError] = useState<string>();
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(undefined);
    try {
      setResult(
        await api.predict({
          release_year: releaseYear,
          genres: chosenGenres,
          platforms: chosenPlatforms,
          tags: tags
            .split(",")
            .map((t) => t.trim())
            .filter(Boolean),
        }),
      );
    } catch (err) {
      setResult(undefined);
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Score predictor</h1>
          <p className="subtle" style={{ margin: 0 }}>
            What Metacritic score would a game like this get? Pick its traits and ask the model.
          </p>
        </div>
      </div>

      <div className="detail">
        <form className="card stack" onSubmit={submit}>
          <label className="field" style={{ maxWidth: 160 }}>
            Release year
            <input
              type="number"
              min={1970}
              max={2100}
              value={releaseYear}
              onChange={(e) => setReleaseYear(Number(e.target.value))}
            />
          </label>
          <div className="field">
            Genres
            <ChipPicker
              options={(genres.data ?? []).map((g) => g.name)}
              selected={chosenGenres}
              onChange={setChosenGenres}
            />
          </div>
          <div className="field">
            Platforms
            <ChipPicker
              options={(platforms.data ?? []).map((p) => p.name)}
              selected={chosenPlatforms}
              onChange={setChosenPlatforms}
            />
          </div>
          <label className="field">
            Tags (comma separated, as on Steam or RAWG)
            <input value={tags} onChange={(e) => setTags(e.target.value)} />
          </label>
          <div>
            <button className="primary" type="submit" disabled={busy}>
              {busy ? "Predicting…" : "Predict score"}
            </button>
          </div>
        </form>

        <div>
          <div className="card section" aria-live="polite">
            <h2>Prediction</h2>
            {error && <Notice kind="error">{error}</Notice>}
            {!error && !result && <p className="subtle">Fill in the form and press Predict.</p>}
            {result && (
              <div className="score-block">
                <Score value={result.predicted_metacritic} big />
                <div>
                  <strong>{result.predicted_metacritic.toFixed(1)}</strong>
                  <small>model v{result.model_version}</small>
                </div>
              </div>
            )}
          </div>
          <div className="section">
            <ModelCard />
          </div>
        </div>
      </div>
    </>
  );
}
