"""
An asynchronous module for interacting with the RAWG.io API using httpx.
"""
import os
import asyncio
import httpx
import calendar
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

BASE_URL = "https://api.rawg.io/api/games"
API_KEY = os.environ.get("RAWG_API_KEY")


async def make_request(
    client: httpx.AsyncClient,
    url: str,
    params: Dict[str, Any],
    retries: int = 5,
    backoff_factor: float = 1.0,
) -> Optional[httpx.Response]:
    """
    Makes an asynchronous GET request to the given URL with retries.
    """
    for i in range(retries):
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as http_err:
            if http_err.response.status_code == 404:
                print(f"404 Error: Not Found. No more pages available.")
                return None
            elif http_err.response.status_code == 502:
                print(f"502 Server Error. Retrying in {backoff_factor * (2 ** i)} seconds...")
                await asyncio.sleep(backoff_factor * (2 ** i))
            else:
                print(f"HTTP error occurred: {http_err}")
        except httpx.RequestError as e:
            print(f"Request failed: {e}. Retrying in {backoff_factor * (2 ** i)} seconds...")
            await asyncio.sleep(backoff_factor * (2 ** i))
    print("Maximum retries exceeded for current request.")
    return None


async def fetch_games_for_month(year: int, month: int) -> List[Dict[str, Any]]:
    """
    Fetches all games released in a specific month from the RAWG API asynchronously.
    """
    if not API_KEY:
        raise ValueError("RAWG_API_KEY environment variable not set.")

    _, num_days = calendar.monthrange(year, month)
    start_date = f"{year}-{month:02d}-01"
    end_date = f"{year}-{month:02d}-{num_days}"

    params = {
        "key": API_KEY,
        "page": 1,
        "page_size": 40,
        "dates": f"{start_date},{end_date}",
    }

    all_games = []
    async with httpx.AsyncClient() as client:
        while True:
            response = await make_request(client, url=BASE_URL, params=params)
            if response is None:
                break

            data = response.json()
            all_games.extend(data.get("results", []))

            if "next" in data and data["next"]:
                params["page"] += 1
            else:
                break

    return all_games


async def fetch_recently_updated_games(days: int = 7) -> List[Dict[str, Any]]:
    """
    Fetches all games updated in the last `days` from the RAWG API asynchronously.
    """
    if not API_KEY:
        raise ValueError("RAWG_API_KEY environment variable not set.")

    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    params = {
        "key": API_KEY,
        "page": 1,
        "page_size": 40,
        "updated": f"{start_date.strftime('%Y-%m-%d')},{end_date.strftime('%Y-%m-%d')}",
    }

    all_games = []
    async with httpx.AsyncClient() as client:
        while True:
            response = await make_request(client, url=BASE_URL, params=params)
            if response is None:
                break

            data = response.json()
            all_games.extend(data.get("results", []))

            if "next" in data and data["next"]:
                params["page"] += 1
            else:
                break

    return all_games
