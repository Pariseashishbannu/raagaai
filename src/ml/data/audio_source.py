"""Turn local audio recordings into svara training sequences.

Pipeline per file: decode → (optional) vocal isolation → pYIN melody tracking →
note events → the same per-chunk raga + tonic fitting used for MIDI datasets
(HuggingFaceFetcher._fit_chunk), so only chunks that sit inside a raga are kept.

Full mixes (film songs) give noisy pitch: harmonic/percussive separation and a
vocal-range f0 search help, `demucs` vocal separation helps more if installed.
Only use recordings you have the right to use for training.
"""

import logging
import shutil
import subprocess
import tempfile
from collections.abc import Iterator
from pathlib import Path

import numpy as np

from src.ml.data.hf_sources import HuggingFaceFetcher

logger = logging.getLogger(__name__)

AUDIO_EXTS = {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".opus"}
SR = 16000
BLOCK_S = 60.0            # analyse in blocks to bound memory on long jukeboxes
MIN_NOTE_S = 0.08         # shorter pitch runs are glides/noise, not notes


class AudioFetcher:
    def __init__(self, fitter: HuggingFaceFetcher | None = None, separate_vocals: bool = False):
        # Pitch tracking on real recordings is noisier than MIDI, so allow a bit more
        # off-raga material per chunk (those notes are dropped, not kept)
        self.fitter = fitter or HuggingFaceFetcher(min_coverage=0.85)
        self.separate_vocals = separate_vocals and shutil.which("demucs") is not None
        if separate_vocals and not self.separate_vocals:
            logger.warning("demucs not installed — falling back to harmonic/percussive split")

    def fetch(self, paths: list[str]) -> list[dict]:
        files = list(_expand(paths))
        logger.info("audio: %d file(s)", len(files))
        seqs: list[dict] = []
        for f in files:
            file_seqs = self.fitter._from_note_rows(self._notes(f))
            for s in file_seqs:
                s["source"] = f"audio:{f.name}"
            logger.info("  %s → %d sequences", f.name, len(file_seqs))
            seqs.extend(file_seqs)
        return seqs

    def _notes(self, path: Path) -> Iterator[tuple[list[int], list[float]]]:
        """Yield (midi_pitches, onset_times) per analysis block."""
        import librosa

        src = self._isolate_vocals(path) if self.separate_vocals else path
        total = librosa.get_duration(path=str(src))
        for offset in np.arange(0.0, total, BLOCK_S):
            y, _ = librosa.load(str(src), sr=SR, mono=True, offset=float(offset), duration=BLOCK_S)
            if not self.separate_vocals:
                y = librosa.effects.harmonic(y, margin=3.0)   # drop drums/transients
            f0, voiced, _ = librosa.pyin(
                y, sr=SR, fmin=librosa.note_to_hz("C3"), fmax=librosa.note_to_hz("C6"),
                frame_length=1024,
            )
            hop_s = 256 / SR  # librosa default hop = frame_length // 4
            # pyin's own voicing decision; an extra probability cut discards ~90%
            # of sung frames in a full mix
            pitches, starts = _frames_to_notes(f0, voiced, hop_s)
            if pitches:
                yield pitches, [s + float(offset) for s in starts]

    @staticmethod
    def _isolate_vocals(path: Path) -> Path:
        out = Path(tempfile.mkdtemp(prefix="raaga_demucs_"))
        subprocess.run(
            ["demucs", "--two-stems=vocals", "-o", str(out), str(path)],
            check=True, capture_output=True,
        )
        return next(out.rglob("vocals.wav"))


def _frames_to_notes(
    f0: np.ndarray, voiced: np.ndarray, hop_s: float
) -> tuple[list[int], list[float]]:
    """Collapse frame-wise f0 into stable semitone notes."""
    from scipy.signal import medfilt

    midi = np.where(voiced, np.round(12 * np.log2(np.nan_to_num(f0, nan=1.0) / 440.0) + 69), -1)
    midi = medfilt(midi, 7)  # ~0.1 s: smooths vibrato/jitter that splits one note into many
    min_frames = max(1, int(MIN_NOTE_S / hop_s))
    pitches: list[int] = []
    starts: list[float] = []
    run_start = 0
    for i in range(1, len(midi) + 1):
        if i == len(midi) or midi[i] != midi[run_start]:
            if midi[run_start] >= 0 and i - run_start >= min_frames:
                pitches.append(int(midi[run_start]))
                starts.append(run_start * hop_s)
            run_start = i
    return pitches, starts


def _expand(paths: list[str]) -> Iterator[Path]:
    for p in map(Path, paths):
        if p.is_dir():
            yield from sorted(f for f in p.rglob("*") if f.suffix.lower() in AUDIO_EXTS)
        elif p.exists():
            yield p
        else:
            logger.warning("audio path not found: %s", p)
