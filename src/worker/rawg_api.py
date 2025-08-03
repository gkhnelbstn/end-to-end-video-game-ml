"""
A module for interacting with the RAWG.io API.

This module provides functions to fetch data about video games from the
RAWG API. It handles API key authentication, request retries, and pagination.
"""
import os
import time
import requests
from typing import List, Dict, Any, Optional

BASE_URL = "https://api.rawg.io/api/games"
API_KEY = os.environ.get("RAWG_API_KEY")


def make_request(
    url: str, params: Dict[str, Any], retries: int = 5, backoff_factor: float = 1.0
) -> Optional[requests.Response]:
    """
    Makes a GET request to the given URL with retries.

    Args:
        url: The URL to make the request to.
        params: A dictionary of query parameters.
        retries: The maximum number of retries.
        backoff_factor: The factor to use for exponential backoff.

    Returns:
        A requests.Response object if successful, None otherwise.
    """
    for i in range(retries):
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response
        except requests.exceptions.HTTPError as http_err:
            if response.status_code == 404:
                print(f"404 Error: {response.json().get('detail', 'Not Found')}. No more pages available.")
                return None
            elif response.status_code == 502:
                print(f"502 Server Error: {http_err}. Retrying in {backoff_factor * (2 ** i)} seconds...")
                time.sleep(backoff_factor * (2 ** i))
            else:
                print(f"HTTP error occurred: {http_err}")
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}. Retrying in {backoff_factor * (2 ** i)} seconds...")
            time.sleep(backoff_factor * (2 ** i))
    print("Maximum retries exceeded for current request.")
    return None


def fetch_games_for_year(year: int) -> List[Dict[str, Any]]:
    """
    Fetches all games released in a specific year from the RAWG API.

    Args:
        year: The year to fetch games for.

    Returns:
        A list of dictionaries, where each dictionary represents a game.
    """
    if not API_KEY:
        raise ValueError("RAWG_API_KEY environment variable not set.")

    params = {
        "key": API_KEY,
        "page": 1,
        "page_size": 40,
        "dates": f"{year}-01-01,{year}-12-31",
    }

    all_games = []
    while True:
        response = make_request(url=BASE_URL, params=params)
        if response is None:
            break

        data = response.json()
        all_games.extend(data.get("results", []))

        if "next" in data and data["next"]:
            params["page"] += 1
        else:
            break

    return all_games
