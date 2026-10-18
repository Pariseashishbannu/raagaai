"""Load openly-licensed Hugging Face datasets as svara training sequences.

Only datasets whose license permits ML training are registered here. MIDI / note
datasets are Western music, so each melody chunk is transposed to whichever
(raga, tonic) fits it best and kept only if nearly all its notes fall in that raga.
That makes them useful for *pretraining* melodic structure; fine-tune afterwards
on Carnatic data (Saraga, synthetic, kaumudi-ragas).

Usage:
    from src.ml.data.hf_sources import HuggingFaceFetcher
    seqs = HuggingFaceFetcher().fetch("lakh", max_songs=5000)
"""

import json
import logging
import random
import re
from collections.abc import Iterable, Iterator
from pathlib import Path

from src.core.constants import SVARA_SEMITONES
from src.ml.data.scraper import (
    COMMON_RAGA_IDS,
    LocalRagaSynthesizer,
    parse_notation_string,
)

logger = logging.getLogger(__name__)

HF_SOURCES: dict[str, dict] = {
    "lakh": {
        "repo": "roszcz/lakh-lmd-full",
        "kind": "notes_parquet",
        "license": "CC-BY-4.0 (Lakh MIDI Dataset, Colin Raffel)",
        "size": "174k songs, ~9 GB (streamed)",
    },
    "maestro": {
        "repo": "roszcz/maestro-sustain-v2",
        "kind": "notes_parquet",
        "license": "CC-BY-NC-SA-4.0 (MAESTRO v2, Google Magenta) — non-commercial",
        "size": "1.3k piano performances, ~90 MB",
    },
    "classical-midi": {
        "repo": "drengskapur/midi-classical-music",
        "kind": "midi_files",
        "license": "MIT",
        "size": "4.8k MIDI files",
    },
    "kaumudi-ragas": {
        "repo": "kaumudi-ai/carnatic-ragas-talas",
        "kind": "raga_jsonl",
        "file": "carnatic-ragas-talas.jsonl",
        "license": "CC-BY-4.0 (kaumudi-ai)",
        "size": "small — raga scales + characteristic phrases",
    },
}

SECTIONS = ["pallavi", "anupallavi", "charanam", "chittaswaram"]

# Phrases written like "M2-P-D2" or "N3-S-R2-G3" inside free-text descriptions
_PHRASE_RE = re.compile(r"\b[SRGMPDN][1-3]?(?:-[SRGMPDN][1-3]?)+\b")


