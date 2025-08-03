"""
Celery tasks for the Game Insight project.

This module contains the definitions of background tasks that are executed
by the Celery workers. This includes both ad-hoc tasks and scheduled tasks
for data ingestion.
"""
from src.backend.celery_app import celery_app
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
    time.sleep(5)  # Simulate a long-running task
    return x + y


@celery_app.task
def fetch_games() -> dict[str, str | int]:
    """
    Fetches game data from the RAWG API.

    This is a placeholder for the main data ingestion task. In the future,
    this task will handle the logic for connecting to the RAWG API, fetching
    new or updated game data, and storing it in the database.
    """
    # This is where the logic to fetch data from RAWG API will go.
    print("Fetching game data from RAWG API...")
    time.sleep(10)  # Simulate API call
    print("Data fetching complete.")
    return {"status": "success", "games_fetched": 100}
