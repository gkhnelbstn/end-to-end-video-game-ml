import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import App from "./App";
import { api, ApiError, isUnreachable } from "./api";
import { AuthProvider } from "./auth";
import { receptionOf } from "./components/ui";

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
  esrb_rating: "Mature",
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

test("reception bands follow Metacritic's wording", () => {
  expect([90, 89, 75, 74, 50, 49].map(receptionOf)).toEqual([
    "acclaim",
    "favourable",
    "favourable",
    "mixed",
    "mixed",
    "unfavourable",
  ]);
});

test("games page lists games from the API", async () => {
  mockApi({
    "/api/games": () => json([GAME]),
    "/api/genres": () => json([{ id: 4, name: "Action", slug: "action" }]),
    "/api/platforms": () => json([]),
  });
  renderAt("/");
  // The same game shows up in the "Best of" shelf and in the full list.
  expect((await screen.findAllByText("Grand Theft Auto V")).length).toBeGreaterThan(0);
  expect(screen.getAllByText("92")[0]).toBeInTheDocument();
  expect(screen.getAllByRole("link", { name: /Grand Theft Auto V/ })[0]).toHaveAttribute("href", "/games/3498");
});

test("unreviewed games show the expected reception, not a score", async () => {
  const upcoming = {
    ...GAME,
    id: 7,
    name: "Starfall III",
    metacritic: null,
    released: "2099-03-01T00:00:00",
    expected: { score: 83.4, low: 76, high: 91, reception: "favourable" },
  };
  mockApi({ "/api/games": () => json([upcoming]), "/api/genres": () => json([]), "/api/platforms": () => json([]) });
  renderAt("/");
  expect((await screen.findAllByText("Generally favourable")).length).toBeGreaterThan(0);
  expect(screen.getAllByText("likely 76–91")[0]).toBeInTheDocument();
  expect(screen.queryByText("83")).not.toBeInTheDocument();
});

const PREDICTION = {
  predicted_metacritic: 85.9,
  expected: { score: 85.9, low: 78, high: 94, reception: "favourable" },
  model_name: "m",
  model_version: "2",
  game_id: 3498,
  actual_metacritic: 92,
};

test("game page compares the real score with what was expected", async () => {
  mockApi({ "/api/games/3498": () => json(GAME), "/api/games/3498/predicted-metacritic": () => json(PREDICTION) });
  renderAt("/games/3498");
  expect(await screen.findByRole("heading", { name: "Grand Theft Auto V" })).toBeInTheDocument();
  expect(screen.getByText("Universal acclaim")).toBeInTheDocument();
  expect(await screen.findByText(/we'd have put it at 78–94, and it landed inside that range/)).toBeInTheDocument();
});

test("an unreviewed game without a model says so plainly", async () => {
  mockApi({
    "/api/games/3498": () => json({ ...GAME, metacritic: null }),
    "/api/games/3498/predicted-metacritic": () => json({ detail: "No 'champion' version" }, 503),
  });
  renderAt("/games/3498");
  expect(await screen.findByText(/no estimate is available yet/)).toBeInTheDocument();
});

test("an unreachable backend gets a clear message and a retry", async () => {
  let calls = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      // The main list pages with skip=; the shelves above it do not.
      if (url.startsWith("/api/games?") && url.includes("skip=")) {
        calls += 1;
        if (calls === 1) throw new TypeError("Failed to fetch");
        return json([GAME]);
      }
      return json([]);
    }),
  );
  renderAt("/");
  expect(await screen.findByText(/Can't reach the API/)).toBeInTheDocument();
  expect(screen.queryByText(/Failed to fetch/)).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Try again" }));
  expect((await screen.findAllByText("Grand Theft Auto V")).length).toBeGreaterThan(0);
});

test("a proxy 502 without a body counts as unreachable", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response("Bad Gateway", { status: 502 })));
  await expect(api.genres()).rejects.toSatisfy(isUnreachable);
});

test("the estimate page sends every trait to the API", async () => {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, _init?: RequestInit) => {
    const path = String(input).split("?")[0];
    if (path === "/api/predictions/metacritic") {
      return json({
        ...PREDICTION,
        predicted_metacritic: 81.2,
        expected: { score: 81.2, low: 73, high: 90, reception: "favourable" },
        game_id: null,
        actual_metacritic: null,
      });
    }
    if (path === "/api/ml/model") {
      return json({ model_name: "m", model_version: "3", run_id: null, metrics: { test_mae: 8.4 }, tracking_uri: "" });
    }
    if (path === "/api/stats/esrb-ratings") return json([{ name: "Mature", count: 3 }]);
    if (path === "/api/genres") return json([{ id: 5, name: "RPG", slug: "rpg" }]);
    return json([]);
  });
  vi.stubGlobal("fetch", fetchMock);
  renderAt("/predict"); // the old address redirects
  expect(screen.getByRole("button", { name: "Estimate reception" })).toBeDisabled();
  fireEvent.click(await screen.findByRole("button", { name: "RPG" }));
  fireEvent.change(screen.getByLabelText(/Working title/), { target: { value: "Space Saga II" } });
  fireEvent.change(screen.getByLabelText(/Tags/), { target: { value: "Singleplayer, Story Rich" } });
  fireEvent.click(screen.getByRole("button", { name: "Estimate reception" }));

  expect(await screen.findByText("Generally favourable")).toBeInTheDocument();
  expect(screen.getByText(/Space Saga II would most likely land between 73 and 90/)).toBeInTheDocument();
  const call = fetchMock.mock.calls.find(([input]) => String(input) === "/api/predictions/metacritic")!;
  expect(JSON.parse(String(call[1]!.body))).toMatchObject({
    name: "Space Saga II",
    genres: ["RPG"],
    platforms: [],
    tags: ["Singleplayer", "Story Rich"],
    esrb_rating: null,
  });
});

test("api errors carry FastAPI's detail message", async () => {
  mockApi({ "/api/auth/login": () => json({ detail: "Invalid credentials" }, 401) });
  await expect(api.login("a@b.c", "x")).rejects.toEqual(new ApiError(401, "Invalid credentials"));
});
