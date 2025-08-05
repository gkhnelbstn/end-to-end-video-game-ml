"""
Celery tasks for the Game Insight project.
"""
from src.backend.celery_app import celery_app  # ✅ Doğru import
from src.worker import rawg_api
from src.backend import crud, schemas
from src.backend.database import SessionLocal
import asyncio
from datetime import datetime, timedelta

# ❌ time.sleep kullanılmaz! Async değil.
# ✅ async uyumlu task tanımları

@celery_app.task
def example_task(x: int, y: int) -> int:
    """
    Example task (sync, test amaçlı)
    """
    return x + y


@celery_app.task
def fetch_games_for_month_task(year: int, month: int) -> dict:
    """
    Fetch and save games for a specific month.
    """
    print(f"Starting to fetch games for {year}-{month:02d}...")

    # ✅ asyncio.run doğru kullanılıyor
    games_data = asyncio.run(rawg_api.fetch_games_for_month(year, month))
    games_fetched = len(games_data)
    print(f"Fetched {games_fetched} games.")

    db = SessionLocal()
    games_created = 0
    try:
        for game_data in games_data:
            game = crud.get_game_by_slug(db, slug=game_data["slug"])
            if not game:
                game_create_data = {
                    "id": game_data.get("id"),
                    "slug": game_data.get("slug"),
                    "name": game_data.get("name"),
                    "released": game_data.get("released"),
                    "rating": game_data.get("rating"),
                    "ratings_count": game_data.get("ratings_count"),
                    "metacritic": game_data.get("metacritic"),
                    "playtime": game_data.get("playtime"),
                    "genres": [g["name"] for g in game_data.get("genres", [])],
                    "platforms": [p["platform"]["name"] for p in game_data.get("platforms", [])],
                    "stores": [s["store"]["name"] for s in game_data.get("stores", [])],
                    "tags": [t["name"] for t in game_data.get("tags", [])],
                }
                game_schema = schemas.GameCreate(**game_create_data)
                crud.create_game(db, game=game_schema)
                games_created += 1
    finally:
        db.close()

    print(f"Created {games_created} new games.")
    return {
        "status": "success",
        "year": year,
        "month": month,
        "games_fetched": games_fetched,
        "games_created": games_created,
    }


@celery_app.task
def fetch_monthly_updates_task() -> dict:
    """
    Fetch last month's games.
    """
    today = datetime.today()
    first_day = today.replace(day=1)
    last_month = first_day - timedelta(days=1)
    return fetch_games_for_month_task(last_month.year, last_month.month)


@celery_app.task
def fetch_weekly_updates_task() -> dict:
    """
    Fetch games updated in the last 7 days.
    """
    print("Fetching weekly updates...")
    games_data = asyncio.run(rawg_api.fetch_recently_updated_games(days=7))
    games_fetched = len(games_data)

    db = SessionLocal()
    games_created = 0
    games_updated = 0
    try:
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
                "genres": [g["name"] for g in game_data.get("genres", [])],
                "platforms": [p["platform"]["name"] for p in game_data.get("platforms", [])],
                "stores": [s["store"]["name"] for s in game_data.get("stores", [])],
                "tags": [t["name"] for t in game_data.get("tags", [])],
            }
            game_schema = schemas.GameCreate(**game_create_data)
            game = crud.get_game_by_slug(db, slug=game_data["slug"])
            if not game:
                crud.create_game(db, game=game_schema)
                games_created += 1
            else:
                crud.update_game(db, db_game=game, game_update=game_schema)
                games_updated += 1
    finally:
        db.close()

    print(f"Created: {games_created}, Updated: {games_updated}")
    return {
        "status": "success",
        "games_fetched": games_fetched,
        "games_created": games_created,
        "games_updated": games_updated,
    }