class HuggingFaceFetcher:
    def __init__(
        self,
        raga_data_dir: str = "data/ragas",
        min_coverage: float = 0.9,
        min_len: int = 16,
        max_len: int = 64,
    ):
        self.ragas = LocalRagaSynthesizer(raga_data_dir)._load_ragas()
        self.min_coverage = min_coverage
        self.min_len = min_len
        self.max_len = max_len
        self._build_raga_masks()

    def fetch(self, source: str, max_songs: int = 5000, per_raga: int = 200) -> list[dict]:
        if source not in HF_SOURCES:
            raise ValueError(f"unknown HF source {source!r}; choose from {list(HF_SOURCES)}")
        spec = HF_SOURCES[source]
        logger.info("HF %s (%s) — license: %s", source, spec["repo"], spec["license"])

        if spec["kind"] == "notes_parquet":
            seqs = self._from_note_rows(self._stream_note_rows(spec["repo"], max_songs))
        elif spec["kind"] == "midi_files":
            seqs = self._from_note_rows(self._iter_midi_files(spec["repo"], max_songs))
        else:
            seqs = self._from_raga_jsonl(spec["repo"], spec["file"], per_raga)

        for s in seqs:
            s["source"] = f"hf:{source}"
        logger.info("  → %d sequences from %s", len(seqs), source)
        return seqs

    # ── raga fitting ──

    def _build_raga_masks(self) -> None:
        import numpy as np

        self._raga_ids: list[str] = []
        self._pc_to_svara: list[dict[int, str]] = []
        masks = []
        for rid, raga in self.ragas.items():
            pc_map: dict[int, str] = {}
            for sv in raga.get("arohanam", []) + raga.get("avarohanam", []):
                if sv in SVARA_SEMITONES:
                    pc_map.setdefault(SVARA_SEMITONES[sv], sv)
            if len(pc_map) < 5:
                continue
            self._raga_ids.append(rid)
            self._pc_to_svara.append(pc_map)
            masks.append([1.0 if pc in pc_map else 0.0 for pc in range(12)])
        # Pitch classes follow SVARA_SEMITONES so synthesized output keeps the
        # melody's intervals
        self._masks = np.array(masks)                    # (R, 12)
        self._raga_sizes = self._masks.sum(axis=1)       # (R,)

    def _fit_chunk(self, pitches: list[int]) -> dict | None:
        """Pick the (raga, tonic shift) that covers the most notes; None if poor fit."""
        import numpy as np

        hist = np.bincount(np.array(pitches) % 12, minlength=12).astype(float)
        hist /= hist.sum()
        # shifted[t, pc] = share of notes at pitch class pc when the tonic is t
        shifted = np.stack([np.roll(hist, -t) for t in range(12)])     # (12, 12)
        coverage = shifted @ self._masks.T                               # (12, R)
        used = (shifted > 0).astype(float) @ self._masks.T
        # Prefer ragas whose svaras the melody actually uses, not loose supersets —
        # otherwise wide ragas (bhairavi spans 9 pitch classes) absorb everything
        score = coverage - 0.1 * (1 - used / self._raga_sizes) - 0.02 * self._raga_sizes
        t, r = np.unravel_index(np.argmax(score), score.shape)
        if coverage[t, r] < self.min_coverage:
            return None

        pc_map = self._pc_to_svara[r]
        svaras = [pc_map[(p - t) % 12] for p in pitches if (p - t) % 12 in pc_map]
        if len(svaras) < self.min_len:
            return None
        return {
            "raga_id": self._raga_ids[r],
            "section": random.choice(SECTIONS),
            "svaras": svaras,
        }

    # ── note datasets ──

    def _from_note_rows(self, rows: Iterable[tuple[list[int], list[float]]]) -> list[dict]:
        seqs: list[dict] = []
        for n_songs, (pitches, starts) in enumerate(rows, start=1):
            melody = _skyline(pitches, starts)
            i = 0
            while i + self.min_len <= len(melody):
                n = random.randint(self.min_len, self.max_len)
                fit = self._fit_chunk(melody[i:i + n])
                if fit:
                    seqs.append(fit)
                i += n
            if n_songs % 1000 == 0:
                logger.info("  %d songs → %d sequences", n_songs, len(seqs))
        return seqs

    @staticmethod
    def _stream_note_rows(repo: str, max_songs: int) -> Iterator[tuple[list[int], list[float]]]:
        from datasets import load_dataset

        ds = load_dataset(repo, split="train", streaming=True)
        for row in ds.take(max_songs):
            notes = row["notes"]
            yield notes["pitch"], notes["start"]

    @staticmethod
    def _iter_midi_files(repo: str, max_songs: int) -> Iterator[tuple[list[int], list[float]]]:
        import pretty_midi
        from huggingface_hub import hf_hub_download, list_repo_files

        files = [f for f in list_repo_files(repo, repo_type="dataset") if f.endswith(".mid")]
        random.shuffle(files)
        for fname in files[:max_songs]:
            try:
                path = hf_hub_download(repo, fname, repo_type="dataset")
                pm = pretty_midi.PrettyMIDI(path)
            except (OSError, ValueError, EOFError, IndexError, KeyError) as e:  # corrupt MIDIs
                logger.debug("skip %s: %s", fname, e)
                continue
            notes = [n for inst in pm.instruments if not inst.is_drum for n in inst.notes]
            yield [n.pitch for n in notes], [n.start for n in notes]

    # ── Carnatic raga metadata ──

    def _from_raga_jsonl(self, repo: str, filename: str, per_raga: int) -> list[dict]:
        from huggingface_hub import hf_hub_download

        path = hf_hub_download(repo, filename, repo_type="dataset")
        synth = LocalRagaSynthesizer()
        seqs: list[dict] = []
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            arohanam = parse_notation_string(row.get("arohana") or "")
            avarohanam = parse_notation_string(row.get("avarohana") or "")
            if len(arohanam) < 5 or len(avarohanam) < 5:
                continue  # tala rows, or malformed scales
            name = re.sub(r"[^a-z]", "", (row.get("name") or "").lower())
            raga_id = COMMON_RAGA_IDS.get(name, name)
            if not raga_id:
                continue
            phrases = [
                p for p in (
                    parse_notation_string(m.replace("-", " "))
                    for m in _PHRASE_RE.findall(row.get("characteristic_phrases") or "")
                ) if len(p) >= 3
            ]
            allowed = list(set(arohanam) | set(avarohanam))
            for _ in range(per_raga):
                seqs.append({
                    "raga_id": raga_id,
                    "section": random.choice(SECTIONS),
                    "svaras": synth._generate_sequence(
                        arohanam, avarohanam, allowed, phrases,
                        random.randint(self.min_len, self.max_len),
                    ),
                })
        return seqs


def _skyline(pitches: list[int], starts: list[float], onset_tol: float = 0.05) -> list[int]:
    """Reduce polyphony to a melody: highest pitch per onset cluster."""
    notes = sorted(
        (s, p) for p, s in zip(pitches, starts) if 36 <= p <= 96  # drop drum/extreme range
    )
    melody: list[int] = []
    cluster_start = None
    for s, p in notes:
        if cluster_start is None or s - cluster_start > onset_tol:
            melody.append(p)
            cluster_start = s
        elif p > melody[-1]:
            melody[-1] = p
    # Collapse immediate repeats — they come from re-struck chords, not melody
    return [p for i, p in enumerate(melody) if i == 0 or p != melody[i - 1]]
