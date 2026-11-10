"""Queue one RAWG ingestion task per month for a range of years.

Usage: python -m src.scripts.backfill_data [START_YEAR] [END_YEAR]

Needs a running worker and a valid RAWG_API_KEY. The default range (1980 to now)
means hundreds of tasks and many thousands of API requests.
"""

import sys
from datetime import datetime

from src.worker.tasks import fetch_games_for_month_task


def backfill_data(start_year: int, end_year: int) -> None:
    now = datetime.now()
    queued = 0
    for year in range(start_year, end_year + 1):
        for month in range(1, 13):
            if (year, month) > (now.year, now.month):
                break
            fetch_games_for_month_task.delay(year, month)
            queued += 1
    print(f"Queued {queued} monthly tasks for {start_year}-{end_year}.")


if __name__ == "__main__":
    start = int(sys.argv[1]) if len(sys.argv) > 1 else 1980
    end = int(sys.argv[2]) if len(sys.argv) > 2 else datetime.now().year
    backfill_data(start, end)
