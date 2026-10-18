"""Raga-locked hybrid song: Raaga.AI composes, ACE-Step 1.5 performs.

  1. L1–L4 as usual — raga-valid svaras per section + Telugu sahityam
  2. L5 renders a guide track (synth vocal + tambura + percussion)
  3. ACE-Step "cover" re-performs the guide with realistic vocals and a band,
     singing our lyrics; audio_cover_strength keeps it close to the guide melody
  4. Each candidate is pitch-tracked and scored for raga adherence; best one wins

Needs a CUDA GPU and ACE-Step 1.5 installed (see notebooks/hybrid_song_colab.ipynb).

Usage:
    python -m scripts.hybrid_song --raga mohanam --theme devotional \\
        --ace-root /content/ACE-Step-1.5 --candidates 4 --out-dir out/
"""

import argparse
import json
import logging
import random
from pathlib import Path

import numpy as np
import soundfile as sf

from src.constraint_engine.raga_engine import RagaEngine
from src.constraint_engine.tala_engine import TalaEngine
from src.core.constants import DEFAULT_TONIC_HZ, KALA_BPM, Kala
from src.ml.carnatic_gpt import CarnaticGPT
from src.sahityam.generator import SahityamGenerator
from src.synthesis.pipeline import SynthesisPipeline, song_arrangement
from src.synthesis.raga_adherence import raga_pitch_classes, score_audio

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# ACE-Step structure tags for each song-mode segment
SEGMENT_TAGS = {
    "intro": "[intro]",
    "pallavi": "[verse]",
    "anupallavi": "[chorus]",
    "charanam": "[verse]",
    "chittaswaram": "[bridge]",
    "outro": "[outro]",
}

RASA_MOODS = {
    "shringara": "romantic", "karuna": "tender, compassionate", "bhakti": "devotional",
    "shanta": "peaceful, meditative", "veera": "heroic, majestic", "hasya": "joyful",
    "adbhuta": "wondrous", "raudra": "intense", "bhayanaka": "dark, tense",
}

LANGUAGE_CODES = {"telugu": "te", "tamil": "ta", "kannada": "unknown"}


def build_lyric_sheet(svara_sections: dict[str, list[str]], lyrics: dict[str, str]) -> str:
    """Lyrics in the exact order the guide track performs the sections."""
    lines: list[str] = []
    for label, key in song_arrangement(svara_sections):
        lines.append(SEGMENT_TAGS.get(label, "[verse]"))
        if label not in ("intro", "outro") and lyrics.get(key):
            lines.append(lyrics[key])
        lines.append("")
    return "\n".join(lines).strip()


def build_caption(raga, tala, kala: str, theme: str | None, voice: str, extra: str) -> str:
    moods = [RASA_MOODS[r] for r in raga.rasa_tags if r in RASA_MOODS]
    if theme:
        moods.insert(0, theme)
    moods = list(dict.fromkeys(moods))  # theme often repeats a rasa mood
    parts = [
        f"Carnatic classical song in raga {raga.name_english}, {tala.name} tala, {kala} tempo",
        ", ".join(moods) if moods else "",
        f"expressive {voice} Indian classical vocals with gamakas",
        "violin, veena, bamboo flute, mridangam, tanpura drone",
        "warm studio production",
        extra,
    ]
    return ", ".join(p for p in parts if p)[:512]


def compose(args) -> tuple[dict, object, object, dict, object]:
    """L1–L5: returns svara sections, raga, tala, song lyrics, guide audio."""
    raga_engine, tala_engine = RagaEngine(), TalaEngine()
    raga = raga_engine.get_raga(args.raga)
    tala = tala_engine.get_tala(args.tala)
    if not raga or not tala:
        raise SystemExit(f"unknown raga {args.raga!r} or tala {args.tala!r}")

    sections = CarnaticGPT(raga_engine, tala_engine).generate_full_composition(
        raga_id=raga.id, tala_id=tala.id, kala=args.kala,
        num_charanams=args.charanams, include_chittaswaram=args.chittaswaram,
    )
    # Same duplicate-name handling as the Celery task
    svara_sections: dict[str, list[str]] = {}
    for gs in sections:
        key = gs.section
        if key in svara_sections:
            key = f"{key}_{sum(1 for k in svara_sections if k.startswith(key)) + 1}"
        svara_sections[key] = gs.svaras

    song = SahityamGenerator().generate_song(
        svara_sections=svara_sections, raga_id=raga.id, theme=args.theme,
    )
    guide = SynthesisPipeline().render(
        svara_sections=svara_sections, raga_id=raga.id, tala_id=tala.id,
        kala=args.kala, structure="song",
    )
    return svara_sections, raga, tala, song, guide


