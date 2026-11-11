import { useState, type FormEvent } from "react";

import { api } from "../api";
import { ErrorNotice, Score, ScoreScale, scoreClass, Stat } from "../components/ui";
import { useAsync } from "../hooks";
import type { GameFeatures, Prediction } from "../types";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const VERDICT: Record<string, string> = {
  good: "Generally favourable",
  mid: "Mixed or average",
  bad: "Generally unfavourable",
};

interface Form {
  name: string;
  year: number;
  month: number | null;
  esrb: string;
  genres: string[];
  platforms: string[];
  stores: string[];
  tags: string;
}

const EMPTY: Form = {
  name: "",
  year: new Date().getFullYear(),
  month: null,
  esrb: "",
  genres: [],
  platforms: ["PC"],
  stores: [],
  tags: "Singleplayer",
};

const EXAMPLES: { label: string; form: Form }[] = [
  {
    label: "Big console RPG sequel",
    form: {
      name: "Starfall Chronicles III",
      year: 2025,
      month: 11,
      esrb: "Mature",
      genres: ["RPG", "Action"],
      platforms: ["PC", "PlayStation 5", "Xbox Series S/X"],
      stores: ["Steam", "PlayStation Store"],
      tags: "Singleplayer, Story Rich, Open World, Atmospheric",
    },
  },
  {
    label: "Small casual puzzle game",
    form: {
      name: "Block Party",
      year: 2025,
      month: 3,
      esrb: "Everyone",
      genres: ["Casual", "Puzzle"],
      platforms: ["PC", "iOS", "Android"],
      stores: ["Steam"],
      tags: "Singleplayer, 2D",
    },
  },
];

function toggle(list: string[], value: string): string[] {
  return list.includes(value) ? list.filter((v) => v !== value) : [...list, value];
}

