"""Main orchestrator task — runs the full L1-L5 pipeline."""

import json
import os
import redis as redis_lib
import structlog

from src.workers.celery_app import app
from src.storage.client import upload_audio
from src.workers.pipeline import run_pipeline

logger = structlog.get_logger()


def _update_status(job_id: str, status: str, stage: str | None, progress: float,
                   result: dict | None = None, error: str | None = None):
    """Update job status in Redis for polling."""
    r = redis_lib.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    data = {"status": status, "stage": stage, "progress": progress}
    if result:
        data["result"] = result
    if error:
        data["error"] = error
    r.setex(f"job:{job_id}", 7200, json.dumps(data))


@app.task(bind=True, name="generate_composition", max_retries=2)
def generate_composition_task(self, job_id: str, params: dict):
    """
    Full L1-L5 generation pipeline (see src/workers/pipeline.py).

    Stages:
      L1+L2: Validate raga/tala constraints
      L3: Generate svara sequences
      L4: Generate sahityam (lyrics)
      L5: Synthesize audio, then optionally re-perform it with ACE-Step
    """
    try:
        result = run_pipeline(job_id, params, _update_status, upload_audio)
        _update_status(job_id, "completed", None, 1.0, result=result)
        return result
    except Exception as e:
        logger.error("generation.failed", job_id=job_id, error=str(e))
        _update_status(job_id, "failed", None, 0.0, error=str(e))
        raise
