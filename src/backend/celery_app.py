"""Celery application shared by the API (to enqueue tasks) and the worker."""

from celery import Celery
from celery.signals import setup_logging as setup_celery_logging

from . import config
from .logger_config import setup_logging


@setup_celery_logging.connect
def setup_celery_logger(**kwargs):
    """Use the same structured JSON logging as the API."""
    setup_logging()


celery_app = Celery(
    "tasks",
    broker=config.CELERY_BROKER_URL,
    backend=config.CELERY_RESULT_BACKEND,
    include=["src.worker.tasks"],
)

celery_app.conf.update(
    task_track_started=True,
    broker_connection_retry_on_startup=True,
)
