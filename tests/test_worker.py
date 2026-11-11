from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.backend import crud, models
from src.worker import rawg_api, tasks

# One game shaped like an entry of RAWG's /api/games "results" list.
RAWG_GAME = {
    "id": 3498,
    "slug": "grand-theft-auto-v",
    "name": "Grand Theft Auto V",
    "released": "2013-09-17",
    "rating": 4.47,
    "ratings_count": 6825,
    "metacritic": 92,
    "playtime": 74,
    "background_image": "https://media.rawg.io/media/games/gta.jpg",
    "clip": None,
    "genres": [{"id": 4, "name": "Action", "slug": "action", "games_count": 180710}],
    "platforms": [
        {"platform": {"id": 4, "name": "PC", "slug": "pc"}, "released_at": "2013-09-17"},
        {"platform": {"id": 187, "name": "PlayStation 5", "slug": "playstation5"}},
    ],
    "stores": [{"id": 290376, "store": {"id": 1, "name": "Steam", "slug": "steam"}}],
    "tags": [{"id": 31, "name": "Singleplayer", "slug": "singleplayer", "language": "eng"}],
}


def test_to_game_create_maps_rawg_payload():
    game = tasks.to_game_create(RAWG_GAME)
    assert game.released == datetime(2013, 9, 17)
    assert [p.slug for p in game.platforms] == ["pc", "playstation5"]
    assert [s.name for s in game.stores] == ["Steam"]
    assert game.background_image.endswith("gta.jpg")


def test_to_game_create_handles_nulls_and_clip_object():
    sparse = {
        "id": 1,
        "slug": "sparse",
        "name": "Sparse",
        "genres": None,
        "platforms": None,
        "stores": None,
        "tags": None,
        "clip": {"clip": "https://media.rawg.io/clip.mp4", "clips": {}},
    }
    game = tasks.to_game_create(sparse)
    assert game.platforms == [] and game.tags == []
    assert game.clip == "https://media.rawg.io/clip.mp4"


def test_fetch_games_for_month_task_saves_games(db):
    with patch.object(
        rawg_api, "fetch_games_for_month", AsyncMock(return_value=[RAWG_GAME])
    ) as fetch:
        result = tasks.fetch_games_for_month_task(2013, 9)
        again = tasks.fetch_games_for_month_task(2013, 9)

    fetch.assert_awaited_with(2013, 9)
    assert result == {
        "status": "success",
        "year": 2013,
        "month": 9,
        "games_fetched": 1,
        "games_created": 1,
        "games_updated": 0,
        "games_merged": 0,
        "games_failed": 0,
    }
    # Running the same month again must not duplicate anything.
    assert again["games_created"] == 0

    game = crud.get_game_by_slug(db, "grand-theft-auto-v")
    assert game.metacritic == 92
    assert [g.name for g in game.genres] == ["Action"]
    assert sorted(p.name for p in game.platforms) == ["PC", "PlayStation 5"]
    assert [t.slug for t in game.tags] == ["singleplayer"]


def test_fetch_weekly_updates_task_creates_and_updates(db):
    with patch.object(
        rawg_api, "fetch_recently_updated_games", AsyncMock(return_value=[RAWG_GAME])
    ):
        first = tasks.fetch_weekly_updates_task()

    assert (first["games_created"], first["games_updated"]) == (1, 0)

    changed = {**RAWG_GAME, "rating": 4.6, "background_image": None, "tags": []}
    with patch.object(rawg_api, "fetch_recently_updated_games", AsyncMock(return_value=[changed])):
        second = tasks.fetch_weekly_updates_task()

    assert (second["games_created"], second["games_updated"]) == (0, 1)
    db.expire_all()
    game = db.get(models.Game, 3498)
    assert game.rating == 4.6
    assert game.tags == []
    # A missing image in the update does not wipe the one we already have.
    assert game.background_image.endswith("gta.jpg")


def test_one_bad_record_does_not_abort_the_batch(db):
    bad = {"id": 2, "slug": "no-name"}
    with patch.object(
        rawg_api, "fetch_recently_updated_games", AsyncMock(return_value=[bad, RAWG_GAME])
    ):
        result = tasks.fetch_weekly_updates_task()

    assert (result["games_failed"], result["games_created"]) == (1, 1)


def test_lookup_with_same_slug_under_another_id_is_reused(db):
    # The fixture already has genre id=1 "Action"; RAWG's id for it is 4.
    with patch.object(rawg_api, "fetch_games_for_month", AsyncMock(return_value=[RAWG_GAME])):
        result = tasks.fetch_games_for_month_task(2013, 9)

    assert result["games_failed"] == 0
    assert [g.id for g in db.get(models.Game, 3498).genres] == [1]


def test_fetch_monthly_updates_task_targets_previous_month():
    with patch.object(tasks, "fetch_games_for_month_task") as fetch_month:
        tasks.fetch_monthly_updates_task()

    last_day_of_previous_month = datetime.today().replace(day=1) - timedelta(days=1)
    fetch_month.assert_called_once_with(
        last_day_of_previous_month.year, last_day_of_previous_month.month
    )


# --- RAWG client ---


_RealAsyncClient = httpx.AsyncClient


def _client(handler) -> httpx.AsyncClient:
    return _RealAsyncClient(transport=httpx.MockTransport(handler))


async def _no_sleep(_):
    return None


def test_rawg_client_follows_pagination(monkeypatch):
    monkeypatch.setenv("RAWG_API_KEY", "test-key")
    pages = {
        "1": {"results": [{"id": 1}], "next": "https://api.rawg.io/api/games?page=2"},
        "2": {"results": [{"id": 2}], "next": None},
    }
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(dict(request.url.params))
        return httpx.Response(200, json=pages[request.url.params["page"]])

    monkeypatch.setattr(rawg_api.httpx, "AsyncClient", lambda **kw: _client(handler))
    games = rawg_api.asyncio.run(rawg_api.fetch_games_for_month(2024, 2))

    assert [g["id"] for g in games] == [1, 2]
    assert seen[0]["dates"] == "2024-02-01,2024-02-29"
    assert seen[0]["key"] == "test-key"


def test_rawg_client_retries_server_errors(monkeypatch):
    monkeypatch.setenv("RAWG_API_KEY", "test-key")
    monkeypatch.setattr(rawg_api.asyncio, "sleep", _no_sleep)
    statuses = iter([502, 429, 200])

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(next(statuses), json={"results": [{"id": 1}], "next": None})

    monkeypatch.setattr(rawg_api.httpx, "AsyncClient", lambda **kw: _client(handler))
    assert len(rawg_api.asyncio.run(rawg_api.fetch_recently_updated_games())) == 1


def test_rawg_client_fails_loudly_on_bad_key(monkeypatch):
    monkeypatch.setenv("RAWG_API_KEY", "wrong")
    monkeypatch.setattr(
        rawg_api.httpx, "AsyncClient", lambda **kw: _client(lambda r: httpx.Response(401))
    )
    with pytest.raises(rawg_api.RawgApiError, match="401"):
        rawg_api.asyncio.run(rawg_api.fetch_games_for_month(2024, 1))


def test_rawg_client_requires_api_key(monkeypatch):
    monkeypatch.delenv("RAWG_API_KEY", raising=False)
    with pytest.raises(rawg_api.RawgApiError, match="RAWG_API_KEY"):
        rawg_api.asyncio.run(rawg_api.fetch_games_for_month(2024, 1))
