import type {
  Game,
  GameFeatures,
  GameQuery,
  Lookup,
  ModelInfo,
  NameCount,
  Prediction,
  Summary,
  User,
} from "./types";

/** An error response from the API, with FastAPI's `detail` message when there is one. */
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

export const UNREACHABLE =
  "Can't reach the API. Make sure the backend is running (docker compose up), then try again.";

/** True when the request never got an answer from the backend. */
export function isUnreachable(error: unknown): boolean {
  return error instanceof ApiError && error.message === UNREACHABLE;
}

function detailMessage(body: unknown, fallback: string): string {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    // Validation errors: [{loc, msg}, ...]
    if (Array.isArray(detail)) return detail.map((d) => d?.msg ?? String(d)).join("; ");
  }
  return fallback;
}

let accessToken: string | undefined;

/** Called by the auth provider whenever Rauthy issues, renews or drops the token. */
export function setAccessToken(token: string | undefined) {
  accessToken = token;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body) headers.set("Content-Type", "application/json");
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  let response: Response;
  try {
    response = await fetch(path, { ...init, headers });
  } catch {
    // fetch only rejects when no response arrived at all (server down, network gone).
    throw new ApiError(0, UNREACHABLE);
  }
  const body = response.headers.get("content-type")?.includes("json")
    ? await response.json().catch(() => null)
    : null;
  if (response.status === 502 || response.status === 503 || response.status === 504) {
    // nginx or the Vite proxy answered, but the backend behind it did not.
    if (!body) throw new ApiError(response.status, UNREACHABLE);
  }
  if (!response.ok) {
    throw new ApiError(response.status, detailMessage(body, `${response.status} ${response.statusText}`));
  }
  return body as T;
}

function query(params: object): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}

export const api = {
  games: (q: GameQuery) => request<Game[]>(`/api/games${query(q)}`),
  game: (id: number) => request<Game>(`/api/games/${id}`),
  genres: () => request<Lookup[]>("/api/genres"),
  platforms: () => request<Lookup[]>("/api/platforms"),

  predictedMetacritic: (id: number) => request<Prediction>(`/api/games/${id}/predicted-metacritic`),
  predict: (features: GameFeatures) =>
    request<Prediction>("/api/predictions/metacritic", {
      method: "POST",
      body: JSON.stringify(features),
    }),
  model: () => request<ModelInfo>("/api/ml/model"),

  gamesPerYear: () => request<{ year: number; count: number }[]>("/api/stats/games-per-year"),
  topGenres: (limit = 12) => request<NameCount[]>(`/api/stats/top-genres?limit=${limit}`),
  topPlatforms: (limit = 12) => request<NameCount[]>(`/api/stats/top-platforms?limit=${limit}`),
  topStores: (limit = 12) => request<NameCount[]>(`/api/stats/top-stores?limit=${limit}`),
  esrbRatings: () => request<NameCount[]>("/api/stats/esrb-ratings"),
  avgRatingByGenre: () =>
    request<{ genre: string; avg_rating: number }[]>("/api/stats/avg-rating-by-genre"),
  summary: () => request<Summary>("/api/stats/summary"),
  metacriticDistribution: () =>
    request<{ band: number; count: number }[]>("/api/stats/metacritic-distribution"),

  me: () => request<User>("/api/me"),
  favorites: () => request<Game[]>("/api/me/favorites"),
  addFavorite: (gameId: number) => request<null>(`/api/me/favorites/${gameId}`, { method: "PUT" }),
  removeFavorite: (gameId: number) =>
    request<null>(`/api/me/favorites/${gameId}`, { method: "DELETE" }),
};
