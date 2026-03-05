"""Build training dataset from all available Carnatic music data sources.

Usage:
    python -m scripts.build_dataset [--saraga-dir PATH] [--scrape-web] [--max-web-pages N]

This script:
  1. Generates synthetic sequences from local raga definitions (always)
  2. Optionally parses Saraga dataset annotations (if --saraga-dir provided)
  3. Optionally scrapes karnatik.com (if --scrape-web flag set)
  4. Augments all sequences with transpositions and repetitions
  5. Saves to data/training/svara_sequences.jsonl
"""

import argparse
import json
import logging
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
        help="Scrape karnatik.com for composition notation",
    )
    parser.add_argument(
        "--max-web-pages",
        type=int,
        default=50,
        help="Max composition pages to scrape from karnatik.com",
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
        KarnatikScraper,
        LocalRagaSynthesizer,
        SaragaScraper,
        augment_sequences,
    )

    all_sequences: list[dict] = []

    # 1. Always generate synthetic sequences from local raga data
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

    # 3. Web scraping (if requested)
    if args.scrape_web:
        logger.info("Scraping karnatik.com (max %d pages)...", args.max_web_pages)
        karnatik = KarnatikScraper()
        web_seqs = karnatik.scrape(max_pages=args.max_web_pages)
        all_sequences.extend(web_seqs)
        logger.info("  → %d web-scraped sequences", len(web_seqs))

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
