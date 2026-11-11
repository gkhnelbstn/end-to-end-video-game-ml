"""IGDB (owned by Twitch): every platform, queried by release date.

Needs a free Twitch developer application: set IGDB_CLIENT_ID and IGDB_CLIENT_SECRET.
See https://api-docs.igdb.com/#account-creation

IGDB's `aggregated_rating` is an average of critic reviews, not a Metacritic score, so it
is stored in `critic_rating` and never mixed into `metacritic`.
"""

import asyncio
import logging
import os
from datetime import UTC, datetime
from typing import Any

import httpx

from src.backend.schemas import GameCreate, slugify
from src.worker.sources import common
from src.worker.sources.common import SourceError

logger = logging.getLogger(__name__)

TOKEN_URL = "https://id.twitch.tv/oauth2/token"
GAMES_URL = "https://api.igdb.com/v4/games"
PAGE_SIZE = 500
# IGDB allows 4 requests per second.
REQUEST_INTERVAL = 0.3
FIELDS = ",".join(
    [
        "name",
        "slug",
        "first_release_date",
        "aggregated_rating",
        "genres.name",
        "platforms.name",
        "themes.name",
        "game_modes.name",
        "player_perspectives.name",
        "cover.image_id",
        "videos.video_id",
    ]
)


def credentials() -> tuple[str, str]:
    client_id = os.environ.get("IGDB_CLIENT_ID", "")
    client_secret = os.environ.get("IGDB_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        raise SourceError(
            "IGDB_CLIENT_ID and IGDB_CLIENT_SECRET are not set. "
            "Create a Twitch application: https://api-docs.igdb.com/#account-creation"
        )
    return client_id, client_secret


def is_configured() -> bool:
    try:
        credentials()
    except SourceError:
        return False
    return True


def _names(items: list[dict[str, Any]] | None) -> list[str]:
    return [item.get("name", "") for item in items or []]


def to_game_create(game: dict[str, Any]) -> GameCreate:
    """Map one IGDB game to our schema."""
    released = game.get("first_release_date")
    cover = (game.get("cover") or {}).get("image_id")
    videos = game.get("videos") or []
    name = common.clean_name(game["name"])
    return GameCreate(
        slug=game.get("slug") or slugify(name),
        name=name,
        released=(datetime.fromtimestamp(released, UTC).replace(tzinfo=None) if released else None),
        critic_rating=game.get("aggregated_rating"),
        background_image=(
            f"https://images.igdb.com/igdb/image/upload/t_1080p/{cover}.jpg" if cover else None
        ),
        clip=(
            f"https://www.youtube.com/watch?v={videos[0]['video_id']}"
            if videos and videos[0].get("video_id")
            else None
        ),
        igdb_id=int(game["id"]),
        genres=common.genres(_names(game.get("genres"))),
        platforms=common.platforms(_names(game.get("platforms"))),
        tags=common.tags(
            _names(game.get("themes"))
            + _names(game.get("game_modes"))
            + _names(game.get("player_perspectives"))
        ),
    )


async def access_token(client: httpx.AsyncClient) -> str:
    client_id, client_secret = credentials()
    payload = await common.request_json(
        client,
        "POST",
        TOKEN_URL,
        source="Twitch OAuth",
        params={
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "client_credentials",
        },
    )
    if not payload or "access_token" not in payload:
        raise SourceError("Twitch OAuth returned no access token")
    return payload["access_token"]


async def fetch_games_between(start: datetime, end: datetime) -> list[GameCreate]:
    """All games first released in [start, end)."""
    client_id, _ = credentials()
    games: list[GameCreate] = []
    async with httpx.AsyncClient(timeout=30) as client:
        headers = {
            "Client-ID": client_id,
            "Authorization": f"Bearer {await access_token(client)}",
        }
        where = (
            f"first_release_date >= {int(start.replace(tzinfo=UTC).timestamp())} & "
            f"first_release_date < {int(end.replace(tzinfo=UTC).timestamp())}"
        )
        offset = 0
        while True:
            query = (
                f"fields {FIELDS}; where {where}; sort id asc; limit {PAGE_SIZE}; offset {offset};"
            )
            page = await common.request_json(
                client, "POST", GAMES_URL, source="IGDB", headers=headers, content=query
            )
            page = page or []
            games.extend(to_game_create(g) for g in page if g.get("name"))
            if len(page) < PAGE_SIZE:
                break
            offset += PAGE_SIZE
            await asyncio.sleep(REQUEST_INTERVAL)
    logger.info("Fetched %d games from IGDB", len(games))
    return games


async def fetch_games_for_month(year: int, month: int) -> list[GameCreate]:
    start = datetime(year, month, 1)
    end = datetime(year + (month == 12), month % 12 + 1, 1)
    return await fetch_games_between(start, end)
