import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import { api, ApiError, isUnreachable } from "../api";
import { useAsync } from "../hooks";
import type { Expectation, Game, Reception } from "../types";

/** The UI is in English, so numbers are too (no "1.330" for 1,330 on a Turkish browser). */
const numberFormat = new Intl.NumberFormat("en-US");
export const fmt = (n: number) => numberFormat.format(n);

/** Metacritic's own wording for its score bands. */
export const RECEPTION_LABEL: Record<Reception, string> = {
  acclaim: "Universal acclaim",
  favourable: "Generally favourable",
  mixed: "Mixed or average",
  unfavourable: "Generally unfavourable",
};

export function receptionOf(score: number): Reception {
  if (score >= 90) return "acclaim";
  if (score >= 75) return "favourable";
  if (score >= 50) return "mixed";
  return "unfavourable";
}

/** A critics' score in the colour of its band. */
export function CriticScore({ value, size = "md" }: { value: number; size?: "sm" | "md" | "lg" }) {
  return (
    <span className={`critic ${receptionOf(value)} ${size}`} title={`Metacritic ${value}`}>
      {Math.round(value)}
    </span>
  );
}

const BANDS: { from: number; to: number; reception: Reception }[] = [
  { from: 0, to: 50, reception: "unfavourable" },
  { from: 50, to: 75, reception: "mixed" },
  { from: 75, to: 90, reception: "favourable" },
  { from: 90, to: 100, reception: "acclaim" },
];

/**
 * The 0-100 reception strip used everywhere a score appears. A critics' score is a solid
 * notch; the model's estimate is a hatched range, so the two never read as the same thing.
 */
export function ReceptionStrip({
  actual,
  expected,
  scale = false,
}: {
  actual?: number | null;
  expected?: Pick<Expectation, "low" | "high"> | null;
  scale?: boolean;
}) {
  const at = (v: number) => `${Math.min(100, Math.max(0, v))}%`;
  return (
    <div className="strip" aria-hidden>
      <div className="strip-track">
        {BANDS.map((b) => (
          <span key={b.reception} className={`strip-band ${b.reception}`} style={{ left: at(b.from), width: `${b.to - b.from}%` }} />
        ))}
        {expected && (
          <span className="strip-range" style={{ left: at(expected.low), width: `${expected.high - expected.low}%` }} />
        )}
        {actual != null && <span className={`strip-notch ${receptionOf(actual)}`} style={{ left: at(actual) }} />}
      </div>
      {scale && (
        <div className="strip-scale">
          {[0, 50, 75, 90, 100].map((v) => (
            <span key={v} style={{ left: at(v) }}>
              {v}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

/** One-line version of an estimate for cards and lists. */
export function ExpectedLine({ expected }: { expected: Expectation }) {
  return (
    <span className={`expected-line ${expected.reception}`}>
      <span className="expected-word">{RECEPTION_LABEL[expected.reception]}</span>
      <span className="expected-range">
        likely {expected.low}–{expected.high}
      </span>
    </span>
  );
}

/** What the estimates are, in plain words, with the measured accuracy behind them. */
export function HowEstimatesWork({ open = false, tryLink = true }: { open?: boolean; tryLink?: boolean }) {
  const model = useAsync(api.model, []);
  const m = model.data?.metrics;
  return (
    <details className="how" open={open}>
      <summary>How estimates work</summary>
      <p>
        Estimates come from a model trained on games that already have a Metacritic score. It only looks at what is
        known before launch: the title, release date, ESRB rating, genres, platforms, stores and tags. Reviews and
        sales are not part of it.
      </p>
      {m?.test_mae !== undefined && (
        <p>
          On games it never saw during training, it misses the real score by{" "}
          <strong>{m.test_mae.toFixed(1)} points</strong> on average
          {m.baseline_test_mae !== undefined && (
            <>
              ; guessing the average score every time would miss by {m.baseline_test_mae.toFixed(1)}
            </>
          )}
          . Every range shown here is the estimate give or take that average miss.
        </p>
      )}
      <p>
        It is weakest at the extremes: true classics and true flops are rarer than everything in between, so their
        estimates lean towards the middle.
      </p>
      <p className="subtle">
        {tryLink && (
          <>
            <Link to="/estimate">Try it on a game idea of your own</Link>
            {model.data && " · "}
          </>
        )}
        {model.data && `Model version ${model.data.model_version}`}
      </p>
    </details>
  );
}

export function year(released: string | null): string {
  return released ? released.slice(0, 4) : "TBA";
}

export function releaseDate(released: string | null, style: "long" | "short" = "long"): string {
  if (!released) return "Release date not announced";
  return new Date(released).toLocaleDateString("en-US", {
    year: "numeric",
    month: style === "long" ? "long" : "short",
    day: "numeric",
  });
}

export function Cover({ game, className = "cover" }: { game: Pick<Game, "background_image" | "name">; className?: string }) {
  // Image hosts come from the data sources and can disappear (RAWG's media CDN may follow its API).
  const [failed, setFailed] = useState(false);
  if (!game.background_image || failed) {
    return (
      <div className={`${className} placeholder`} aria-hidden>
        <span>{game.name}</span>
      </div>
    );
  }
  return <img className={className} src={game.background_image} alt="" loading="lazy" onError={() => setFailed(true)} />;
}

export function Notice({ kind = "info", children }: { kind?: "info" | "error" | "success"; children: ReactNode }) {
  return (
    <div className={`notice ${kind === "info" ? "" : kind}`} role={kind === "error" ? "alert" : "status"}>
      {children}
    </div>
  );
}

/** An error from a loader, with a Retry button. A 503 "no model yet" is shown as info. */
export function ErrorNotice({ error, onRetry, prefix }: { error: Error; onRetry?: () => void; prefix?: string }) {
  const noModel = error instanceof ApiError && error.status === 503 && !isUnreachable(error);
  return (
    <div className={`notice ${noModel ? "" : "error"}`} role={noModel ? "status" : "alert"}>
      <span>
        {prefix && !isUnreachable(error) ? `${prefix}: ` : ""}
        {error.message}
      </span>
      {onRetry && (
        <button className="link-button" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  );
}

export function Bars({
  rows,
  format = fmt,
  max: fixedMax,
}: {
  rows: { label: string; value: number }[];
  format?: (v: number) => string;
  max?: number;
}) {
  const max = fixedMax ?? Math.max(...rows.map((r) => r.value), 1);
  return (
    <div className="bars">
      {rows.map((row) => (
        <div className="bar-row" key={row.label}>
          <span className="bar-label" title={row.label}>
            {row.label}
          </span>
          <div className="bar-track">
            <div className="bar-fill" style={{ width: `${(row.value / max) * 100}%` }} />
          </div>
          <span className="bar-value">{format(row.value)}</span>
        </div>
      ))}
    </div>
  );
}

export function Figure({ label, value, hint }: { label: string; value: ReactNode; hint?: ReactNode }) {
  return (
    <div className="figure">
      <div className="figure-value">{value}</div>
      <div className="figure-label">{label}</div>
      {hint && <div className="figure-hint">{hint}</div>}
    </div>
  );
}
