"""HTTP and naming helpers shared by the source clients."""

import asyncio
import logging
from typing import Any

import httpx

from src.backend.schemas import LookupIn

logger = logging.getLogger(__name__)


class SourceError(RuntimeError):
    """A source rejected the request or kept failing."""


async def request_json(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    source: str,
    retries: int = 5,
    backoff_factor: float = 1.0,
    **kwargs: Any,
) -> Any | None:
    """Send a request with retries on transient errors (network, 429, 5xx).

    Returns the decoded JSON, or None on 404. Raises SourceError on other 4xx responses.
    Never logs the URL: some sources put credentials in it.
    """
    for attempt in range(retries):
        delay = backoff_factor * (2**attempt)
        try:
            response = await client.request(method, url, **kwargs)
        except httpx.RequestError as exc:
            logger.warning("%s request failed (%s); retrying in %ss", source, exc, delay)
            await asyncio.sleep(delay)
            continue

        status = response.status_code
        if status == 404:
            return None
        if status == 429 or status >= 500:
            logger.warning("%s returned HTTP %s; retrying in %ss", source, status, delay)
            await asyncio.sleep(delay)
            continue
        if status >= 400:
            raise SourceError(f"{source} returned HTTP {status}")
        try:
            return response.json()
        except ValueError as exc:
            # SteamSpy answers overload with a plain-text 200 ("Connection failed: ...").
            logger.warning("%s returned a non-JSON body; retrying in %ss", source, delay)
            if attempt == retries - 1:
                raise SourceError(f"{source} returned a non-JSON response") from exc
            await asyncio.sleep(delay)

    raise SourceError(f"{source} still failing after {retries} attempts")


_TRADEMARKS = str.maketrans("", "", "™®©")


def clean_name(name: str) -> str:
    """Store names carry trademark signs ("Apex Legends™") that other sources omit."""
    return " ".join(name.translate(_TRADEMARKS).split())


# Names as the RAWG snapshot spells them, so rows from every source share look-up rows.
_GENRE_NAMES = {
    "role-playing (rpg)": "RPG",
    "platform": "Platformer",
    "simulator": "Simulation",
    "sport": "Sports",
    "real time strategy (rts)": "Strategy",
    "turn-based strategy (tbs)": "Strategy",
    "hack and slash/beat 'em up": "Action",
    "card & board game": "Card",
    "point-and-click": "Adventure",
}
_PLATFORM_NAMES = {
    "pc (microsoft windows)": "PC",
    "windows": "PC",
    "mac": "macOS",
    "linux": "Linux",
    "xbox series x|s": "Xbox Series S/X",
    "playstation 4": "PlayStation 4",
    "playstation 5": "PlayStation 5",
}
_TAG_NAMES = {
    "single-player": "Singleplayer",
    "single player": "Singleplayer",
    "multi-player": "Multiplayer",
    "co-operative": "Co-op",
    "online co-op": "Online Co-Op",
    "pvp": "PvP",
    "online pvp": "Online PvP",
    "first person": "First-Person",
    "third person": "Third Person",
}


def _lookups(names, mapping: dict[str, str]) -> list[LookupIn]:
    seen: dict[str, LookupIn] = {}
    for raw in names:
        if not raw:
            continue
        name = mapping.get(raw.strip().lower(), raw.strip())
        seen.setdefault(name.lower(), LookupIn(name=name))
    return list(seen.values())


def genres(names) -> list[LookupIn]:
    return _lookups(names, _GENRE_NAMES)


def platforms(names) -> list[LookupIn]:
    return _lookups(names, _PLATFORM_NAMES)


def tags(names) -> list[LookupIn]:
    return _lookups(names, _TAG_NAMES)