function ChipPicker({ options, selected, onChange }: { options: string[]; selected: string[]; onChange: (v: string[]) => void }) {
  if (options.length === 0) return <div className="skeleton" style={{ minHeight: 32 }} />;
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

function ModelPanel() {
  const model = useAsync(api.model, []);
  if (model.loading) return <div className="skeleton" style={{ minHeight: 140 }} />;
  if (model.error) return <ErrorNotice error={model.error} onRetry={model.reload} />;
  const m = model.data!;
  const mae = m.metrics.test_mae;
  const baseline = m.metrics.baseline_test_mae;
  const gain = mae !== undefined && baseline ? (1 - mae / baseline) * 100 : null;
  return (
    <div className="panel">
      <h2>About the model</h2>
      <div className="stats-row">
        <Stat label="Version" value={`v${m.model_version}`} />
        <Stat label="Avg. miss (MAE)" value={mae?.toFixed(1) ?? "–"} hint="points, unseen games" />
        <Stat
          label="Always-average guess"
          value={baseline?.toFixed(1) ?? "–"}
          hint={gain !== null ? `model is ${gain.toFixed(0)}% closer` : undefined}
        />
        <Stat label="R²" value={m.metrics.test_r2?.toFixed(2) ?? "–"} />
      </div>
      <p className="subtle small">
        Scores are measured on a held-out fifth of the games the model never trained on. It is the version currently
        promoted to <code>champion</code> in the MLflow registry (<code>{m.model_name}</code>). It only uses what is
        known before release, so treat a prediction as a rough prior, not a review.
      </p>
    </div>
  );
}

export default function Predictor() {
  const genres = useAsync(api.genres, []);
  const platforms = useAsync(() => api.topPlatforms(18), []);
  const stores = useAsync(() => api.topStores(10), []);
  const esrb = useAsync(api.esrbRatings, []);
  const model = useAsync(api.model, []);
  const [form, setForm] = useState<Form>(EMPTY);
  const [result, setResult] = useState<Prediction>();
  const [error, setError] = useState<Error>();
  const [busy, setBusy] = useState(false);

  const set = <K extends keyof Form>(key: K, value: Form[K]) => setForm((f) => ({ ...f, [key]: value }));

  const submit = async (e?: FormEvent) => {
    e?.preventDefault();
    setBusy(true);
    setError(undefined);
    const features: GameFeatures = {
      name: form.name.trim(),
      release_year: form.year || null,
      release_month: form.month,
      esrb_rating: form.esrb || null,
      genres: form.genres,
      platforms: form.platforms,
      stores: form.stores,
      tags: form.tags
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean),
    };
    try {
      setResult(await api.predict(features));
    } catch (err) {
      setResult(undefined);
      setError(err as Error);
    } finally {
      setBusy(false);
    }
  };

  const mae = model.data?.metrics.test_mae;
  const band = result ? scoreClass(result.predicted_metacritic) : "none";

  return (
    <>
      <section className="page-intro">
        <p className="eyebrow">Score predictor</p>
        <h1>What would critics give a game like this?</h1>
        <p className="lede">
          Describe a game the way a store page would before launch. The model estimates its Metacritic score from
          those traits alone.
        </p>
        <div className="chips">
          <span className="subtle small">Try:</span>
          {EXAMPLES.map((ex) => (
            <button key={ex.label} type="button" className="chip selectable" onClick={() => setForm(ex.form)}>
              {ex.label}
            </button>
          ))}
        </div>
      </section>

      <div className="detail">
        <form className="panel form" onSubmit={submit}>
          <div className="form-row">
            <label className="field grow">
              <span>
                Title <span className="opt">optional</span>
              </span>
              <input value={form.name} placeholder="e.g. Starfall Chronicles III" onChange={(e) => set("name", e.target.value)} />
            </label>
          </div>
          <div className="form-row">
            <label className="field">
              Release year
              <input
                type="number"
                min={1970}
                max={2100}
                value={form.year}
                onChange={(e) => set("year", Number(e.target.value))}
              />
            </label>
            <label className="field">
              Month
              <select value={form.month ?? ""} onChange={(e) => set("month", e.target.value ? Number(e.target.value) : null)}>
                <option value="">Unknown</option>
                {MONTHS.map((m, i) => (
                  <option key={m} value={i + 1}>
                    {m}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              ESRB rating
              <select value={form.esrb} onChange={(e) => set("esrb", e.target.value)}>
                <option value="">Unknown</option>
                {esrb.data?.map((r) => (
                  <option key={r.name} value={r.name}>
                    {r.name}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <fieldset className="field">
            <legend>Genres</legend>
            <ChipPicker options={(genres.data ?? []).map((g) => g.name)} selected={form.genres} onChange={(v) => set("genres", v)} />
          </fieldset>
          <fieldset className="field">
            <legend>Platforms</legend>
            <ChipPicker
              options={(platforms.data ?? []).map((p) => p.name)}
              selected={form.platforms}
              onChange={(v) => set("platforms", v)}
            />
          </fieldset>
          <fieldset className="field">
            <legend>Stores</legend>
            <ChipPicker options={(stores.data ?? []).map((s) => s.name)} selected={form.stores} onChange={(v) => set("stores", v)} />
          </fieldset>
          <label className="field">
            <span>
              Tags <span className="opt">comma separated, as on Steam</span>
            </span>
            <input value={form.tags} onChange={(e) => set("tags", e.target.value)} />
          </label>
          <div className="form-actions">
            <button className="primary" type="submit" disabled={busy}>
              {busy ? "Predicting…" : "Predict score"}
            </button>
            <button type="button" className="ghost" onClick={() => (setForm(EMPTY), setResult(undefined))}>
              Reset
            </button>
          </div>
        </form>

        <aside className="stack-lg sticky">
          <div className={`panel result ${band}`} aria-live="polite">
            <h2>Prediction</h2>
            {error && <ErrorNotice error={error} />}
            {!error && !result && <p className="subtle">Pick some traits and press Predict score.</p>}
            {result && (
              <>
                <div className="result-main">
                  <Score value={result.predicted_metacritic} size="lg" />
                  <div>
                    <strong className="result-verdict">{VERDICT[band]}</strong>
                    <small>
                      {result.predicted_metacritic.toFixed(1)}
                      {mae !== undefined && ` ± ${mae.toFixed(1)}`} · model v{result.model_version}
                    </small>
                  </div>
                </div>
                <ScoreScale predicted={result.predicted_metacritic} spread={mae} />
              </>
            )}
          </div>
          <ModelPanel />
        </aside>
      </div>
    </>
  );
}
