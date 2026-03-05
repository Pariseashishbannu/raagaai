"""MinIO/S3 object storage client."""

import io
from datetime import timedelta
from minio import Minio
from src.api.config import settings

_client: Minio | None = None


def init_storage():
    """Initialize MinIO client and ensure buckets exist."""
    import urllib3
    global _client

    http = urllib3.PoolManager(
        timeout=urllib3.Timeout(connect=2.0, read=2.0),
        retries=urllib3.Retry(total=0),
    )
    _client = Minio(
        settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_SECURE,
        http_client=http,
    )
    for bucket in [settings.MINIO_BUCKET_AUDIO, settings.MINIO_BUCKET_CHECKPOINTS]:
        if not _client.bucket_exists(bucket):
            _client.make_bucket(bucket)


def get_client() -> Minio:
    global _client
    if _client is None:
        init_storage()
    return _client


def upload_audio(job_id: str, wav_bytes: bytes, filename: str = "composition.wav") -> str:
    """Upload WAV to MinIO. Returns the object key."""
    client = get_client()
    key = f"compositions/{job_id}/{filename}"
    client.put_object(
        settings.MINIO_BUCKET_AUDIO,
        key,
        io.BytesIO(wav_bytes),
        length=len(wav_bytes),
        content_type="audio/wav",
    )
    return key


def get_presigned_url(bucket: str, key: str, expires_hours: int = 1) -> str:
    """Generate a presigned download URL."""
    client = get_client()
    return client.presigned_get_object(bucket, key, expires=timedelta(hours=expires_hours))


def upload_checkpoint(job_id: str, stage: str, data: bytes) -> str:
    """Upload pipeline checkpoint data."""
    client = get_client()
    key = f"checkpoints/{job_id}/{stage}.json"
    client.put_object(
        settings.MINIO_BUCKET_CHECKPOINTS,
        key,
        io.BytesIO(data),
        length=len(data),
        content_type="application/json",
    )
    return key
