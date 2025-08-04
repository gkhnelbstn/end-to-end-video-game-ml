import asyncio
from datetime import datetime
from src.worker.tasks import fetch_games_for_month_task


def backfill_data(start_year: int, end_year: int):
    """
    Triggers Celery tasks to backfill game data for a range of years.
    """
    print(f"Starting data backfill from {start_year} to {end_year}...")
    for year in range(start_year, end_year + 1):
        for month in range(1, 13):
            print(f"Triggering task for {year}-{month:02d}")
            fetch_games_for_month_task.delay(year, month)
    print("All backfill tasks have been triggered.")


if __name__ == "__main__":
    current_year = datetime.now().year
    # Example: Backfill data from 1980 to the current year
    backfill_data(1980, current_year)
