import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import App from "./App";
import { api, ApiError } from "./api";
import { AuthProvider } from "./auth";
import { scoreClass } from "./components/ui";

const GAME = {
  id: 3498,
  slug: "grand-theft-auto-v",
  name: "Grand Theft Auto V",
  released: "2013-09-17T00:00:00",
  rating: 4.47,
  ratings_count: 6825,
  metacritic: 92,
  critic_rating: null,
  playtime: 74,
  background_image: null,
  clip: null,
  steam_appid: null,
  igdb_id: null,
  genres: [{ id: 4, name: "Action", slug: "action" }],
  platforms: [{ id: 4, name: "PC", slug: "pc" }],
  stores: [],
  tags: [],
};

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function mockApi(routes: Record<string, () => Response>) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input).split("?")[0];
      const handler = routes[path];
      return handler ? handler() : json({ detail: "Not Found" }, 404);
    }),
  );
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  );
}

afterEach(() => vi.unstubAllGlobals());

test("score colour bands follow Metacritic's", () => {
  expect([scoreClass(92), scoreClass(75), scoreClass(74), scoreClass(49), scoreClass(null)]).toEqual([
    "good",
    "good",
    "mid",
    "bad",
    "none",
  ]);
});

test("games page lists games from the API", async () => {
  mockApi({
    "/api/games": () => json([GAME]),
    "/api/genres": () => json([{ id: 4, name: "Action", slug: "action" }]),
    "/api/platforms": () => json([]),
  });
  renderAt("/");
  expect(await screen.findByText("Grand Theft Auto V")).toBeInTheDocument();
  expect(screen.getByText("92")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /Grand Theft Auto V/ })).toHaveAttribute("href", "/games/3498");
});

test("game page shows actual and predicted Metacritic", async () => {
  mockApi({
    "/api/games/3498": () => json(GAME),
    "/api/games/3498/predicted-metacritic": () =>
      json({ predicted_metacritic: 85.9, model_name: "m", model_version: "2", game_id: 3498, actual_metacritic: 92 }),
  });
  renderAt("/games/3498");
  expect(await screen.findByRole("heading", { name: "Grand Theft Auto V" })).toBeInTheDocument();
  expect(await screen.findByText(/model v2 · -6.1 vs actual/)).toBeInTheDocument();
});

test("game page explains a missing model", async () => {
  mockApi({
    "/api/games/3498": () => json(GAME),
    "/api/games/3498/predicted-metacritic": () => json({ detail: "No 'champion' version" }, 503),
  });
  renderAt("/games/3498");
  expect(await screen.findByText("No trained model is available yet.")).toBeInTheDocument();
});

test("api errors carry FastAPI's detail message", async () => {
  mockApi({ "/api/auth/login": () => json({ detail: "Invalid credentials" }, 401) });
  await expect(api.login("a@b.c", "x")).rejects.toEqual(new ApiError(401, "Invalid credentials"));
});
