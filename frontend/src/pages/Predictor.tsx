import { useState, type FormEvent } from "react";

import { api } from "../api";
import { ErrorNotice, HowEstimatesWork, RECEPTION_LABEL, ReceptionStrip } from "../components/ui";
import { useAsync } from "../hooks";
import type { GameFeatures, Prediction } from "../types";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

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
  year: new Date().getFullYear() + 1,
  month: null,
  esrb: "",
  genres: [],
  platforms: [],
  stores: [],
  tags: "",
};

const EXAMPLES: { label: string; form: Form }[] = [
  {
    label: "A big-budget RPG sequel",
    form: {
      name: "Starfall Chronicles III",
      year: new Date().getFullYear() + 1,
      month: 11,
      esrb: "Mature",
      genres: ["RPG", "Action"],
      platforms: ["PC", "PlayStation 5", "Xbox Series S/X"],
      stores: ["Steam", "PlayStation Store"],
      tags: "Singleplayer, Story Rich, Open World, Atmospheric",
    },
  },
  {
    label: "A small mobile puzzler",
    form: {
      name: "Block Party",
      year: new Date().getFullYear() + 1,
      month: 3,
      esrb: "Everyone",
      genres: ["Casual", "Puzzle"],
      platforms: ["iOS", "Android"],
      stores: ["App Store", "Google Play"],
      tags: "Singleplayer, 2D",
    },
  },
];

function toggle(list: string[], value: string): string[] {
  return list.includes(value) ? list.filter((v) => v !== value) : [...list, value];
}

function Picker({
  legend,
  options,
  selected,
  onChange,
}: {
  legend: string;
  options: string[] | undefined;
  selected: string[];
  onChange: (v: string[]) => void;
}) {
  return (
    <fieldset className="picker">
      <legend>{legend}</legend>
      {options ? (
        <div className="picker-options">
          {options.map((name) => (
            <button
              type="button"
              key={name}
              className={`rail-chip${selected.includes(name) ? " on" : ""}`}
              aria-pressed={selected.includes(name)}
              onClick={() => onChange(toggle(selected, name))}
            >
              {name}
            </button>
          ))}
        </div>
      ) : (
        <div className="skeleton" style={{ minHeight: 34 }} />
      )}
    </fieldset>
  );
}

export default function Predictor() {
  const genres = useAsync(api.genres, []);
  const platforms = useAsync(() => api.topPlatforms(18), []);
  const stores = useAsync(() => api.topStores(10), []);
  const esrb = useAsync(api.esrbRatings, []);
  const [form, setForm] = useState<Form>(EMPTY);
  const [result, setResult] = useState<Prediction>();
  const [error, setError] = useState<Error>();
  const [busy, setBusy] = useState(false);

  const set = <K extends keyof Form>(key: K, value: Form[K]) => setForm((f) => ({ ...f, [key]: value }));
  const empty = form.genres.length === 0 && form.platforms.length === 0 && !form.tags.trim();

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

  const e = result?.expected;
  return (
    <div className="estimate">
      <header className="page-head">
        <h1>Estimate a game that isn't out yet</h1>
        <p>
          Describe it the way its store page would before launch. You'll get the reception critics are likely to give it,
          judged against games that already have a score.
        </p>
        <p className="examples">
          Or start from an example:{" "}
          {EXAMPLES.map((ex, i) => (
            <span key={ex.label}>
              {i > 0 && ", "}
              <button type="button" className="link-button" onClick={() => (setForm(ex.form), setResult(undefined))}>
                {ex.label.toLowerCase()}
              </button>
            </span>
          ))}
        </p>
      </header>

      <div className="estimate-layout">
        <form className="estimate-form" onSubmit={submit}>
          <div className="field-row">
            <label className="field wide">
              Working title
              <input value={form.name} placeholder="Sequels and remasters are read from the title" onChange={(ev) => set("name", ev.target.value)} />
            </label>
          </div>
          <div className="field-row">
            <label className="field">
              Release year
              <input type="number" min={1970} max={2100} value={form.year} onChange={(ev) => set("year", Number(ev.target.value))} />
            </label>
            <label className="field">
              Month
              <select value={form.month ?? ""} onChange={(ev) => set("month", ev.target.value ? Number(ev.target.value) : null)}>
                <option value="">Not decided</option>
                {MONTHS.map((m, i) => (
                  <option key={m} value={i + 1}>
                    {m}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              ESRB rating
              <select value={form.esrb} onChange={(ev) => set("esrb", ev.target.value)}>
                <option value="">Not rated yet</option>
                {esrb.data?.map((r) => (
                  <option key={r.name} value={r.name}>
                    {r.name}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <Picker legend="Genres" options={genres.data?.map((g) => g.name)} selected={form.genres} onChange={(v) => set("genres", v)} />
          <Picker legend="Platforms" options={platforms.data?.map((p) => p.name)} selected={form.platforms} onChange={(v) => set("platforms", v)} />
          <Picker legend="Stores" options={stores.data?.map((s) => s.name)} selected={form.stores} onChange={(v) => set("stores", v)} />
          <label className="field">
            Tags, as you'd list them on Steam
            <input value={form.tags} placeholder="Singleplayer, Story Rich, Open World" onChange={(ev) => set("tags", ev.target.value)} />
          </label>
          <div className="form-actions">
            <button className="button" type="submit" disabled={busy || empty}>
              {busy ? "Estimating…" : "Estimate reception"}
            </button>
            <button type="button" className="link-button" onClick={() => (setForm(EMPTY), setResult(undefined))}>
              Start over
            </button>
            {empty && <span className="subtle small">Pick a genre, a platform or a tag first.</span>}
          </div>
        </form>

        <aside className="estimate-result" aria-live="polite">
          {error && <ErrorNotice error={error} />}
          {!error && !e && (
            <div className="verdict placeholder-verdict">
              <p className="verdict-word">No estimate yet</p>
              <ReceptionStrip scale />
              <p className="verdict-aside">The result appears here, on the same scale critics use.</p>
            </div>
          )}
          {e && (
            <section className="verdict">
              <div className="verdict-head">
                <span className={`critic expected ${e.reception} lg`} aria-hidden>
                  ≈{Math.round(e.score)}
                </span>
                <div>
                  <p className="verdict-word">{RECEPTION_LABEL[e.reception]}</p>
                  <p className="verdict-source">
                    likely {e.low}–{e.high}
                  </p>
                </div>
              </div>
              <ReceptionStrip expected={e} scale />
              <p className="verdict-aside">
                {form.name.trim() ? `${form.name.trim()} would` : "A game like this would"} most likely land between {e.low} and{" "}
                {e.high}.
              </p>
            </section>
          )}
          <HowEstimatesWork tryLink={false} />
        </aside>
      </div>
    </div>
  );
}
