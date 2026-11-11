export interface Lookup {
  id: number;
  name: string;
  slug: string;
}

export interface Game {
  id: number;
  slug: string;
  name: string;
  released: string | null;
  rating: number | null;
  ratings_count: number | null;
  metacritic: number | null;
  critic_rating: number | null;
  playtime: number | null;
  background_image: string | null;
  clip: string | null;
  steam_appid: number | null;
  igdb_id: number | null;
  genres: Lookup[];
  platforms: Lookup[];
  stores: Lookup[];
  tags: Lookup[];
}

export interface User {
  id: number;
  email: string;
}

export interface Prediction {
  predicted_metacritic: number;
  model_name: string;
  model_version: string;
  game_id: number | null;
  actual_metacritic: number | null;
}

export interface ModelInfo {
  model_name: string;
  model_version: string;
  run_id: string | null;
  metrics: Record<string, number>;
  tracking_uri: string;
}

export interface GameFeatures {
  release_year: number | null;
  genres: string[];
  platforms: string[];
  tags: string[];
}

export interface GameQuery {
  search?: string;
  genre?: string;
  platform?: string;
  sort_by?: "name" | "released" | "rating" | "metacritic";
  sort_order?: "asc" | "desc";
  skip?: number;
  limit?: number;
}

export interface NameCount {
  name: string;
  count: number;
}
