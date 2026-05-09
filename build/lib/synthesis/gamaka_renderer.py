"""Gamaka-aware pitch contour generation for Carnatic music."""

import numpy as np
from src.core.constants import SVARA_SEMITONES, DEFAULT_TONIC_HZ


def svara_to_hz(svara: str, tonic_hz: float = DEFAULT_TONIC_HZ, octave: int = 0) -> float:
    """Convert svara name to frequency in Hz using equal temperament."""
    semitones = SVARA_SEMITONES.get(svara, 0)
    return tonic_hz * (2.0 ** ((semitones + 12 * octave) / 12.0))


class GamakaRenderer:
    """Renders svara sequences into pitch contours with gamaka ornamentation."""

    def render(
        self,
        svaras: list[str],
        raga_id: str,
        kala: str,
        tonic_hz: float = DEFAULT_TONIC_HZ,
        beat_duration: float = 0.6,
        sample_rate: int = 44100,
    ) -> list[np.ndarray]:
        """Generate per-note pitch contours (Hz over time) with gamaka effects."""
        contours = []
        phrase_counter = 0
        # How many notes until the next breath gap
        phrase_length = np.random.randint(5, 9)

        for i, svara in enumerate(svaras):
            freq = svara_to_hz(svara, tonic_hz)

            # --- Rhythmic variety: vary note duration ---
            duration = beat_duration
            beat_in_group = i % 8  # approximate tala position
            if beat_in_group == 0:
                # Sam / strong beat — held slightly longer
                duration *= 1.2
            elif beat_in_group in (2, 4, 6):
                # Weaker subdivisions — slightly shorter
                duration *= 0.8
            elif np.random.random() < 0.12:
                # Occasional held note for expression
                duration *= 1.5

            num_samples = int(duration * sample_rate)
            t = np.linspace(0, duration, num_samples, endpoint=False)

            # Base pitch
            pitch = np.full(num_samples, freq)

            # --- Enhanced vibrato (kampita gamaka) ---
            vibrato_rate = 5.0 + np.random.uniform(-0.5, 0.5)
            vibrato_depth = freq * 0.012  # slightly deeper than before
            # Ramp up vibrato — starts subtle, builds during sustain
            ramp = np.clip(t / (duration * 0.35), 0.0, 1.0)
            pitch += vibrato_depth * ramp * np.sin(2 * np.pi * vibrato_rate * t)

            # --- Slide from previous note (jaru gamaka) ---
            if i > 0:
                prev_freq = svara_to_hz(svaras[i - 1], tonic_hz)
                interval_ratio = abs(prev_freq - freq) / freq
                if interval_ratio < 0.25:
                    # Wider slides for more expression
                    slide_frac = 0.06 if interval_ratio > 0.1 else 0.04
                    slide_len = min(int(slide_frac * sample_rate), num_samples // 3)
                    slide = np.linspace(prev_freq, freq, slide_len)
                    pitch[:slide_len] = slide

            contours.append(pitch)
            phrase_counter += 1

            # --- Breath gap: insert short silence between phrases ---
            if phrase_counter >= phrase_length:
                gap_duration = np.random.uniform(0.06, 0.15)
                gap_samples = int(gap_duration * sample_rate)
                # Use a very quiet pitch (will be near-silent after envelope)
                contours.append(np.full(gap_samples, 0.0))
                phrase_counter = 0
                phrase_length = np.random.randint(5, 9)

        return contours
