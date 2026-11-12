import { useState, type ReactNode } from "react";

import { ApiError, isUnreachable } from "../api";
import type { Game } from "../types";

/** The UI is in English, so numbers are too (no "1.330" for 1,330 on a Turkish browser). */
const numberFormat = new Intl.NumberFormat("en-US");
export const fmt = (n: number) => numberFormat.format(n);

/** Metacritic's colour bands: 75+ favourable, 50-74 mixed, below 50 unfavourable. */
export function scoreClass(score: number | null | undefined): string {
  if (score === null || score === undefined) return "none";
  if (score >= 75) return "good";
  if (score >= 50) return "mid";
  return "bad";
}

export function Score({
  value,
  size = "md",
  title,
}: {
  value: number | null | undefined;
  size?: "sm" | "md" | "lg";
  title?: string;
}) {
  const shown = value === null || value === undefined ? "–" : Math.round(value);
  return (
    <span className={`score ${scoreClass(value)} ${size}`} title={title}>
      {shown}
    </span>
  );
}

export function year(released: string | null): string {
  return released ? released.slice(0, 4) : "TBA";
}

export function Cover({ game, className = "cover" }: { game: Pick<Game, "background_image" | "name">; className?: string }) {
  // Image hosts come from the data sources and can disappear (RAWG's media CDN may follow its API).
  const [failed, setFailed] = useState(false);
  if (!game.background_image || failed) {
    return (
      <div className={`${className} placeholder`} aria-hidden>
        <span>{initials(game.name)}</span>
      </div>
    );
  }
  return <img className={className} src={game.background_image} alt="" loading="lazy" onError={() => setFailed(true)} />;
}

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter((w) => /^[A-Za-z0-9]/.test(w))
    .slice(0, 2)
    .map((w) => w[0].toUpperCase())
    .join("");
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
        <button className="ghost small" onClick={onRetry}>
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

export function Stat({ label, value, hint }: { label: string; value: ReactNode; hint?: ReactNode }) {
  return (
    <div className="stat">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {hint && <div className="stat-hint">{hint}</div>}
    </div>
  );
}

/**
 * Where scores sit on the 0-100 Metacritic scale, coloured by its bands.
 * `actual` and `predicted` are drawn as markers; `spread` shades predicted ± spread.
 */
export function ScoreScale({
  actual,
  predicted,
  spread,
}: {
  actual?: number | null;
  predicted?: number | null;
  spread?: number | null;
}) {
  const at = (v: number) => `${Math.min(100, Math.max(0, v))}%`;
  return (
    <div className="scale" aria-hidden>
      <div className="scale-track">
        <span className="band bad" style={{ width: "50%" }} />
        <span className="band mid" style={{ width: "25%" }} />
        <span className="band good" style={{ width: "25%" }} />
        {predicted != null && spread != null && (
          <span
            className="scale-spread"
            style={{ left: at(predicted - spread), width: `${Math.min(100, predicted + spread) - Math.max(0, predicted - spread)}%` }}
          />
        )}
        {actual != null && <span className="marker actual" style={{ left: at(actual) }} />}
        {predicted != null && <span className="marker predicted" style={{ left: at(predicted) }} />}
      </div>
      <div className="scale-axis">
        <span>0</span>
        <span style={{ left: "50%" }}>50</span>
        <span style={{ left: "75%" }}>75</span>
        <span>100</span>
      </div>
    </div>
  );
}
