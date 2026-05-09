"""Celery task error handlers and retry logic."""

import structlog
from src.workers.celery_app import app

logger = structlog.get_logger()


@app.task(name="on_generation_failure")
def on_generation_failure(request, exc, traceback):
    """Handle generation task failures after all retries exhausted."""
    logger.error(
        "generation.dead_letter",
        task_id=request.id,
        exception=str(exc),
    )
