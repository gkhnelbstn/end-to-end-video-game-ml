"""Asynchronous client for the RAWG.io games API."""

import asyncio
import calendar
import logging
import os
from datetime import datetime, timedelta
from typing import Any

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://api.rawg.io/api/games"
PAGE_SIZE = 40


class RawgApiError(RuntimeError):
    """The RAWG API rejected the request (e.g. a missing or invalid API key)."""


def _api_key() -> str:
    key = os.environ.get("RAWG_API_KEY")
    if not key or key == "your_api_key_here":
        raise RawgApiError("RAWG_API_KEY is not set. Get a free key at https://rawg.io/apidocs")
    return key


async def make_request(
    client: httpx.AsyncClient,
    url: str,
    params: dict[str, Any],
    retries: int = 5,
    backoff_factor: float = 1.0,
) -> httpx.Response | None:
    """GET with retries on transient errors. Returns None when there are no more pages."""
    for attempt in range(retries):
        delay = backoff_factor * (2**attempt)
        try:
            response = await client.get(url, params=params)
        except httpx.RequestError as exc:
            logger.warning("RAWG request failed (%s); retrying in %ss", exc, delay)
            await asyncio.sleep(delay)
            continue

        status = response.status_code
        if status == 404:
            # RAWG answers 404 when paging past the last page.
            return None
        if status == 429 or status >= 500:
            logger.warning("RAWG returned %s; retrying in %ss", status, delay)
            await asyncio.sleep(delay)
            continue
        if status >= 400:
            # Never log the URL here: it carries the API key.
            raise RawgApiError(f"RAWG API returned HTTP {status}; check RAWG_API_KEY")
        return response

    raise RawgApiError(f"RAWG API still failing after {retries} attempts")


async def _fetch_all_pages(filters: dict[str, Any]) -> list[dict[str, Any]]:
    params = {"key": _api_key(), "page": 1, "page_size": PAGE_SIZE, **filters}
    games: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=30) as client:
        while True:
            response = await make_request(client, url=BASE_URL, params=params)
            if response is None:
                break
            data = response.json()
            games.extend(data.get("results", []))
            if not data.get("next"):
                break
            params["page"] += 1
    return games


async def fetch_games_for_month(year: int, month: int) -> list[dict[str, Any]]:
    """Fetch all games released in the given month."""
    _, num_days = calendar.monthrange(year, month)
    start, end = f"{year}-{month:02d}-01", f"{year}-{month:02d}-{num_days}"
    return await _fetch_all_pages({"dates": f"{start},{end}"})


async def fetch_recently_updated_games(days: int = 7) -> list[dict[str, Any]]:
    """Fetch all games updated in the last `days` days."""
    end = datetime.now()
    start = end - timedelta(days=days)
    return await _fetch_all_pages({"updated": f"{start:%Y-%m-%d},{end:%Y-%m-%d}"})
