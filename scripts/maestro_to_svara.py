"""Convert MAESTRO v2.0.0 preprocessed .pt files to Carnatic svara training sequences.

MAESTRO contains tokenized MIDI piano performances. This script:
  1. Loads each .pt file (TorchScript module with int16 token tensor)
  2. Extracts MIDI note numbers (tokens 0-127)
  3. Maps MIDI notes to the nearest Carnatic svara (12-TET -> svara mapping)
  4. Segments into phrase-length chunks
  5. Assigns each chunk a raga based on best-fit arohanam/avarohanam match
  6. Outputs JSONL training data for SvaraTransformer

Usage:
    python -m scripts.maestro_to_svara [--maestro-dir PATH] [--output PATH]
"""

import argparse
import json
import logging
import random
from pathlib import Path
from collections import Counter

import torch

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# ── MIDI note number to svara mapping ──
# Carnatic svaras repeat every 12 semitones. We map pitch class (note % 12) to svara.
# Assuming Sa = C (pitch class 0). This is the standard mapping.
PITCH_CLASS_TO_SVARA = {
    0: "Sa",    # C
    1: "Ri1",   # C#/Db
    2: "Ri2",   # D
    3: "Ga2",   # D#/Eb
    4: "Ga2",   # E  (maps to Ga2 — closest)
    5: "Ma1",   # F
    6: "Ma2",   # F#/Gb
    7: "Pa",    # G
    8: "Da1",   # G#/Ab
    9: "Da2",   # A
    10: "Ni1",  # A#/Bb
    11: "Ni2",  # B
}

