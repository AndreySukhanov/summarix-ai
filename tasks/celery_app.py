"""
Celery app + beat schedule. Tasks use the SYNC db stack (get_db).
"""
from celery import Celery
from celery.schedules import crontab

from config.settings import settings

celery_app = Celery(
    "bot_tasks",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["tasks.scheduled"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    beat_schedule={
        "expire-subscriptions": {
            "task": "tasks.scheduled.expire_subscriptions",
            "schedule": crontab(hour=1, minute=0),  # daily 01:00 UTC
        },
        "reset-monthly-usage": {
            "task": "tasks.scheduled.reset_monthly_usage",
            "schedule": crontab(day_of_month=1, hour=0, minute=10),
        },
    },
)
