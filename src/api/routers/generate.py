"""Generation endpoints — submit jobs and poll status.

In development mode (no Celery worker), runs generation synchronously
in a background thread to avoid needing a separate worker process.
"""

import json
import logging
import os
import threading
import uuid
from datetime import datetime, timezone

import redis as redis_lib
from fastapi import APIRouter, HTTPException, Depends

from src.api.config import settings
from src.api.schemas.generation import (
    GenerationRequest,
    GenerationResponse,
    JobStatus,
    CompositionResult,
    Kala,
)
from src.api.middleware.auth import get_current_user_optional
from src.api.dependencies import get_raga_engine, get_tala_engine
from src.api.prompt_parser import PromptParser

logger = logging.getLogger(__name__)

_prompt_parser = PromptParser()

router = APIRouter()


def _has_celery_workers() -> bool:
    """Check if any Celery workers are connected."""
    try:
        from src.workers.celery_app import app as celery_app
        inspect = celery_app.control.inspect(timeout=1.0)
        active = inspect.active_queues()
        return bool(active)
    except Exception:
        return False


def _save_local(job_id: str, wav_bytes: bytes, filename: str) -> str:
    """Dev-mode storage: data/audio/<job_id>/<filename>, served by the audio route."""
    audio_dir = os.path.join("data", "audio", job_id)
    os.makedirs(audio_dir, exist_ok=True)
    with open(os.path.join(audio_dir, filename), "wb") as f:
        f.write(wav_bytes)
    return f"{job_id}/{filename}"


def _run_sync(job_id: str, params: dict) -> None:
    """Run the generation pipeline synchronously in a thread."""
    from src.workers.pipeline import run_pipeline
    from src.workers.tasks.generate_composition import _update_status

    try:
        result = run_pipeline(job_id, params, _update_status, _save_local)
        _update_status(job_id, "completed", None, 1.0, result=result)
    except Exception as e:
        logger.error("generation.failed job_id=%s error=%s", job_id, e)
        _update_status(job_id, "failed", None, 0.0, error=str(e))


def _audio_url(audio_key: str) -> str:
    """Local file if it exists (dev/sync mode), otherwise a MinIO presigned URL."""
    if os.path.exists(os.path.join("data", "audio", audio_key)):
        return f"/api/v1/audio/{audio_key}"
    try:
        from src.storage.client import get_presigned_url
        return get_presigned_url(settings.MINIO_BUCKET_AUDIO, audio_key)
    except Exception:
        return f"/api/v1/audio/{audio_key}"


@router.post("", response_model=GenerationResponse)
async def submit_generation(
    req: GenerationRequest,
    user: dict | None = Depends(get_current_user_optional),
):
    """Submit a new composition generation job."""
    # Parse prompt if provided
    if req.prompt:
        parsed = _prompt_parser.parse(req.prompt)
        req.raga_id = parsed["raga_id"]
        req.tala_id = parsed.get("tala_id", req.tala_id)
        req.kala = Kala(parsed.get("kala", req.kala.value))
        if req.theme is None:
            req.theme = parsed["theme"]

    if req.theme is None:
        req.theme = "romantic"

    # Validate raga and tala exist
    raga_engine = get_raga_engine()
    tala_engine = get_tala_engine()

    raga = raga_engine.get_raga(req.raga_id)
    if not raga:
        raise HTTPException(404, f"Raga '{req.raga_id}' not found")

    tala = tala_engine.get_tala(req.tala_id)
    if not tala:
        raise HTTPException(404, f"Tala '{req.tala_id}' not found")

    job_id = str(uuid.uuid4())

    # Set initial status in Redis
    r = redis_lib.from_url(settings.REDIS_URL)
    r.setex(
        f"job:{job_id}",
        7200,
        json.dumps({"status": "queued", "stage": None, "progress": 0.0}),
    )

    params = req.model_dump()
    if user:
        params["user_id"] = user["user_id"]

    # Try Celery first, fall back to sync thread if no workers available
    if _has_celery_workers():
        from src.workers.tasks.generate_composition import generate_composition_task
        generate_composition_task.delay(job_id, params)
    else:
        logger.info("No Celery workers — running generation synchronously")
        thread = threading.Thread(target=_run_sync, args=(job_id, params), daemon=True)
        thread.start()

    return GenerationResponse(
        job_id=job_id,
        status="queued",
        estimated_wait=30,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


@router.get("/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str):
    """Poll job status and get result when completed."""
    r = redis_lib.from_url(settings.REDIS_URL)
    data = r.get(f"job:{job_id}")
    if not data:
        raise HTTPException(404, "Job not found")

    job_data = json.loads(data)

    result = None
    if job_data.get("result"):
        res = job_data["result"]
        guide_key = res.get("guide_audio_key")
        result = CompositionResult(
            audio_url=_audio_url(res.get("audio_key", "")),
            guide_audio_url=_audio_url(guide_key) if guide_key else None,
            raga_score=res.get("raga_score"),
            song_title=res.get("song_title"),
            sahityam=res.get("sahityam"),
            sahityam_sections=res.get("sahityam_sections"),
            svara_sequence=res.get("svara_sequence"),
            metadata={
                "raga_id": res.get("raga_id"),
                "tala_id": res.get("tala_id"),
                "kala": res.get("kala"),
                "duration_seconds": res.get("duration_seconds"),
                "performed_by": res.get("performed_by", "synth"),
                "guide_raga_score": res.get("guide_raga_score"),
            },
        )

    return JobStatus(
        job_id=job_id,
        status=job_data["status"],
        stage=job_data.get("stage"),
        progress=job_data.get("progress"),
        result=result,
        error=job_data.get("error"),
    )


@router.delete("/{job_id}")
async def cancel_job(job_id: str):
    """Cancel a pending/processing job."""
    r = redis_lib.from_url(settings.REDIS_URL)
    data = r.get(f"job:{job_id}")
    if not data:
        raise HTTPException(404, "Job not found")

    job_data = json.loads(data)
    if job_data["status"] in ("completed", "failed"):
        raise HTTPException(400, "Cannot cancel a completed/failed job")

    job_data["status"] = "cancelled"
    r.setex(f"job:{job_id}", 7200, json.dumps(job_data))
    return {"job_id": job_id, "status": "cancelled"}