# Load raga definitions to match sequences to ragas
def load_ragas(raga_dir: str = "data/ragas") -> dict[str, dict]:
    ragas = {}
    for json_file in Path(raga_dir).glob("*.json"):
        with open(json_file, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            for rid, rdata in data.items():
                if "arohanam" in rdata:
                    ragas[rid] = rdata
        elif isinstance(data, list):
            for r in data:
                if "arohanam" in r:
                    ragas[r["id"]] = r
    return ragas


def midi_note_to_svara(midi_note: int) -> str:
    """Convert MIDI note number to Carnatic svara name."""
    pitch_class = midi_note % 12
    return PITCH_CLASS_TO_SVARA[pitch_class]


def extract_notes_from_pt(pt_path: str) -> list[int]:
    """Load a MAESTRO .pt file and extract MIDI note numbers."""
    model = torch.jit.load(pt_path, map_location="cpu")
    tokens = list(model.parameters())[0].flatten().tolist()
    # MIDI notes are tokens 0-127
    notes = [int(t) for t in tokens if 0 <= t <= 127]
    return notes


def score_raga_fit(svaras: list[str], raga: dict) -> float:
    """Score how well a svara sequence fits a raga (0.0 to 1.0)."""
    arohanam = set(raga.get("arohanam", []))
    avarohanam = set(raga.get("avarohanam", []))
    allowed = arohanam | avarohanam

    if not allowed:
        return 0.0

    svara_set = set(svaras)
    # Percentage of svaras in the sequence that are in the raga
    match_count = sum(1 for s in svaras if s in allowed)
    coverage = match_count / len(svaras) if svaras else 0

    # Bonus: check for characteristic phrase matches
    phrases = raga.get("characteristic_phrases", [])
    phrase_bonus = 0.0
    svara_str = " ".join(svaras)
    for phrase in phrases:
        phrase_str = " ".join(phrase)
        if phrase_str in svara_str:
            phrase_bonus += 0.1

    # Penalty: svaras outside the raga
    outside = sum(1 for s in svaras if s not in allowed)
    penalty = outside / len(svaras) if svaras else 0

    return min(1.0, coverage + phrase_bonus - penalty * 0.5)


def assign_raga(svaras: list[str], ragas: dict[str, dict]) -> tuple[str, float]:
    """Find the best matching raga for a svara sequence."""
    best_raga = "shankarabharanam"  # default fallback
    best_score = 0.0

    for raga_id, raga in ragas.items():
        score = score_raga_fit(svaras, raga)
        if score > best_score:
            best_score = score
            best_raga = raga_id

    return best_raga, best_score


def constrain_to_raga(svaras: list[str], raga: dict) -> list[str]:
    """Replace out-of-raga svaras with the nearest allowed svara."""
    arohanam = raga.get("arohanam", [])
    avarohanam = raga.get("avarohanam", [])
    allowed = list(set(arohanam) | set(avarohanam))

    if not allowed:
        return svaras

    ALL = ["Sa", "Ri1", "Ri2", "Ga1", "Ga2", "Ma1", "Ma2", "Pa", "Da1", "Da2", "Ni1", "Ni2"]

    def nearest_allowed(svara: str) -> str:
        if svara in allowed:
            return svara
        if svara not in ALL:
            return random.choice(allowed)
        idx = ALL.index(svara)
        # Search nearest
        for dist in range(1, 12):
            for delta in [dist, -dist]:
                candidate = ALL[(idx + delta) % len(ALL)]
                if candidate in allowed:
                    return candidate
        return allowed[0]

    return [nearest_allowed(s) for s in svaras]


def segment_notes(notes: list[int], min_len: int = 16, max_len: int = 64) -> list[list[int]]:
    """Split a note sequence into phrase-length chunks."""
    segments = []
    i = 0
    while i < len(notes):
        length = random.randint(min_len, max_len)
        chunk = notes[i:i + length]
        if len(chunk) >= min_len:
            segments.append(chunk)
        i += length
    return segments


def main():
    parser = argparse.ArgumentParser(description="Convert MAESTRO to Carnatic svara training data")
    parser.add_argument("--maestro-dir", type=str, default="maestro-v2.0.0")
    parser.add_argument("--raga-dir", type=str, default="data/ragas")
    parser.add_argument("--output", type=str, default="data/training/svara_sequences.jsonl")
    parser.add_argument("--min-score", type=float, default=0.5,
                        help="Minimum raga fit score to include a sequence")
    parser.add_argument("--max-files", type=int, default=0,
                        help="Max .pt files to process (0 = all)")
    parser.add_argument("--synthetic-per-raga", type=int, default=100,
                        help="Additional synthetic sequences per raga")
    args = parser.parse_args()

    # Load ragas
    ragas = load_ragas(args.raga_dir)
    logger.info("Loaded %d raga definitions", len(ragas))

    # Find all .pt files
    maestro_path = Path(args.maestro_dir)
    pt_files = sorted(maestro_path.rglob("*.pt"))
    if args.max_files > 0:
        pt_files = pt_files[:args.max_files]
    logger.info("Found %d .pt files in %s", len(pt_files), maestro_path)

    # Process files
    all_sequences: list[dict] = []
    sections = ["pallavi", "anupallavi", "charanam", "chittaswaram"]
    raga_counts: Counter = Counter()
    skipped = 0

    for fi, pt_file in enumerate(pt_files):
        if (fi + 1) % 100 == 0:
            logger.info("Processing %d/%d files... (%d sequences so far)",
                        fi + 1, len(pt_files), len(all_sequences))

        try:
            notes = extract_notes_from_pt(str(pt_file))
        except Exception:
            skipped += 1
            continue

        if len(notes) < 16:
            skipped += 1
            continue

        # Segment into phrase-length chunks
        segments = segment_notes(notes, min_len=16, max_len=64)

        for seg_notes in segments:
            # Convert MIDI notes to svaras
            raw_svaras = [midi_note_to_svara(n) for n in seg_notes]

            # Find best matching raga
            raga_id, score = assign_raga(raw_svaras, ragas)

            if score < args.min_score:
                # Try with constrained svaras
                raga_data = ragas.get(raga_id, {})
                constrained = constrain_to_raga(raw_svaras, raga_data)
                raga_id, score = assign_raga(constrained, ragas)
                svaras = constrained
            else:
                # Still constrain to ensure 100% validity
                raga_data = ragas.get(raga_id, {})
                svaras = constrain_to_raga(raw_svaras, raga_data)

            section = random.choice(sections)
            all_sequences.append({
                "raga_id": raga_id,
                "section": section,
                "svaras": svaras,
            })
            raga_counts[raga_id] += 1

    logger.info("Extracted %d sequences from MAESTRO (skipped %d files)", len(all_sequences), skipped)

    # Add synthetic sequences from local raga data for better coverage
    if args.synthetic_per_raga > 0:
        logger.info("Generating synthetic sequences (%d per raga)...", args.synthetic_per_raga)
        from src.ml.data.scraper import LocalRagaSynthesizer, augment_sequences
        synth = LocalRagaSynthesizer(args.raga_dir)
        synthetic = synth.synthesize(sequences_per_raga=args.synthetic_per_raga)
        all_sequences.extend(synthetic)
        logger.info("  Added %d synthetic sequences", len(synthetic))

    # Augment with transpositions and repetitions
    logger.info("Augmenting %d sequences...", len(all_sequences))
    from src.ml.data.scraper import augment_sequences
    all_sequences = augment_sequences(all_sequences)
    logger.info("  %d sequences after augmentation", len(all_sequences))

    # Shuffle
    random.shuffle(all_sequences)

    # Save
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        for seq in all_sequences:
            f.write(json.dumps(seq, ensure_ascii=False) + "\n")

    # Stats
    total_svaras = sum(len(s["svaras"]) for s in all_sequences)
    section_counts = Counter(s["section"] for s in all_sequences)
    raga_final = Counter(s["raga_id"] for s in all_sequences)

    logger.info("=" * 60)
    logger.info("DATASET COMPLETE")
    logger.info("=" * 60)
    logger.info("  Total sequences: %d", len(all_sequences))
    logger.info("  Total svaras: %d", total_svaras)
    logger.info("  Avg sequence length: %.1f", total_svaras / max(len(all_sequences), 1))
    logger.info("  Unique ragas: %d", len(raga_final))
    logger.info("  Top 10 ragas: %s", dict(raga_final.most_common(10)))
    logger.info("  Sections: %s", dict(section_counts))
    logger.info("  Saved to: %s", output_path)


if __name__ == "__main__":
    main()
