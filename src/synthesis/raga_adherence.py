"""Measure how closely rendered audio stays inside a raga's svaras.

Used to rank neural-render candidates (e.g. ACE-Step covers of the guide track):
pitch-track the audio, fold each voiced frame onto the 12 svara positions relative
to the tonic, and count how much of the time is spent on svaras the raga allows.
"""

from dataclasses import dataclass

import numpy as np

from src.core.constants import DEFAULT_TONIC_HZ, SVARA_SEMITONES


@dataclass
class AdherenceReport:
    score: float                       # share of voiced time on allowed svaras (0–1)
    voiced_ratio: float                # share of frames with a detectable pitch
    tonic_shift: int                   # semitones the audio sits from the expected tonic
    off_raga: dict[int, float]         # semitone → share of voiced time, for disallowed ones


def raga_pitch_classes(arohanam: list[str], avarohanam: list[str]) -> set[int]:
    return {SVARA_SEMITONES[s] for s in arohanam + avarohanam if s in SVARA_SEMITONES}


def score_audio(
    audio: np.ndarray,
    sample_rate: int,
    allowed: set[int],
    tonic_hz: float = DEFAULT_TONIC_HZ,
    allow_transpose: bool = True,
) -> AdherenceReport:
    """Score mono or (channels, samples) audio against a raga's allowed pitch classes.

    allow_transpose: a neural render may move the whole song by a few semitones;
    that keeps the raga intact, so score at the best whole-song shift (±2 semitones
    only — larger shifts can turn one raga into another mode).
    """
    import librosa

    if audio.ndim > 1:
        audio = audio.mean(axis=0)
    # pyin is slow at 44.1 kHz; 16 kHz is plenty for vocal f0
    y = librosa.resample(audio.astype(np.float32), orig_sr=sample_rate, target_sr=16000)
    f0, voiced, _ = librosa.pyin(
        y, fmin=librosa.note_to_hz("C2"), fmax=librosa.note_to_hz("C6"), sr=16000
    )
    f0 = f0[voiced & ~np.isnan(f0)]
    voiced_ratio = float(len(f0)) / max(len(voiced), 1)
    if len(f0) == 0:
        return AdherenceReport(0.0, 0.0, 0, {})

    pcs = np.round(12 * np.log2(f0 / tonic_hz)).astype(int) % 12
    hist = np.bincount(pcs, minlength=12) / len(pcs)

    shifts = range(-2, 3) if allow_transpose else [0]
    mask = np.array([1.0 if pc in allowed else 0.0 for pc in range(12)])
    best = max(shifts, key=lambda t: float(np.roll(hist, -t) @ mask))
    rolled = np.roll(hist, -best)
    return AdherenceReport(
        score=float(rolled @ mask),
        voiced_ratio=voiced_ratio,
        tonic_shift=best,
        off_raga={pc: round(float(rolled[pc]), 3) for pc in range(12)
                  if pc not in allowed and rolled[pc] > 0.01},
    )
