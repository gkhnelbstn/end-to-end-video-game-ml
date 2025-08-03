"""
Celery application setup for the Game Insight project.

This module configures the Celery instance that is used by the worker
and scheduler services. It sets up the broker and result backend using
environment variables, with sensible defaults for a Docker environment.

It also automatically discovers tasks from the modules listed in the `include`
list.
"""
import os
from celery import Celery
from dotenv import load_dotenv

# Load environment variables from a .env file, if it exists.
load_dotenv()

celery_app = Celery(
    "tasks",
    broker=os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/0"),
    backend=os.environ.get("CELERY_RESULT_BACKEND", "redis://redis:6379/0"),
    include=["src.worker.tasks"]
)

celery_app.conf.update(
    task_track_started=True,
)

# Optional: Configure periodic tasks (Celery Beat).
# This is where scheduled tasks can be defined.
# Example:
# celery_app.conf.beat_schedule = {
#     'fetch-games-every-hour': {
#         'task': 'src.worker.tasks.fetch_games',
#         'schedule': 3600.0,  # in seconds
#     },
# }
