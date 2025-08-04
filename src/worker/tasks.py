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
            # Prepare the data for GameCreate schema
            game_create_data = {
                "id": game_data.get("id"),
                "slug": game_data.get("slug"),
                "name": game_data.get("name"),
                "released": game_data.get("released"),
                "rating": game_data.get("rating"),
                "ratings_count": game_data.get("ratings_count"),
                "metacritic": game_data.get("metacritic"),
                "playtime": game_data.get("playtime"),
                "genres": game_data.get("genres", []),
                "platforms": [p["platform"] for p in game_data.get("platforms", [])],
                "stores": [s["store"] for s in game_data.get("stores", [])],
                "tags": game_data.get("tags", []),
            }
            game_schema = schemas.GameCreate(**game_create_data)
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


from datetime import datetime, timedelta

@celery_app.task
def fetch_monthly_updates_task() -> dict[str, str | int]:
    """
    A Celery task to fetch and save all games for the previous month.
    """
    today = datetime.today()
    first_day_of_current_month = today.replace(day=1)
    last_day_of_previous_month = first_day_of_current_month - timedelta(days=1)
    year = last_day_of_previous_month.year
    month = last_day_of_previous_month.month
    return fetch_games_for_month_task(year, month)


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
        game_create_data = {
            "id": game_data.get("id"),
            "slug": game_data.get("slug"),
            "name": game_data.get("name"),
            "released": game_data.get("released"),
            "rating": game_data.get("rating"),
            "ratings_count": game_data.get("ratings_count"),
            "metacritic": game_data.get("metacritic"),
            "playtime": game_data.get("playtime"),
            "genres": game_data.get("genres", []),
            "platforms": [p["platform"] for p in game_data.get("platforms", [])],
            "stores": [s["store"] for s in game_data.get("stores", [])],
            "tags": game_data.get("tags", []),
        }
        game_schema = schemas.GameCreate(**game_create_data)

        game = crud.get_game_by_slug(db, slug=game_data["slug"])
        if not game:
            crud.create_game(db, game=game_schema)
            games_created += 1
        else:
            crud.update_game(db, db_game=game, game_update=game_schema)
            games_updated += 1
    db.close()

    print(f"Created {games_created} new games and updated {games_updated} existing games.")
    return {
        "status": "success",
        "games_fetched": games_fetched,
        "games_created": games_created,
        "games_updated": games_updated,
    }
