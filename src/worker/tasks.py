"""Celery tasks: game ingestion (Steam, IGDB, RAWG), model training, and demo tasks."""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Any

from src.backend import crud, schemas
from src.backend.celery_app import celery_app
from src.backend.database import SessionLocal
from src.worker import rawg_api
from src.worker.sources import igdb, steam

logger = logging.getLogger(__name__)

# ----------------------------------------------------
# Demo tasks (used to try out the task-management UI)
# ----------------------------------------------------


@celery_app.task(bind=True)
def test_task(self, message="Hello from Celery!"):
    """Simple test task to demonstrate progress updates."""
    for i in range(10):
        time.sleep(1)
        self.update_state(state="PROGRESS", meta={"current": i + 1, "total": 10})
    return {"message": message, "status": "completed"}


@celery_app.task
def quick_test():
    """A quick task for basic testing."""
    return {"status": "Quick test completed"}


@celery_app.task
def long_running_task(duration=30):
    """Long-running task for testing extended operations."""
    time.sleep(duration)
    return {"status": f"Completed after {duration} seconds"}


@celery_app.task
def example_task(x: int, y: int) -> int:
    """An example task that adds two numbers."""
    time.sleep(5)
    return x + y


# ----------------------------------------------------
# RAWG data ingestion
# ----------------------------------------------------


def to_game_create(game_data: dict[str, Any]) -> schemas.GameCreate:
    """Map one game from a RAWG API response to our schema."""
    clip = game_data.get("clip")
    return schemas.GameCreate(
        id=game_data["id"],
        slug=game_data["slug"],
        name=game_data["name"],
        released=game_data.get("released"),
        rating=game_data.get("rating"),
        ratings_count=game_data.get("ratings_count"),
        metacritic=game_data.get("metacritic"),
        playtime=game_data.get("playtime"),
        background_image=game_data.get("background_image"),
        clip=clip.get("clip") if isinstance(clip, dict) else clip,
        # RAWG returns null instead of an empty list for these.
        genres=game_data.get("genres") or [],
        platforms=[p["platform"] for p in game_data.get("platforms") or []],
        stores=[s["store"] for s in game_data.get("stores") or []],
        tags=game_data.get("tags") or [],
    )


def save_games(games: list[schemas.GameCreate], source_field: str | None) -> dict[str, int]:
    """Upsert games from one source. See `crud.upsert_game` for how matches are handled."""
    counts = {"created": 0, "updated": 0, "merged": 0}
    failed = 0
    with SessionLocal(expire_on_commit=False) as db:
        for game in games:
            try:
                _, outcome = crud.upsert_game(db, game, source_field=source_field)
                counts[outcome] += 1
            except Exception:
                # One bad record must not abort the whole batch.
                db.rollback()
                failed += 1
                logger.exception("Could not save game %r", game.slug)
    return {
        "games_fetched": len(games),
        "games_created": counts["created"],
        "games_updated": counts["updated"],
        "games_merged": counts["merged"],
        "games_failed": failed,
    }


def _save_games(games_data: list[dict[str, Any]], update_existing: bool) -> dict[str, int]:
    """Save RAWG API results. Without `update_existing`, games we already have are skipped."""
    games, unparsable = [], 0
    for game_data in games_data:
        try:
            games.append(to_game_create(game_data))
        except Exception:
            unparsable += 1
            logger.exception("Could not parse RAWG game %r", game_data.get("slug"))
    if not update_existing:
        with SessionLocal() as db:
            games = [g for g in games if crud.find_matching_game(db, g) is None]
    result = save_games(games, source_field=None)
    result["games_fetched"] = len(games_data)
    result["games_failed"] += unparsable
    return result


# ----------------------------------------------------
# Steam + SteamSpy and IGDB ingestion
# ----------------------------------------------------


@celery_app.task
def fetch_steam_games_task(list_name: str = "topsellers", limit: int = 100) -> dict:
    """Fetch games from a Steam store list ("topsellers", "new", "top_rated") and save them."""
    games = asyncio.run(steam.fetch_games(list_name, limit))
    result = save_games(games, "steam_appid")
    return {"status": "success", "source": "steam", "list": list_name, **result}


@celery_app.task
def fetch_igdb_games_for_month_task(year: int, month: int) -> dict:
    """Fetch every game IGDB lists as released in the given month and save it."""
    games = asyncio.run(igdb.fetch_games_for_month(year, month))
    result = save_games(games, "igdb_id")
    return {"status": "success", "source": "igdb", "year": year, "month": month, **result}


@celery_app.task
def fetch_igdb_monthly_updates_task() -> dict:
    """IGDB games released in the previous month."""
    previous_month = datetime.now().replace(day=1) - timedelta(days=1)
    return fetch_igdb_games_for_month_task(previous_month.year, previous_month.month)


# ----------------------------------------------------
# Machine learning
# ----------------------------------------------------


@celery_app.task
def train_metacritic_model_task() -> dict:
    """Retrain the Metacritic model on the current database and log it to MLflow."""
    from src.ml import train  # heavy imports (scikit-learn, mlflow) only when needed

    return train.main([])


@celery_app.task
def fetch_games_for_month_task(year: int, month: int) -> dict[str, str | int]:
    """Fetch and save games from RAWG API for a specified month."""
    logger.info("Fetching games for %d-%02d", year, month)
    games_data = asyncio.run(rawg_api.fetch_games_for_month(year, month))
    result = _save_games(games_data, update_existing=False)
    return {"status": "success", "year": year, "month": month, **result}


@celery_app.task
def fetch_monthly_updates_task() -> dict[str, str | int]:
    """Fetch games for the previous month."""
    previous_month = datetime.now().replace(day=1) - timedelta(days=1)
    return fetch_games_for_month_task(previous_month.year, previous_month.month)


@celery_app.task
def fetch_weekly_updates_task() -> dict[str, str | int]:
    """Fetch and update games from RAWG API that have updates in the last week."""
    logger.info("Fetching recently updated games")
    games_data = asyncio.run(rawg_api.fetch_recently_updated_games(days=7))
    result = _save_games(games_data, update_existing=True)
    return {"status": "success", **result}
