"""Generate one raga-locked song from the command line (same path the app uses).

Raaga.AI composes and renders a guide track; an ACE-Step 1.5 API server re-performs
it with realistic vocals; candidates are ranked by raga adherence.

Start an ACE-Step server first (notebooks/acestep_server_colab.ipynb or
`make acestep-local`), then:

    ACESTEP_API_URL=https://xxxx.trycloudflare.com ACESTEP_API_KEY=... \\
        python -m scripts.hybrid_song --raga mohanam --theme devotional --out-dir out/
"""

import argparse
import json
import logging
from pathlib import Path

from src.api.config import settings
from src.workers.pipeline import run_pipeline

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Raga-locked song via ACE-Step 1.5")
    parser.add_argument("--raga", default="mohanam")
    parser.add_argument("--tala", default="adi")
    parser.add_argument("--kala", default="madhyama", choices=["vilamba", "madhyama", "druta"])
    parser.add_argument("--theme", default="devotional",
                        choices=["devotional", "romantic", "nature", "celebration", "melancholy"])
    parser.add_argument("--language", default="telugu")
    parser.add_argument("--sections", type=int, default=4, help="Total sections (≥3)")
    parser.add_argument("--voice", default="female", choices=["female", "male"])
    parser.add_argument("--strength", type=float, default=0.7,
                        help="audio_cover_strength: higher = closer to the raga guide")
    parser.add_argument("--candidates", type=int, default=None,
                        help="Renders to rank (default: ACESTEP_CANDIDATES)")
    parser.add_argument("--out-dir", type=Path, default=Path("out/hybrid"))
    args = parser.parse_args()

    if not settings.ACESTEP_API_URL:
        raise SystemExit("set ACESTEP_API_URL (and ACESTEP_API_KEY) to an ACE-Step server")
    if args.candidates:
        settings.ACESTEP_CANDIDATES = args.candidates
    args.out_dir.mkdir(parents=True, exist_ok=True)

    def save(_job_id: str, wav_bytes: bytes, filename: str) -> str:
        path = args.out_dir / filename
        path.write_bytes(wav_bytes)
        return str(path)

    def status(_job_id: str, _status: str, stage: str | None, progress: float) -> None:
        if stage:
            logger.info("[%3.0f%%] %s", progress * 100, stage)

    result = run_pipeline("cli", {
        "raga_id": args.raga, "tala_id": args.tala, "kala": args.kala,
        "theme": args.theme, "language": args.language, "sections": args.sections,
        "structure": "song", "realistic": True, "voice": args.voice,
        "cover_strength": args.strength,
    }, status, save)

    (args.out_dir / "song.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    if result["performed_by"] != "ace-step":
        logger.warning("ACE-Step failed — %s is the synth guide only", result["audio_key"])
    else:
        logger.info("raga score %.3f (guide %.3f) → %s",
                    result["raga_score"], result["guide_raga_score"], result["audio_key"])


if __name__ == "__main__":
    main()
