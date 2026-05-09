"""Vocal synthesis using additive sine waves with harmonics, ADSR, and formant filtering."""

import numpy as np

try:
    from scipy.signal import lfilter, butter
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

# Formant sets for different vowel sounds (F1, F2, F3 in Hz with bandwidths)
VOWEL_FORMANTS = {
    "ah": [(750, 120), (1200, 140), (2600, 220)],
    "ee": [(300, 80), (2200, 120), (3000, 200)],
    "oo": [(350, 80), (800, 100), (2500, 200)],
    "eh": [(550, 100), (1800, 130), (2600, 210)],
}
VOWEL_NAMES = list(VOWEL_FORMANTS.keys())


def adsr_envelope(
    num_samples: int,
    sample_rate: int,
    attack: float = 0.06,
    decay: float = 0.08,
    sustain_level: float = 0.65,
    release: float = 0.08,
) -> np.ndarray:
    """Generate ADSR amplitude envelope with softer, more natural onsets."""
    a = int(attack * sample_rate)
    d = int(decay * sample_rate)
    r = int(release * sample_rate)
    s = max(num_samples - a - d - r, 0)

    # Smooth exponential-ish attack for natural onset
    attack_curve = np.sqrt(np.linspace(0, 1, a)) if a > 0 else np.array([])
    decay_curve = np.linspace(1, sustain_level, d) if d > 0 else np.array([])
    sustain_curve = np.full(s, sustain_level)
    release_curve = sustain_level * np.sqrt(np.linspace(1, 0, r)) if r > 0 else np.array([])

    envelope = np.concatenate([attack_curve, decay_curve, sustain_curve, release_curve])
    if len(envelope) < num_samples:
        envelope = np.concatenate([envelope, np.zeros(num_samples - len(envelope))])
    return envelope[:num_samples]


class VocalSynthesizer:
    """Synthesizes vocal-like audio from pitch contours with formant filtering."""

    def __init__(self):
        self._vowel_index = 0

    def synthesize(
        self,
        pitch_contours: list[np.ndarray],
        sample_rate: int = 44100,
    ) -> np.ndarray:
        """Render pitch contours to audio using additive synthesis + formants."""
        audio = np.array([], dtype=np.float64)

        for idx, contour in enumerate(pitch_contours):
            num_samples = len(contour)

            # Handle breath gaps (zero-pitch contours from gamaka renderer)
            if np.all(contour == 0.0):
                audio = np.concatenate([audio, np.zeros(num_samples)])
                continue

            # Phase accumulation for smooth frequency changes
            phase = np.cumsum(2 * np.pi * contour / sample_rate)

            # --- Slight pitch drift for humanization ---
            drift = np.cumsum(np.random.randn(num_samples) * 0.0003)
            drift = np.clip(drift, -0.015, 0.015)
            phase *= (1.0 + drift)

            # Rich harmonic series for warm vocal tone
            signal = np.sin(phase)                            # fundamental
            signal += 0.50 * np.sin(2 * phase)                # 2nd harmonic
            signal += 0.25 * np.sin(3 * phase)                # 3rd
            signal += 0.12 * np.sin(4 * phase)                # 4th
            signal += 0.06 * np.sin(5 * phase)                # 5th
            signal += 0.03 * np.sin(6 * phase)                # 6th
            signal += 0.015 * np.sin(7 * phase)               # 7th

            # --- Breathy noise component (~5% mix) ---
            t = np.linspace(0, num_samples / sample_rate, num_samples, endpoint=False)
            noise = np.random.randn(num_samples) * 0.05
            # Bandpass the noise around the fundamental for a warm breath
            if HAS_SCIPY:
                avg_freq = np.mean(contour)
                nyq = sample_rate / 2.0
                low_n = max(avg_freq * 0.5 / nyq, 0.005)
                high_n = min(avg_freq * 3.0 / nyq, 0.995)
                if low_n < high_n:
                    b_n, a_n = butter(1, [low_n, high_n], btype='band')
                    noise = lfilter(b_n, a_n, noise) * 3.0  # boost filtered noise
            signal += noise

            # Apply ADSR envelope
            env = adsr_envelope(num_samples, sample_rate)
            signal *= env

            audio = np.concatenate([audio, signal])

        # Apply formant filtering for vocal warmth (with vowel variation)
        if HAS_SCIPY and len(audio) > 0:
            audio = self._apply_formants_varied(audio, sample_rate)

        # Normalize
        peak = np.max(np.abs(audio)) if len(audio) > 0 else 1
        if peak > 0:
            audio = audio / peak * 0.7
        return audio

    def _apply_formants_varied(self, signal: np.ndarray, sample_rate: int) -> np.ndarray:
        """Apply rotating vowel formant filtering for more natural sound."""
        total = len(signal)
        # Split signal into chunks and apply different vowel formants
        chunk_size = int(1.5 * sample_rate)  # rotate vowels every ~1.5 seconds
        output = np.zeros_like(signal)
        nyq = sample_rate / 2.0

        for start in range(0, total, chunk_size):
            end = min(start + chunk_size, total)
            chunk = signal[start:end]

            vowel = VOWEL_NAMES[self._vowel_index % len(VOWEL_NAMES)]
            self._vowel_index += 1
            formants = VOWEL_FORMANTS[vowel]

            filtered = np.zeros_like(chunk)
            for freq, bw in formants:
                low = max((freq - bw / 2) / nyq, 0.005)
                high = min((freq + bw / 2) / nyq, 0.995)
                if low >= high:
                    continue
                b, a = butter(2, [low, high], btype='band')
                filtered += lfilter(b, a, chunk) * 0.35

            # Blend: 30% original + 70% formant-filtered
            output[start:end] = chunk * 0.30 + filtered * 0.70

            # Crossfade at chunk boundaries to avoid clicks
            if start > 0:
                xfade = min(512, end - start)
                fade_in = np.linspace(0, 1, xfade)
                fade_out = np.linspace(1, 0, xfade)
                output[start:start + xfade] = (
                    output[start:start + xfade] * fade_in +
                    signal[start:start + xfade] * 0.3 * fade_out
                )

        return output
