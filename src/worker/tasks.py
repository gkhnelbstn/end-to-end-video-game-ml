"""
Celery tasks for the Game Insight project.

This module contains the definitions of background tasks executed
by Celery workers. Includes scheduled and ad-hoc tasks for data ingestion.
"""
import time
import asyncio
from datetime import datetime, timedelta
import logging

from src.backend.celery_app import celery_app
from src.worker import rawg_api
from src.backend import crud, schemas
from src.backend.database import SessionLocal

logger = logging.getLogger(__name__)

# ----------------------------------------------------
# 🛠️ Utility Tasks (Testing and Examples)
# ----------------------------------------------------

@celery_app.task(bind=True)
def test_task(self, message="Hello from Celery!"):
    """Simple test task to demonstrate progress updates."""
    logger.info(f"Starting test_task with message: {message}")
    for i in range(10):
        time.sleep(1)
        self.update_state(state='PROGRESS', meta={'current': i + 1, 'total': 10})
    logger.info("test_task completed.")
    return {"message": message, "status": "completed"}

@celery_app.task
def quick_test():
    """A quick task for basic testing."""
    logger.info("Executing quick_test task.")
    return {"status": "Quick test completed"}

@celery_app.task
def long_running_task(duration=30):
    """Long-running task for testing extended operations."""
    logger.info(f"Starting long_running_task for {duration} seconds.")
    time.sleep(duration)
    logger.info("long_running_task completed.")
    return {"status": f"Completed after {duration} seconds"}

@celery_app.task
def example_task(x: int, y: int) -> int:
    """An example task that adds two numbers."""
    logger.info(f"example_task started with arguments: {x}, {y}")
    time.sleep(5)
    result = x + y
    logger.info(f"example_task completed. Result: {result}")
    return result

# ----------------------------------------------------
# 🎮 RAWG Data Ingestion Tasks
# ----------------------------------------------------

@celery_app.task
def fetch_games_for_month_task(year: int, month: int) -> dict[str, str | int]:
    """Fetch and save games from RAWG API for a specified month."""

    async def _fetch_games_async():
        logger.info(f"Fetching games for {year}-{month:02d}...")
        games_data = await rawg_api.fetch_games_for_month(year, month)
        games_fetched = len(games_data)
        games_created = 0

        db = SessionLocal()
        try:
            for game_data in games_data:
                game = crud.get_game_by_slug(db, slug=game_data["slug"])
                if not game:
                    game_create = schemas.GameCreate(
                        id=game_data.get("id"),
                        slug=game_data.get("slug"),
                        name=game_data.get("name"),
                        released=game_data.get("released"),
                        rating=game_data.get("rating"),
                        ratings_count=game_data.get("ratings_count"),
                        metacritic=game_data.get("metacritic"),
                        playtime=game_data.get("playtime"),
                        genres=game_data.get("genres", []),
                        platforms=[p["platform"] for p in game_data.get("platforms", [])],
                        stores=[s["store"] for s in game_data.get("stores", [])],
                        tags=game_data.get("tags", []),
                    )
                    crud.create_game(db, game=game_create)
                    games_created += 1
                    logger.info(f"Created game: {game_data['name']}")
                else:
                    logger.info(f"Game already exists: {game_data['name']}")
        finally:
            db.close()

        logger.info(f"Completed fetching games for {year}-{month:02d}.")
        return {
            "status": "success",
            "games_fetched": games_fetched,
            "games_created": games_created,
            "year": year,
            "month": month,
        }

    return asyncio.run(_fetch_games_async())

@celery_app.task
def fetch_monthly_updates_task() -> dict[str, str | int]:
    """Fetch games for the previous month."""
    previous_month = (datetime.now().replace(day=1) - timedelta(days=1))
    return fetch_games_for_month_task(previous_month.year, previous_month.month)

@celery_app.task
def fetch_weekly_updates_task() -> dict[str, str | int]:
    """Fetch and update games from RAWG API that have updates in the last week."""

    async def _fetch_weekly_async():
        logger.info("Fetching recently updated games...")
        games_data = await rawg_api.fetch_recently_updated_games(days=7)
        games_fetched = len(games_data)
        games_created = 0
        games_updated = 0

        db = SessionLocal()
        try:
            for game_data in games_data:
                existing_game = crud.get_game_by_slug(db, slug=game_data["slug"])
                if existing_game:
                    game_update = schemas.GameUpdate(
                        rating=game_data.get("rating"),
                        ratings_count=game_data.get("ratings_count"),
                        metacritic=game_data.get("metacritic"),
                        playtime=game_data.get("playtime"),
                    )
                    crud.update_game(db, game_id=existing_game.id, game=game_update)
                    games_updated += 1
                    logger.info(f"Updated game: {game_data['name']}")
                else:
                    game_create = schemas.GameCreate(
                        id=game_data.get("id"),
                        slug=game_data.get("slug"),
                        name=game_data.get("name"),
                        released=game_data.get("released"),
                        rating=game_data.get("rating"),
                        ratings_count=game_data.get("ratings_count"),
                        metacritic=game_data.get("metacritic"),
                        playtime=game_data.get("playtime"),
                        genres=game_data.get("genres", []),
                        platforms=[p["platform"] for p in game_data.get("platforms", [])],
                        stores=[s["store"] for s in game_data.get("stores", [])],
                        tags=game_data.get("tags", []),
                    )
                    crud.create_game(db, game=game_create)
                    games_created += 1
                    logger.info(f"Created game: {game_data['name']}")
        finally:
            db.close()

        logger.info("Weekly update task completed.")
        return {
            "status": "success",
            "games_fetched": games_fetched,
            "games_created": games_created,
            "games_updated": games_updated,
        }

    return asyncio.run(_fetch_weekly_async())
