"""Steam/SteamSpy and IGDB clients (HTTP mocked) and cross-source merging."""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.backend import crud, models
from src.worker import tasks
from src.worker.sources import common, igdb, steam

# Trimmed from a real appdetails response (Cyberpunk 2077, fetched 2026-11-10).
STEAM_DETAILS = {
    "type": "game",
    "name": "Cyberpunk 2077",
    "steam_appid": 1091500,
    "metacritic": {"score": 86, "url": "https://www.metacritic.com/game/pc/cyberpunk-2077"},
    "genres": [{"id": "1", "description": "Action"}, {"id": "3", "description": "RPG"}],
    "categories": [
        {"id": 2, "description": "Single-player"},
        {"id": 22, "description": "Steam Achievements"},
    ],
    "platforms": {"windows": True, "mac": True, "linux": False},
    "release_date": {"coming_soon": False, "date": "Dec 9, 2020"},
    "header_image": "https://shared.akamai.steamstatic.com/header.jpg",
}
STEAMSPY = {"appid": 1091500, "tags": {"Open World": 6081, "Cyberpunk": 6625, "RPG": 5000}}

IGDB_GAME = {
    "id": 1877,
    "name": "Cyberpunk 2077",
    "slug": "cyberpunk-2077",
    "first_release_date": 1607472000,  # 2020-12-09
    "aggregated_rating": 81.4,
    "genres": [{"id": 12, "name": "Role-playing (RPG)"}, {"id": 5, "name": "Shooter"}],
    "platforms": [
        {"id": 6, "name": "PC (Microsoft Windows)"},
        {"id": 167, "name": "PlayStation 5"},
    ],
    "themes": [{"id": 1, "name": "Action"}, {"id": 18, "name": "Science fiction"}],
    "game_modes": [{"id": 1, "name": "Single player"}],
    "cover": {"id": 1, "image_id": "co7497"},
    "videos": [{"id": 1, "video_id": "abc123"}],
}

_RealAsyncClient = httpx.AsyncClient


async def _no_sleep(_):
    return None


@pytest.fixture(autouse=True)
def fast(monkeypatch):
    monkeypatch.setattr(common.asyncio, "sleep", _no_sleep)
    monkeypatch.setattr(steam.asyncio, "sleep", _no_sleep)
    monkeypatch.setattr(igdb.asyncio, "sleep", _no_sleep)


def _mock_client(monkeypatch, module, handler):
    monkeypatch.setattr(
        module.httpx,
        "AsyncClient",
        lambda **kw: _RealAsyncClient(transport=httpx.MockTransport(handler)),
    )


# --- Steam ---


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Dec 9, 2020", datetime(2020, 12, 9)),
        ("9 Dec, 2020", datetime(2020, 12, 9)),
        ("March 2027", datetime(2027, 3, 1)),
        ("Q3 2026", None),
        ("Coming soon", None),
    ],
)
def test_parse_release_date(text, expected):
    assert steam.parse_release_date({"coming_soon": False, "date": text}) == expected


def test_parse_release_date_coming_soon_flag():
    assert steam.parse_release_date({"coming_soon": True, "date": "Dec 9, 2020"}) is None


def test_steam_to_game_create():
    game = steam.to_game_create(STEAM_DETAILS, STEAMSPY)
    assert (game.slug, game.steam_appid, game.metacritic) == ("cyberpunk-2077", 1091500, 86)
    assert game.released == datetime(2020, 12, 9)
    assert [g.name for g in game.genres] == ["Action", "RPG"]
    assert [p.name for p in game.platforms] == ["PC", "macOS"]
    assert [s.slug for s in game.stores] == ["steam"]
    tag_names = [t.name for t in game.tags]
    # Steam categories first (renamed to RAWG's spelling), then SteamSpy tags by votes.
    assert tag_names[:2] == ["Singleplayer", "Steam Achievements"]
    assert tag_names[2:] == ["Cyberpunk", "Open World", "RPG"]


def test_steam_names_lose_trademark_signs():
    game = steam.to_game_create({**STEAM_DETAILS, "name": "Call of Duty®: Warzone™ "}, None)
    assert (game.name, game.slug) == ("Call of Duty: Warzone", "call-of-duty-warzone")


def test_steam_free_to_play_is_a_tag_not_a_genre():
    details = {**STEAM_DETAILS, "genres": [{"description": "Free To Play"}]}
    game = steam.to_game_create(details, None)
    assert game.genres == []
    assert "Free To Play" in [t.name for t in game.tags]


