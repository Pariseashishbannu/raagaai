"""Build training dataset from all available Carnatic music data sources.

Usage:
    python -m scripts.build_dataset \\
        [--saraga-dir PATH] \\
        [--scrape-karnatik] [--scrape-shivkumar] [--max-web-pages N] \\
        [--dunya-token TOKEN | $DUNYA_TOKEN] [--dunya-recordings N]

Sources merged into a single JSONL:
  1. Synthetic sequences from local raga definitions (always)
  2. Saraga 1.5 annotations (--saraga-dir, see docs/SARAGA.md)
  3. karnatik.com krithi notations (--scrape-karnatik)
  4. shivkumar.org krithi notations (--scrape-shivkumar)
  5. CompMusic Dunya pitch contours (--dunya-token or DUNYA_TOKEN env var)
  6. Hugging Face datasets (--hf lakh maestro classical-midi kaumudi-ragas)
  7. Local audio recordings (--audio FILE_OR_DIR ...) via pitch tracking
  8. Pre-built sequence files (--include-jsonl FILE ...), e.g. audio extracted earlier
"""

import argparse
import json
import logging
import os
import random
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Build Carnatic svara training dataset")
    parser.add_argument(
        "--saraga-dir",
        type=str,
        default=None,
        help="Path to extracted Saraga Carnatic dataset",
    )
    parser.add_argument(
        "--scrape-web",
        action="store_true",
        help="(Alias for --scrape-karnatik, kept for backwards compatibility)",
    )
    parser.add_argument(
        "--scrape-karnatik",
        action="store_true",
        help="Scrape karnatik.com for composition notation",
    )
    parser.add_argument(
        "--scrape-shivkumar",
        action="store_true",
        help="Scrape shivkumar.org for krithi notation",
    )
    parser.add_argument(
        "--max-web-pages",
        type=int,
        default=50,
        help="Max pages to scrape per web source",
    )
    parser.add_argument(
        "--dunya-token",
        type=str,
        default=None,
        help="CompMusic Dunya API token (or set DUNYA_TOKEN env var)",
    )
    parser.add_argument(
        "--dunya-recordings",
        type=int,
        default=100,
        help="Max Dunya recordings to fetch",
    )
    parser.add_argument(
        "--hf",
        nargs="*",
        default=[],
        metavar="SOURCE",
        help="Hugging Face sources: lakh, maestro, classical-midi, kaumudi-ragas",
    )
    parser.add_argument(
        "--hf-max-songs",
        type=int,
        default=5000,
        help="Max songs/files to read per Hugging Face MIDI source",
    )
    parser.add_argument(
        "--audio",
        nargs="*",
        default=[],
        metavar="PATH",
        help="Audio files or folders (mp3/wav/flac/...) to pitch-track into svaras",
    )
    parser.add_argument(
        "--separate-vocals",
        action="store_true",
        help="Isolate vocals with demucs (if installed) before pitch tracking",
    )
    parser.add_argument(
        "--include-jsonl",
        nargs="*",
        default=[],
        metavar="FILE",
        help="Merge sequences from JSONL files built earlier (missing files are skipped)",
    )
    parser.add_argument(
        "--no-synthetic",
        action="store_true",
        help="Skip local synthetic sequences (e.g. for a MIDI-only pretraining set)",
    )
    parser.add_argument(
        "--synthetic-per-raga",
        type=int,
        default=200,
        help="Synthetic sequences to generate per raga",
    )
    parser.add_argument(
        "--no-augment",
        action="store_true",
        help="Skip data augmentation",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/training/svara_sequences.jsonl",
        help="Output JSONL file path",
    )
    args = parser.parse_args()

    from src.ml.data.scraper import (
        DunyaFetcher,
        KarnatikScraper,
        LocalRagaSynthesizer,
        SaragaScraper,
        ShivkumarScraper,
        augment_sequences,
    )

    all_sequences: list[dict] = []

    # 1. Synthetic sequences from local raga data
    if not args.no_synthetic:
        logger.info("Generating synthetic sequences from local raga definitions...")
        synth = LocalRagaSynthesizer("data/ragas")
        synthetic = synth.synthesize(sequences_per_raga=args.synthetic_per_raga)
        all_sequences.extend(synthetic)
        logger.info("  → %d synthetic sequences", len(synthetic))

    # 2. Saraga dataset (if available)
    if args.saraga_dir:
        logger.info("Parsing Saraga dataset from %s...", args.saraga_dir)
        saraga = SaragaScraper()
        saraga_seqs = saraga.scrape(args.saraga_dir)
        all_sequences.extend(saraga_seqs)
        logger.info("  → %d Saraga sequences", len(saraga_seqs))

    # 3. karnatik.com
    if args.scrape_web or args.scrape_karnatik:
        logger.info("Scraping karnatik.com (max %d pages)...", args.max_web_pages)
        karnatik = KarnatikScraper()
        web_seqs = karnatik.scrape(max_pages=args.max_web_pages)
        all_sequences.extend(web_seqs)
        logger.info("  → %d karnatik.com sequences", len(web_seqs))

    # 4. shivkumar.org
    if args.scrape_shivkumar:
        logger.info("Scraping shivkumar.org (max %d pages)...", args.max_web_pages)
        shiv = ShivkumarScraper()
        shiv_seqs = shiv.scrape(max_pages=args.max_web_pages)
        all_sequences.extend(shiv_seqs)
        logger.info("  → %d shivkumar.org sequences", len(shiv_seqs))

    # 5. Dunya API
    dunya_token = args.dunya_token or os.environ.get("DUNYA_TOKEN")
    if dunya_token:
        logger.info("Fetching from Dunya (max %d recordings)...", args.dunya_recordings)
        dunya = DunyaFetcher(dunya_token)
        dunya_seqs = dunya.fetch(max_recordings=args.dunya_recordings)
        all_sequences.extend(dunya_seqs)
        logger.info("  → %d Dunya sequences", len(dunya_seqs))

    # 6. Hugging Face datasets
    if args.hf:
        from src.ml.data.hf_sources import HuggingFaceFetcher

        hf = HuggingFaceFetcher()
        for source in args.hf:
            all_sequences.extend(hf.fetch(
                source, max_songs=args.hf_max_songs, per_raga=args.synthetic_per_raga,
            ))

    # 7. Local audio recordings
    if args.audio:
        from src.ml.data.audio_source import AudioFetcher

        all_sequences.extend(AudioFetcher(separate_vocals=args.separate_vocals).fetch(args.audio))

    # 8. Pre-built sequence files
    for jsonl in args.include_jsonl:
        path = Path(jsonl)
        if not path.exists():
            logger.warning("skipping missing %s", path)
            continue
        with open(path, encoding="utf-8") as f:
            included = [json.loads(line) for line in f if line.strip()]
        all_sequences.extend(included)
        logger.info("  → %d sequences from %s", len(included), path.name)

    if not all_sequences:
        logger.error("No sequences collected! Check data sources.")
        return

    # 4. Augment
    if not args.no_augment:
        logger.info("Augmenting %d sequences...", len(all_sequences))
        all_sequences = augment_sequences(all_sequences)
        logger.info("  → %d sequences after augmentation", len(all_sequences))

    # 5. Shuffle and save
    random.shuffle(all_sequences)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        for seq in all_sequences:
            f.write(json.dumps(seq, ensure_ascii=False) + "\n")

    logger.info("Saved %d sequences to %s", len(all_sequences), output_path)

    # Print stats
    raga_counts: dict[str, int] = {}
    section_counts: dict[str, int] = {}
    total_svaras = 0
    for seq in all_sequences:
        raga_counts[seq["raga_id"]] = raga_counts.get(seq["raga_id"], 0) + 1
        section_counts[seq["section"]] = section_counts.get(seq["section"], 0) + 1
        total_svaras += len(seq["svaras"])

    logger.info("Dataset stats:")
    logger.info("  Ragas: %d unique", len(raga_counts))
    logger.info("  Sections: %s", dict(section_counts))
    logger.info("  Total svaras: %d", total_svaras)
    logger.info("  Avg sequence length: %.1f", total_svaras / len(all_sequences))


if __name__ == "__main__":
    main()
