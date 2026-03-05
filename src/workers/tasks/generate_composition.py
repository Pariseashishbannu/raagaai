"""Main orchestrator task — runs the full L1-L5 pipeline."""

import json
import os
import redis as redis_lib
import structlog

from src.workers.celery_app import app
from src.constraint_engine.raga_engine import RagaEngine
from src.constraint_engine.tala_engine import TalaEngine
from src.ml.carnatic_gpt import CarnaticGPT
from src.sahityam.generator import SahityamGenerator
from src.synthesis.pipeline import SynthesisPipeline
from src.storage.client import upload_audio

logger = structlog.get_logger()

# Initialize engines once per worker process
_raga_engine = RagaEngine()
_tala_engine = TalaEngine()
_svara_gen = CarnaticGPT(_raga_engine, _tala_engine)
_sahityam_gen = SahityamGenerator()
_synth_pipeline = SynthesisPipeline()


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
    Full L1-L5 generation pipeline.

    Stages:
      L1+L2: Validate raga/tala constraints
      L3: Generate svara sequences
      L4: Generate sahityam (lyrics)
      L5: Synthesize audio
    """
    try:
        raga_id = params["raga_id"]
        tala_id = params["tala_id"]
        kala = params.get("kala", "madhyama")
        sections = params.get("sections", 3)
        theme = params.get("theme", "devotional")

        logger.info("generation.started", job_id=job_id, raga=raga_id, tala=tala_id)

        # ── L1 + L2: Constraint validation ──
        _update_status(job_id, "processing", "setting_up_raga", 0.1)
        raga = _raga_engine.get_raga(raga_id)
        if not raga:
            raise ValueError(f"Unknown raga: {raga_id}")

        tala = _tala_engine.get_tala(tala_id)
        if not tala:
            raise ValueError(f"Unknown tala: {tala_id}")

        logger.info("generation.constraints_ok", job_id=job_id)

        # ── L3: Svara generation ──
        _update_status(job_id, "processing", "composing_melody", 0.3)
        include_chitta = params.get("include_chittaswaram", False)
        section_results = _svara_gen.generate_full_composition(
            raga_id=raga_id,
            tala_id=tala_id,
            kala=kala,
            num_charanams=max(sections - 2, 1),
            include_chittaswaram=include_chitta,
        )

        # Convert to dict format
        svara_sections = {}
        for gs in section_results:
            key = gs.section
            if key in svara_sections:
                # Append number for duplicate section names
                count = sum(1 for k in svara_sections if k.startswith(key))
                key = f"{key}_{count + 1}"
            svara_sections[key] = gs.svaras

        # Flatten all svaras for sahityam
        all_svaras = []
        for gs in section_results:
            all_svaras.extend(gs.svaras)

        logger.info("generation.svaras_done", job_id=job_id, total_svaras=len(all_svaras))

        # ── L4: Sahityam / lyrics generation ──
        _update_status(job_id, "processing", "writing_lyrics", 0.5)
        song_result = _sahityam_gen.generate_song(
            svara_sections=svara_sections,
            raga_id=raga_id,
            theme=theme,
        )

        logger.info("generation.lyrics_done", job_id=job_id, title=song_result.title)

        # ── L5: Audio synthesis ──
        structure = params.get("structure", "song")
        use_vocoder = params.get("vocoder", None)
        _update_status(job_id, "processing", "producing_audio", 0.7)
        audio_output = _synth_pipeline.render(
            svara_sections=svara_sections,
            raga_id=raga_id,
            tala_id=tala_id,
            kala=kala,
            structure=structure,
            use_vocoder=use_vocoder,
        )

        logger.info("generation.audio_done", job_id=job_id,
                     duration=audio_output.duration_seconds)

        # ── Upload to MinIO ──
        _update_status(job_id, "processing", "uploading", 0.9)
        audio_key = upload_audio(job_id, audio_output.wav_bytes)

        # ── Build result ──
        result = {
            "audio_key": audio_key,
            "duration_seconds": audio_output.duration_seconds,
            "svara_sequence": audio_output.svara_sequence[:200],  # Truncate for Redis
            "sahityam": song_result.full_text,
            "sahityam_sections": song_result.sections,
            "song_title": song_result.title,
            "raga_id": raga_id,
            "tala_id": tala_id,
            "kala": kala,
        }

        _update_status(job_id, "completed", None, 1.0, result=result)
        logger.info("generation.completed", job_id=job_id)
        return result

    except Exception as e:
        logger.error("generation.failed", job_id=job_id, error=str(e))
        _update_status(job_id, "failed", None, 0.0, error=str(e))
        raise
