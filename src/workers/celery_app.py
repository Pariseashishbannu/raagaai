"""Celery application configuration."""

import os
from celery import Celery

app = Celery("raaga")

app.config_from_object({
    "broker_url": os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    "result_backend": os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1"),
    "task_serializer": "json",
    "result_serializer": "json",
    "accept_content": ["json"],
    "task_track_started": True,
    "task_acks_late": True,
    "worker_prefetch_multiplier": 1,
    "task_routes": {
        "generate_composition": {"queue": "generation"},
    },
})

app.autodiscover_tasks(["src.workers.tasks"])

# Explicit import to ensure task registration
import src.workers.tasks.generate_composition  # noqa: F401, E402
