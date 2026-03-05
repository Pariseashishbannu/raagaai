"""Health check endpoints."""

from fastapi import APIRouter
import redis as redis_lib
from src.api.config import settings

router = APIRouter()


@router.get("")
async def health():
    """Liveness probe."""
    return {"status": "ok", "service": "raaga-ai"}


@router.get("/ready")
async def readiness():
    """Readiness probe — checks Redis connectivity."""
    checks = {}

    # Check Redis
    try:
        r = redis_lib.from_url(settings.REDIS_URL)
        r.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {e}"

    # Check MinIO
    try:
        from src.storage.client import get_client
        client = get_client()
        client.bucket_exists(settings.MINIO_BUCKET_AUDIO)
        checks["minio"] = "ok"
    except Exception as e:
        checks["minio"] = f"error: {e}"

    all_ok = all(v == "ok" for v in checks.values())
    return {"status": "ready" if all_ok else "degraded", "checks": checks}