def perform(args, guide_path: Path, caption: str, lyrics: str, bpm: int) -> list[dict]:
    """ACE-Step cover of the guide track; returns its audio dicts."""
    from acestep.handler import AceStepHandler
    from acestep.inference import GenerationConfig, GenerationParams, generate_music

    dit = AceStepHandler()
    dit.initialize_service(
        project_root=args.ace_root, config_path=args.ace_config,
        device="cuda", offload_to_cpu=args.offload,
    )
    params = GenerationParams(
        task_type="cover",
        src_audio=str(guide_path),
        caption=caption,
        lyrics=lyrics,
        vocal_language=LANGUAGE_CODES.get(args.language, "unknown"),
        bpm=bpm,
        keyscale="",  # ragas aren't western keys; the guide audio carries the pitch
        audio_cover_strength=args.strength,
        thinking=False,  # the 5Hz LM is skipped for cover tasks anyway
    )
    config = GenerationConfig(
        batch_size=args.candidates,
        use_random_seed=args.seed is None,
        seeds=None if args.seed is None else [args.seed + i for i in range(args.candidates)],
        audio_format="wav",
    )
    # llm_handler=None is supported: cover tasks never call the LM
    result = generate_music(dit, None, params, config, save_dir=str(args.out_dir / "candidates"))
    if not result.success:
        raise SystemExit(f"ACE-Step failed: {result.error}")
    return result.audios


def main():
    parser = argparse.ArgumentParser(description="Raga-locked hybrid song via ACE-Step 1.5")
    parser.add_argument("--raga", default="mohanam")
    parser.add_argument("--tala", default="adi")
    parser.add_argument("--kala", default="madhyama", choices=[k.value for k in Kala])
    parser.add_argument("--theme", default="devotional",
                        choices=["devotional", "romantic", "nature", "celebration", "melancholy"])
    parser.add_argument("--language", default="telugu")
    parser.add_argument("--charanams", type=int, default=2)
    parser.add_argument("--chittaswaram", action="store_true")
    parser.add_argument("--voice", default="female", choices=["female", "male"])
    parser.add_argument("--style", default="", help="Extra caption text, e.g. 'film song'")
    parser.add_argument("--candidates", type=int, default=4, help="Renders to rank")
    parser.add_argument("--strength", type=float, default=0.7,
                        help="audio_cover_strength: higher = closer to guide melody")
    parser.add_argument("--max-drop", type=float, default=0.1,
                        help="Warn if the best candidate scores this far below the guide "
                             "(gamaka slides keep even the guide below 1.0)")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--ace-root", required=True, help="Path to the ACE-Step-1.5 checkout")
    parser.add_argument("--ace-config", default="acestep-v15-turbo")
    parser.add_argument("--offload", action="store_true", help="CPU offload (low VRAM)")
    parser.add_argument("--out-dir", type=Path, default=Path("out/hybrid"))
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)
        np.random.seed(args.seed)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    # ── Compose (L1–L5) ──
    svara_sections, raga, tala, song, guide = compose(args)
    guide_path = args.out_dir / "guide.wav"
    guide_path.write_bytes(guide.wav_bytes)
    lyrics = build_lyric_sheet(svara_sections, song.sections)
    caption = build_caption(raga, tala, args.kala, args.theme, args.voice, args.style)
    bpm = KALA_BPM[Kala(args.kala)]
    logger.info("composed '%s' in %s — guide %ds", song.title, raga.name_english,
                guide.duration_seconds)
    logger.info("caption: %s", caption)

    # ── Perform (ACE-Step cover) ──
    audios = perform(args, guide_path, caption, lyrics, bpm)

    # ── Raga lock: rank candidates by adherence ──
    allowed = raga_pitch_classes(raga.arohanam, raga.avarohanam)
    guide_audio, guide_sr = sf.read(guide_path)
    guide_score = score_audio(guide_audio, guide_sr, allowed, DEFAULT_TONIC_HZ).score
    ranked = []
    for a in audios:
        rep = score_audio(a["tensor"].numpy(), a["sample_rate"], allowed, DEFAULT_TONIC_HZ)
        ranked.append((rep, a))
        logger.info("candidate %s: raga score %.3f (voiced %.0f%%, shift %+d, off-raga %s)",
                    Path(a["path"]).name, rep.score, rep.voiced_ratio * 100,
                    rep.tonic_shift, rep.off_raga)
    ranked.sort(key=lambda x: x[0].score, reverse=True)
    best_rep, best = ranked[0]

    final_path = args.out_dir / "song.wav"
    sf.write(final_path, best["tensor"].numpy().T, best["sample_rate"])
    (args.out_dir / "song.json").write_text(json.dumps({
        "title": song.title,
        "raga": raga.id,
        "tala": tala.id,
        "kala": args.kala,
        "caption": caption,
        "lyrics": lyrics,
        "svara_sections": svara_sections,
        "raga_score": round(best_rep.score, 3),
        "guide_raga_score": round(guide_score, 3),
        "candidate_scores": [round(r.score, 3) for r, _ in ranked],
        "seed": best["params"].get("seed"),
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info("best raga score %.3f (guide %.3f) → %s", best_rep.score, guide_score, final_path)
    if best_rep.score < guide_score - args.max_drop:
        logger.warning("drifted from the raga — try a higher --strength or more --candidates")


if __name__ == "__main__":
    main()
