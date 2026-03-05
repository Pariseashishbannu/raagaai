"""Training data collection for future Carnatic-specific vocoder fine-tuning.

Saves generation artifacts (vocal waveform, pitch contours, metadata) to MinIO
for building a Carnatic music dataset. Gated by COLLECT_TRAINING_DATA setting.
"""

import io
import json

import numpy as np
import soundfile as sf
import structlog

from src.api.config import settings
from src.storage.client import get_client

logger = structlog.get_logger()

BUCKET = settings.MINIO_BUCKET_TRAINING


def save_training_pair(
    job_id: str,
    vocal_waveform: np.ndarray,
    pitch_contours: list[np.ndarray],
    metadata: dict,
    sample_rate: int = 44100,
) -> None:
    """Save a vocal + pitch contour pair for future model training.

    Stored in MinIO under training-data/{job_id}/:
      - vocal.wav — the raw vocal waveform
      - pitch_contours.npy — pitch contour arrays
      - metadata.json — raga, tala, kala, svara info
    """
    if not settings.COLLECT_TRAINING_DATA:
        return

    try:
        client = get_client()
        prefix = f"training-data/{job_id}"

        # Ensure bucket exists
        if not client.bucket_exists(BUCKET):
            client.make_bucket(BUCKET)

        # Save vocal WAV
        wav_buf = io.BytesIO()
        pcm = (vocal_waveform * 32767).astype(np.int16)
        sf.write(wav_buf, pcm, sample_rate, format="WAV", subtype="PCM_16")
        wav_bytes = wav_buf.getvalue()
        client.put_object(
            BUCKET,
            f"{prefix}/vocal.wav",
            io.BytesIO(wav_bytes),
            length=len(wav_bytes),
            content_type="audio/wav",
        )

        # Save pitch contours as numpy archive
        contour_buf = io.BytesIO()
        np.savez_compressed(contour_buf, *pitch_contours)
        contour_bytes = contour_buf.getvalue()
        client.put_object(
            BUCKET,
            f"{prefix}/pitch_contours.npz",
            io.BytesIO(contour_bytes),
            length=len(contour_bytes),
            content_type="application/octet-stream",
        )

        # Save metadata JSON
        meta_bytes = json.dumps(metadata, indent=2).encode()
        client.put_object(
            BUCKET,
            f"{prefix}/metadata.json",
            io.BytesIO(meta_bytes),
            length=len(meta_bytes),
            content_type="application/json",
        )

        logger.info("training_data.saved", job_id=job_id, prefix=prefix)

    except Exception:
        logger.warning("training_data.save_failed", job_id=job_id, exc_info=True)
