import { useState, type ReactNode } from "react";

import type { Game } from "../types";

/** Metacritic's colour bands: 75+ favourable, 50-74 mixed, below 50 unfavourable. */
export function scoreClass(score: number | null | undefined): string {
  if (score === null || score === undefined) return "none";
  if (score >= 75) return "good";
  if (score >= 50) return "mid";
  return "bad";
}

export function Score({ value, big = false, title }: { value: number | null | undefined; big?: boolean; title?: string }) {
  const shown = value === null || value === undefined ? "–" : Math.round(value);
  return (
    <span className={`score ${scoreClass(value)}${big ? " big" : ""}`} title={title}>
      {shown}
    </span>
  );
}

export function year(released: string | null): string {
  return released ? released.slice(0, 4) : "TBA";
}

export function Cover({ game }: { game: Pick<Game, "background_image" | "name"> }) {
  // Image hosts come from the data sources and can disappear (RAWG's media CDN may follow its API).
  const [failed, setFailed] = useState(false);
  if (!game.background_image || failed) {
    return <div className="cover placeholder">No image</div>;
  }
  return (
    <img className="cover" src={game.background_image} alt="" loading="lazy" onError={() => setFailed(true)} />
  );
}

export function Notice({ kind = "info", children }: { kind?: "info" | "error" | "success"; children: ReactNode }) {
  return (
    <div className={`notice ${kind === "info" ? "" : kind}`} role={kind === "error" ? "alert" : "status"}>
      {children}
    </div>
  );
}

export function Bars({ rows, format = (v) => v.toLocaleString() }: { rows: { label: string; value: number }[]; format?: (v: number) => string }) {
  const max = Math.max(...rows.map((r) => r.value), 1);
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
