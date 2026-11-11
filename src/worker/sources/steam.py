"""Steam store + SteamSpy. Neither needs an API key.

- Steam store search lists app ids (top sellers, new releases, top rated).
- Steam `appdetails` gives name, release date, genres, platforms, Metacritic score, images.
- SteamSpy adds community tags. It is often overloaded, so a failure there only means
  the game is saved without SteamSpy tags.

Steam allows roughly 200 `appdetails` calls per 5 minutes, hence the pause between calls.
"""

import asyncio
import logging
import os
import re
from datetime import datetime
from typing import Any

import httpx

from src.backend.schemas import GameCreate, LookupIn, slugify
from src.worker.sources import common
from src.worker.sources.common import SourceError

logger = logging.getLogger(__name__)

SEARCH_URL = "https://store.steampowered.com/search/results/"
APPDETAILS_URL = "https://store.steampowered.com/api/appdetails"
STEAMSPY_URL = "https://steamspy.com/api.php"

# Steam store search orderings that `fetch_games` can walk.
LISTS = {
    "topsellers": {"filter": "topsellers"},
    "new": {"sort_by": "Released_DESC"},
    "top_rated": {"sort_by": "Reviews_DESC"},
}
SEARCH_PAGE_SIZE = 50
MAX_STEAMSPY_TAGS = 20
# Steam "genres" that are really business models; stored as tags instead.
_GENRES_AS_TAGS = {"free to play", "early access"}
_DATE_FORMATS = ("%b %d, %Y", "%d %b, %Y", "%B %d, %Y", "%d %B, %Y", "%b %Y", "%B %Y", "%Y")


def request_interval() -> float:
    """Seconds to wait between Steam/SteamSpy calls."""
    return float(os.environ.get("STEAM_REQUEST_INTERVAL", "1.5"))


def parse_release_date(release_date: dict[str, Any] | None) -> datetime | None:
    """Steam dates are free text: "Dec 9, 2020", "9 Dec, 2020", "Q3 2026", "Coming soon"."""
    if not release_date or release_date.get("coming_soon"):
        return None
    text = (release_date.get("date") or "").strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def to_game_create(details: dict[str, Any], steamspy: dict[str, Any] | None) -> GameCreate:
    """Map a Steam `appdetails` payload (plus optional SteamSpy data) to our schema."""
    steam_genres = [g.get("description", "") for g in details.get("genres") or []]
    categories = [c.get("description", "") for c in details.get("categories") or []]
    spy_tags = (steamspy or {}).get("tags") or {}
    # SteamSpy returns [] instead of {} when a game has no tags.
    if isinstance(spy_tags, dict):
        ranked = sorted(spy_tags.items(), key=lambda item: item[1], reverse=True)
        spy_tag_names = [name for name, _ in ranked[:MAX_STEAMSPY_TAGS]]
    else:
        spy_tag_names = []

    platform_flags = details.get("platforms") or {}
    platform_names = [name for name, enabled in platform_flags.items() if enabled]
    name = common.clean_name(details["name"])

    return GameCreate(
        slug=slugify(name),
        name=name,
        released=parse_release_date(details.get("release_date")),
        metacritic=(details.get("metacritic") or {}).get("score"),
        background_image=details.get("header_image"),
        steam_appid=int(details["steam_appid"]),
        genres=common.genres(g for g in steam_genres if g.lower() not in _GENRES_AS_TAGS),
        platforms=common.platforms(platform_names),
        stores=[LookupIn(name="Steam", slug="steam")],
        tags=common.tags(
            [g for g in steam_genres if g.lower() in _GENRES_AS_TAGS] + categories + spy_tag_names
        ),
    )


async def list_app_ids(client: httpx.AsyncClient, list_name: str, limit: int) -> list[int]:
    """App ids from a Steam store search list, games only (no DLC, demos or soundtracks)."""
    if list_name not in LISTS:
        raise ValueError(f"Unknown Steam list {list_name!r}; choose from {sorted(LISTS)}")
    app_ids: list[int] = []
    start = 0
    while len(app_ids) < limit:
        params = {
            "infinite": 1,
            "json": 1,
            "start": start,
            "count": SEARCH_PAGE_SIZE,
            "category1": 998,  # Games
            "cc": "us",
            "l": "english",
            **LISTS[list_name],
        }
        page = await common.request_json(
            client, "GET", SEARCH_URL, source="Steam search", params=params
        )
        html = (page or {}).get("results_html", "")
        found = [int(m) for m in re.findall(r'data-ds-appid="(\d+)"', html)]
        new = [app_id for app_id in found if app_id not in app_ids]
        if not new:
            break
        app_ids.extend(new)
        start += SEARCH_PAGE_SIZE
        await asyncio.sleep(request_interval())
    return app_ids[:limit]


async def app_details(client: httpx.AsyncClient, app_id: int) -> dict[str, Any] | None:
    """The store data for one app, or None if Steam has none or it is not a game."""
    payload = await common.request_json(
        client,
        "GET",
        APPDETAILS_URL,
        source="Steam appdetails",
        params={"appids": app_id, "cc": "us", "l": "english"},
    )
    entry = (payload or {}).get(str(app_id)) or {}
    data = entry.get("data") if entry.get("success") else None
    if not data or data.get("type") != "game" or not data.get("name"):
        return None
    return data


async def steamspy_details(client: httpx.AsyncClient, app_id: int) -> dict[str, Any] | None:
    try:
        return await common.request_json(
            client,
            "GET",
            STEAMSPY_URL,
            source="SteamSpy",
            params={"request": "appdetails", "appid": app_id},
            retries=2,
        )
    except SourceError as exc:
        logger.warning("SteamSpy unavailable for app %s (%s); saving without its tags", app_id, exc)
        return None


async def fetch_games(list_name: str = "topsellers", limit: int = 50) -> list[GameCreate]:
    """Fetch up to `limit` games from a Steam store list, with full details."""
    games: list[GameCreate] = []
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        for app_id in await list_app_ids(client, list_name, limit):
            details = await app_details(client, app_id)
            await asyncio.sleep(request_interval())
            if details is None:
                continue
            spy = await steamspy_details(client, app_id)
            games.append(to_game_create(details, spy))
    logger.info("Fetched %d games from Steam list %r", len(games), list_name)
    return games
