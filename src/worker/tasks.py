"""
Celery tasks for the Game Insight project.

This module contains the definitions of background tasks that are executed
by the Celery workers. This includes both ad-hoc tasks and scheduled tasks
for data ingestion.
"""
from src.backend.celery_app import celery_app
from src.worker import rawg_api
import time


@celery_app.task
def example_task(x: int, y: int) -> int:
    """
    An example task that adds two numbers.

    This is a simple task to demonstrate Celery functionality and for testing
    purposes. It simulates a delay to represent a long-running operation.

    Args:
        x: The first number.
        y: The second number.

    Returns:
        The sum of x and y.
    """
    time.sleep(5)
    return x + y


@celery_app.task
def fetch_games_for_year_task(year: int) -> dict[str, str | int]:
    """
    A Celery task to fetch all games for a specific year from the RAWG API.

    This task wraps the `fetch_games_for_year` function from the `rawg_api`
    module, allowing it to be executed asynchronously by a Celery worker.

    Args:
        year: The year to fetch games for.

    Returns:
        A dictionary with the status and the number of games fetched.
    """
    print(f"Starting to fetch games for the year {year}...")
    games = rawg_api.fetch_games_for_year(year)
    games_fetched = len(games)
    print(f"Successfully fetched {games_fetched} games for the year {year}.")

    # In a real application, you would save the `games` data to the database here.
    # For now, we just return a status message.

    return {"status": "success", "year": year, "games_fetched": games_fetched}
