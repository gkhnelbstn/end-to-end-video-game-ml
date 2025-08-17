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
from celery.signals import setup_logging as setup_celery_logging
from dotenv import load_dotenv
from .logger_config import setup_logging

# Load environment variables from a .env file, if it exists.
load_dotenv()

@setup_celery_logging.connect
def setup_celery_logger(**kwargs):
    """
    Set up structured logging for Celery workers.
    """
    setup_logging()


celery_app = Celery(
    "tasks",
    broker=os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/0"),
    backend=os.environ.get("CELERY_RESULT_BACKEND", "redis://redis:6379/0"),
    include=["src.worker.tasks"]
)

celery_app.conf.update(
    task_track_started=True,
)

from celery.schedules import crontab

# celery_app.conf.beat_schedule = {
#     'fetch-monthly-updates': {
#         'task': 'src.worker.tasks.fetch_monthly_updates_task',
#         'schedule': crontab(day_of_month='1', hour=0, minute=0),
#     },
#     'fetch-weekly-updates': {
#         'task': 'src.worker.tasks.fetch_weekly_updates_task',
#         'schedule': crontab(day_of_week='monday', hour=0, minute=0),
#     },
# }
