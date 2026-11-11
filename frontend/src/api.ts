import type {
  Game,
  GameFeatures,
  GameQuery,
  Lookup,
  ModelInfo,
  NameCount,
  Prediction,
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

function detailMessage(body: unknown, fallback: string): string {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    // Validation errors: [{loc, msg}, ...]
    if (Array.isArray(detail)) return detail.map((d) => d?.msg ?? String(d)).join("; ");
  }
  return fallback;
}

async function request<T>(path: string, init: RequestInit & { userId?: number } = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body) headers.set("Content-Type", "application/json");
  if (init.userId !== undefined) headers.set("X-User-Id", String(init.userId));
  const response = await fetch(path, { ...init, headers });
  const body = response.headers.get("content-type")?.includes("json")
    ? await response.json()
    : null;
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
  avgRatingByGenre: () =>
    request<{ genre: string; avg_rating: number }[]>("/api/stats/avg-rating-by-genre"),

  register: (email: string, password: string) =>
    request<User>("/api/users", { method: "POST", body: JSON.stringify({ email, password }) }),
  login: (email: string, password: string) =>
    request<User>("/api/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  favorites: (userId: number) => request<Game[]>(`/api/users/${userId}/favorites`),
  addFavorite: (userId: number, gameId: number) =>
    request<unknown>(`/api/users/${userId}/favorites/${gameId}`, { method: "POST", userId }),
  removeFavorite: (userId: number, gameId: number) =>
    request<unknown>(`/api/users/${userId}/favorites/${gameId}`, { method: "DELETE", userId }),
};
