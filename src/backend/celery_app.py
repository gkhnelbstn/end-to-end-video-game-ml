"""
Celery application setup for the Game Insight project.
"""
import os
from celery import Celery
from celery.signals import setup_logging as setup_celery_logging
from dotenv import load_dotenv
from .logging import setup_logging

# Load environment variables
load_dotenv()

@setup_celery_logging.connect
def setup_celery_logger(**kwargs):
    setup_logging()

# 🔑 Redis URL (Docker'da çalışan redis servisi)
REDIS_URL = os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/0")

# ✅ Celery uygulaması
celery_app = Celery(
    "game_insight",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=[
        "src.worker.tasks",  # ✅ Doğru modül yolu
    ],
)

# 🔥 REDBEAT: Dinamik schedule için
celery_app.conf.update(
    task_track_started=True,

    # 🔄 Dinamik scheduler (statik beat_schedule KALDIRILDI)
    beat_scheduler='redbeat.RedBeatScheduler',
    redbeat_redis_url=REDIS_URL,
    redbeat_lock_key='redbeat-lock',
    redbeat_lock_timeout=30,

    # 🧩 Kuyruk yapılandırması
    task_queues={
        "default": {"exchange": "default", "routing_key": "task.default"},
        "high_priority": {"exchange": "high_priority", "routing_key": "high.priority"},
    },
    task_default_queue="default",
)