"""The L1–L5 generation pipeline, shared by the Celery task and the no-worker fallback.

Callers differ only in how they report status and where audio is stored, so both
are passed in.
"""

from collections.abc import Callable

import structlog

from src.constraint_engine.raga_engine import RagaEngine
from src.constraint_engine.tala_engine import TalaEngine
from src.ml.carnatic_gpt import CarnaticGPT
from src.sahityam.generator import SahityamGenerator
from src.synthesis.performer import perform_song
from src.synthesis.pipeline import SynthesisPipeline

logger = structlog.get_logger()

# (job_id, status, stage, progress) -> None
StatusFn = Callable[[str, str, str | None, float], None]
# (job_id, wav_bytes, filename) -> storage key
SaveFn = Callable[[str, bytes, str], str]

# Initialize engines once per process
_raga_engine = RagaEngine()
_tala_engine = TalaEngine()
_svara_gen = CarnaticGPT(_raga_engine, _tala_engine)
_sahityam_gen = SahityamGenerator()
_synth_pipeline = SynthesisPipeline()


def run_pipeline(job_id: str, params: dict, update_status: StatusFn, save_audio: SaveFn) -> dict:
    """Run L1–L5 (+ optional ACE-Step performance) and return the job result dict."""
    raga_id = params["raga_id"]
    tala_id = params["tala_id"]
    kala = params.get("kala", "madhyama")
    sections = params.get("sections", 3)
    theme = params.get("theme", "devotional")

    logger.info("generation.started", job_id=job_id, raga=raga_id, tala=tala_id)

    # ── L1 + L2: Constraint validation ──
    update_status(job_id, "processing", "setting_up_raga", 0.1)
    raga = _raga_engine.get_raga(raga_id)
    if not raga:
        raise ValueError(f"Unknown raga: {raga_id}")
    tala = _tala_engine.get_tala(tala_id)
    if not tala:
        raise ValueError(f"Unknown tala: {tala_id}")

    # ── L3: Svara generation ──
    update_status(job_id, "processing", "composing_melody", 0.3)
    section_results = _svara_gen.generate_full_composition(
        raga_id=raga_id,
        tala_id=tala_id,
        kala=kala,
        num_charanams=max(sections - 2, 1),
        include_chittaswaram=params.get("include_chittaswaram", False),
    )
    svara_sections: dict[str, list[str]] = {}
    for gs in section_results:
        key = gs.section
        if key in svara_sections:
            # Append number for duplicate section names
            count = sum(1 for k in svara_sections if k.startswith(key))
            key = f"{key}_{count + 1}"
        svara_sections[key] = gs.svaras
    logger.info("generation.svaras_done", job_id=job_id,
                total_svaras=sum(len(s) for s in svara_sections.values()))

    # ── L4: Sahityam / lyrics generation ──
    update_status(job_id, "processing", "writing_lyrics", 0.5)
    song_result = _sahityam_gen.generate_song(
        svara_sections=svara_sections, raga_id=raga_id, theme=theme,
    )

    # ── L5: Audio synthesis (the raga-correct guide) ──
    update_status(job_id, "processing", "producing_audio", 0.7)
    audio_output = _synth_pipeline.render(
        svara_sections=svara_sections,
        raga_id=raga_id,
        tala_id=tala_id,
        kala=kala,
        structure=params.get("structure", "song"),
        use_vocoder=params.get("vocoder", None),
    )

    # ── L5b: Realistic performance via ACE-Step (falls back to the guide) ──
    performed = None
    if params.get("realistic", True):
        update_status(job_id, "processing", "performing", 0.8)
        performed = perform_song(
            guide_wav=audio_output.wav_bytes,
            svara_sections=svara_sections,
            lyrics_sections=song_result.sections,
            raga=raga,
            tala=tala,
            kala=kala,
            theme=theme,
            language=params.get("language", "telugu"),
            voice=params.get("voice", "female"),
            strength=params.get("cover_strength", 0.7),
        )

    update_status(job_id, "processing", "uploading", 0.9)
    result = {
        "svara_sequence": audio_output.svara_sequence[:200],  # Truncate for Redis
        "sahityam": song_result.full_text,
        "sahityam_sections": song_result.sections,
        "song_title": song_result.title,
        "raga_id": raga_id,
        "tala_id": tala_id,
        "kala": kala,
    }
    if performed:
        result.update({
            "audio_key": save_audio(job_id, performed.wav_bytes, "composition.wav"),
            "guide_audio_key": save_audio(job_id, audio_output.wav_bytes, "guide.wav"),
            "duration_seconds": performed.duration_seconds,
            "raga_score": performed.raga_score,
            "guide_raga_score": performed.guide_raga_score,
            "performed_by": "ace-step",
        })
    else:
        result.update({
            "audio_key": save_audio(job_id, audio_output.wav_bytes, "composition.wav"),
            "duration_seconds": audio_output.duration_seconds,
            "performed_by": "synth",
        })

    logger.info("generation.completed", job_id=job_id, performed_by=result["performed_by"])
    return result