def test_steam_fetch_games(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        host, params = request.url.host, request.url.params
        if request.url.path == "/search/results/":
            html = (
                ""
                if params["start"] != "0"
                else ('<a data-ds-appid="1091500"></a><a data-ds-appid="999"></a>')
            )
            return httpx.Response(200, json={"results_html": html})
        if host == "steamspy.com":
            # SteamSpy overloaded: plain-text 200. The game is still saved.
            return httpx.Response(200, text="Connection failed: Too many connections")
        app_id = params["appids"]
        if app_id == "999":  # a DLC
            return httpx.Response(200, json={"999": {"success": True, "data": {"type": "dlc"}}})
        return httpx.Response(200, json={app_id: {"success": True, "data": STEAM_DETAILS}})

    _mock_client(monkeypatch, steam, handler)
    games = asyncio.run(steam.fetch_games("topsellers", limit=10))

    assert [g.steam_appid for g in games] == [1091500]
    assert "Open World" not in [t.name for t in games[0].tags]


def test_steam_unknown_list():
    with pytest.raises(ValueError, match="Unknown Steam list"):
        asyncio.run(steam.list_app_ids(None, "bogus", 10))


def test_request_json_retries_then_gives_up(monkeypatch):
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(503)

    async def run():
        async with _RealAsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await common.request_json(client, "GET", "https://x.test", source="X", retries=3)

    with pytest.raises(common.SourceError, match="3 attempts"):
        asyncio.run(run())
    assert len(calls) == 3


# --- IGDB ---


def test_igdb_to_game_create():
    game = igdb.to_game_create(IGDB_GAME)
    assert (game.igdb_id, game.critic_rating, game.metacritic) == (1877, 81.4, None)
    assert game.released == datetime(2020, 12, 9)
    assert [g.name for g in game.genres] == ["RPG", "Shooter"]
    assert [p.name for p in game.platforms] == ["PC", "PlayStation 5"]
    assert "Singleplayer" in [t.name for t in game.tags]
    assert game.background_image.endswith("/t_1080p/co7497.jpg")
    assert game.clip == "https://www.youtube.com/watch?v=abc123"


def test_igdb_requires_credentials(monkeypatch):
    monkeypatch.delenv("IGDB_CLIENT_ID", raising=False)
    monkeypatch.delenv("IGDB_CLIENT_SECRET", raising=False)
    assert not igdb.is_configured()
    with pytest.raises(common.SourceError, match="IGDB_CLIENT_ID"):
        asyncio.run(igdb.fetch_games_for_month(2020, 12))


def test_igdb_fetch_paginates_with_token(monkeypatch):
    monkeypatch.setenv("IGDB_CLIENT_ID", "id")
    monkeypatch.setenv("IGDB_CLIENT_SECRET", "secret")
    monkeypatch.setattr(igdb, "PAGE_SIZE", 1)
    queries = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "id.twitch.tv":
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 100})
        assert request.headers["Authorization"] == "Bearer tok"
        assert request.headers["Client-ID"] == "id"
        query = request.content.decode()
        queries.append(query)
        return httpx.Response(200, json=[IGDB_GAME] if "offset 0;" in query else [])

    _mock_client(monkeypatch, igdb, handler)
    games = asyncio.run(igdb.fetch_games_for_month(2020, 12))

    assert [g.igdb_id for g in games] == [1877]
    assert len(queries) == 2
    # December rolls over into January of the next year.
    assert "first_release_date >= 1606780800" in queries[0]
    assert "first_release_date < 1609459200" in queries[0]


# --- Saving and merging across sources ---


def test_steam_then_igdb_merge_into_one_game(db):
    steam_game = steam.to_game_create(STEAM_DETAILS, STEAMSPY)
    with patch.object(steam, "fetch_games", AsyncMock(return_value=[steam_game])):
        first = tasks.fetch_steam_games_task("topsellers", 1)
        again = tasks.fetch_steam_games_task("topsellers", 1)
    with patch.object(
        igdb, "fetch_games_for_month", AsyncMock(return_value=[igdb.to_game_create(IGDB_GAME)])
    ):
        merged = tasks.fetch_igdb_games_for_month_task(2020, 12)

    assert (first["games_created"], again["games_updated"], merged["games_merged"]) == (1, 1, 1)
    db.expire_all()
    rows = db.query(models.Game).filter(models.Game.name == "Cyberpunk 2077").all()
    assert len(rows) == 1
    game = rows[0]
    assert (game.steam_appid, game.igdb_id) == (1091500, 1877)
    # Steam's Metacritic score stays; IGDB's critic average goes to its own column.
    assert (game.metacritic, game.critic_rating) == (86, 81.4)
    # IGDB added PlayStation 5 and Shooter without dropping Steam's data.
    assert {p.name for p in game.platforms} == {"PC", "macOS", "PlayStation 5"}
    assert {g.name for g in game.genres} == {"Action", "RPG", "Shooter"}
    # "Action" and "RPG" reused the fixture's look-up rows instead of creating duplicates.
    assert db.query(models.Genre).filter(models.Genre.name == "Action").count() == 1


def test_same_name_different_year_stays_separate(db):
    old = steam.to_game_create(STEAM_DETAILS, None)
    remake = steam.to_game_create(
        {**STEAM_DETAILS, "steam_appid": 2, "release_date": {"date": "Jan 1, 2030"}}, None
    )
    crud.upsert_game(db, old, "steam_appid")
    row, outcome = crud.upsert_game(db, remake, "steam_appid")

    assert outcome == "created"
    assert row.slug == "cyberpunk-2077-2030"


def test_two_steam_apps_with_same_name_and_year_are_not_merged(db):
    first = steam.to_game_create(STEAM_DETAILS, None)
    second = steam.to_game_create({**STEAM_DETAILS, "steam_appid": 2}, None)
    crud.upsert_game(db, first, "steam_appid")
    row, outcome = crud.upsert_game(db, second, "steam_appid")

    assert outcome == "created"
    assert row.slug == "cyberpunk-2077-2020"
    assert crud.count_games(db) == 5
