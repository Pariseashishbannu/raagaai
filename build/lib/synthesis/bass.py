"""Bass harmony layer — follows melody one octave below."""

import numpy as np


class BassLayer:
    """Generates a smooth bass track from pitch contours."""

    def generate(self, contours: list[np.ndarray], sample_rate: int = 44100) -> np.ndarray:
        """Generate bass one octave below the melody with smooth ADSR.

        Args:
            contours: List of pitch contour arrays (Hz values per sample) from GamakaRenderer.
            sample_rate: Audio sample rate.

        Returns:
            Bass audio signal as numpy array.
        """
        if not contours:
            return np.array([], dtype=np.float64)

        segments = []
        for contour in contours:
            if len(contour) == 0:
                continue

            # Get the root frequency (median of contour) and drop one octave
            root_hz = np.median(contour) / 2.0

            n = len(contour)
            t = np.arange(n) / sample_rate

            # Simple sine at the bass frequency
            phase = 2 * np.pi * root_hz * t
            signal = np.sin(phase)
            # Add subtle second harmonic for warmth
            signal += 0.2 * np.sin(2 * phase)

            # Gentle ADSR envelope
            envelope = self._envelope(n, sample_rate)
            signal *= envelope

            segments.append(signal)

        if not segments:
            return np.array([], dtype=np.float64)

        output = np.concatenate(segments)

        # Normalize
        peak = np.max(np.abs(output))
        if peak > 0:
            output = output / peak * 0.7

        return output

    def _envelope(self, n: int, sr: int) -> np.ndarray:
        """Gentle ADSR: slow attack, long sustain, smooth release."""
        attack = min(int(0.03 * sr), n // 4)
        release = min(int(0.03 * sr), n // 4)
        sustain_level = 0.8

        env = np.ones(n) * sustain_level
        if attack > 0:
            env[:attack] = np.linspace(0, sustain_level, attack)
        if release > 0:
            env[-release:] = np.linspace(sustain_level, 0.1, release)

        return env
