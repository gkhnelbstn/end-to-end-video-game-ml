"""
Celery tasks for the Game Insight project.

This module contains the definitions of background tasks that are executed
by the Celery workers. This includes both ad-hoc tasks and scheduled tasks
for data ingestion.
"""
from src.backend.celery_app import celery_app
from src.worker import rawg_api
from src.backend import crud, schemas
from src.backend.database import SessionLocal
import time


@celery_app.task
def example_task(x: int, y: int) -> int:
    """
    An example task that adds two numbers.
    """
    time.sleep(5)
    return x + y


@celery_app.task
def fetch_games_for_month_task(year: int, month: int) -> dict[str, str | int]:
    """
    A Celery task to fetch and save all games for a specific month from the RAWG API.
    """
    print(f"Starting to fetch games for {year}-{month:02d}...")
    games_data = rawg_api.fetch_games_for_month(year, month)
    games_fetched = len(games_data)
    print(f"Successfully fetched {games_fetched} games for {year}-{month:02d}.")

    db = SessionLocal()
    games_created = 0
    for game_data in games_data:
        game = crud.get_game_by_slug(db, slug=game_data["slug"])
        if not game:
            game_schema = schemas.GameCreate(**game_data)
            crud.create_game(db, game=game_schema)
            games_created += 1
    db.close()

    print(f"Created {games_created} new games in the database.")
    return {
        "status": "success",
        "year": year,
        "month": month,
        "games_fetched": games_fetched,
        "games_created": games_created,
    }


@celery_app.task
def fetch_weekly_updates_task() -> dict[str, str | int]:
    """
    A Celery task to fetch and save/update games updated in the last week.
    """
    print("Starting to fetch weekly game updates...")
    games_data = rawg_api.fetch_recently_updated_games(days=7)
    games_fetched = len(games_data)
    print(f"Successfully fetched {games_fetched} recently updated games.")

    db = SessionLocal()
    games_created = 0
    games_updated = 0
    for game_data in games_data:
        game = crud.get_game_by_slug(db, slug=game_data["slug"])
        if not game:
            game_schema = schemas.GameCreate(**game_data)
            crud.create_game(db, game=game_schema)
            games_created += 1
        else:
            # Here you would implement the logic to update an existing game.
            # For now, we'll just count it as an update.
            games_updated += 1
    db.close()

    print(f"Created {games_created} new games and found {games_updated} existing games to update.")
    return {
        "status": "success",
        "games_fetched": games_fetched,
        "games_created": games_created,
        "games_updated": games_updated,
    }
