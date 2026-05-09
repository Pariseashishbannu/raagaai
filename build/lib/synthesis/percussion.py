"""Percussion/rhythm track synthesizer — physically-modeled mridangam strokes."""

import numpy as np


class PercussionSynthesizer:
    """Generates a rhythmic percussion track from tala structure using mridangam models."""

    TALA_BEATS = {
        "adi": 8,
        "rupaka": 3,
        "misra_chapu": 7,
        "khanda_chapu": 5,
        "triputa": 7,
        "ata": 5,
        "dhruva": 7,
    }

    # Stress patterns per tala (1.0 = sam, 0.7 = strong, 0.4 = medium, 0.2 = weak)
    STRESS_PATTERNS = {
        "adi": [1.0, 0.2, 0.4, 0.2, 0.7, 0.2, 0.4, 0.2],
        "rupaka": [1.0, 0.4, 0.7],
        "misra_chapu": [1.0, 0.2, 0.4, 0.7, 0.2, 0.4, 0.2],
        "khanda_chapu": [1.0, 0.2, 0.7, 0.2, 0.4],
        "triputa": [1.0, 0.2, 0.4, 0.2, 0.7, 0.4, 0.2],
        "ata": [1.0, 0.2, 0.7, 0.2, 0.4],
        "dhruva": [1.0, 0.2, 0.4, 0.7, 0.2, 0.4, 0.2],
    }

    KALA_BPM = {
        "vilamba": 60,
        "madhyama": 100,
        "druta": 140,
    }

    def generate(self, tala_id: str, total_samples: int, kala: str = "madhyama",
                 sample_rate: int = 44100) -> np.ndarray:
        """Generate a percussion track matching the given duration with humanization."""
        bpm = self.KALA_BPM.get(kala, 100)
        beat_duration = 60.0 / bpm
        beats_per_cycle = self.TALA_BEATS.get(tala_id, 8)
        stress_pattern = self.STRESS_PATTERNS.get(tala_id, [1.0, 0.2, 0.4, 0.2])

        output = np.zeros(total_samples, dtype=np.float64)
        duration_sec = total_samples / sample_rate

        beat_idx = 0
        t = 0.0
        while t < duration_sec:
            pos_in_cycle = beat_idx % beats_per_cycle
            stress = stress_pattern[pos_in_cycle % len(stress_pattern)]

            # Humanization: ±5% timing jitter
            jitter = np.random.uniform(-0.05, 0.05) * beat_duration
            sample_start = int((t + jitter) * sample_rate)
            sample_start = max(0, sample_start)

            if sample_start >= total_samples:
                break

            # Humanization: ±8% velocity variation
            vel_variation = 1.0 + np.random.uniform(-0.08, 0.08)

            if stress >= 0.9:
                # Sam beat — thoppi (bass membrane)
                sound = self._thoppi(sample_rate, amplitude=0.8 * vel_variation)
            elif stress >= 0.6:
                # Strong beat — valanthalai (treble membrane)
                sound = self._valanthalai(sample_rate, amplitude=0.5 * vel_variation)
            elif stress >= 0.35:
                # Medium beat — chapu/nam (slap)
                sound = self._chapu_nam(sample_rate, amplitude=0.35 * vel_variation)
            else:
                # Weak beat — ta/di (finger stroke)
                sound = self._ta_di(sample_rate, amplitude=0.18 * vel_variation)

            end = min(sample_start + len(sound), total_samples)
            length = end - sample_start
            output[sample_start:end] += sound[:length]

            t += beat_duration
            beat_idx += 1

        # Normalize
        peak = np.max(np.abs(output))
        if peak > 0:
            output = output / peak * 0.85

        return output

    def _thoppi(self, sr: int, amplitude: float = 0.8) -> np.ndarray:
        """Bass head (thoppi) — circular membrane model with inharmonic modes.

        Uses the first 4 modes of a circular membrane (Bessel function zeros):
        1.00, 1.59, 2.14, 2.65 × fundamental.
        """
        duration = 0.18
        n = int(sr * duration)
        t = np.linspace(0, duration, n, endpoint=False)

        fundamental = 85.0  # bass membrane fundamental
        # Inharmonic mode ratios for circular membrane
        mode_ratios = [1.0, 1.593, 2.136, 2.653]
        mode_amps = [1.0, 0.6, 0.35, 0.15]
        # Each mode decays at a different rate (higher modes decay faster)
        mode_decays = [18.0, 28.0, 42.0, 60.0]

        signal = np.zeros(n, dtype=np.float64)
        for ratio, amp, dec in zip(mode_ratios, mode_amps, mode_decays):
            freq = fundamental * ratio
            envelope = np.exp(-t * dec)
            signal += amp * np.sin(2 * np.pi * freq * t) * envelope

        # Add a low-frequency body thump — pitch-dropping transient
        thump_freq = 120.0 * np.exp(-t * 25) + 40.0
        thump_phase = 2 * np.pi * np.cumsum(thump_freq) / sr
        thump = 0.5 * np.sin(thump_phase) * np.exp(-t * 22)
        signal += thump

        # Soft clipping for warmth
        signal = np.tanh(signal * 1.5) / 1.5

        return amplitude * signal

    def _valanthalai(self, sr: int, amplitude: float = 0.5) -> np.ndarray:
        """Treble head (valanthalai) — higher membrane with karanai paste harmonic effect.

        The karanai paste on the center constrains vibration to produce
        a more harmonic series (unlike the bass head).
        """
        duration = 0.12
        n = int(sr * duration)
        t = np.linspace(0, duration, n, endpoint=False)

        fundamental = 280.0  # treble membrane
        # Near-harmonic series (karanai effect makes modes more harmonic)
        harmonics = [1.0, 2.0, 3.02, 4.05, 5.1]
        harm_amps = [1.0, 0.7, 0.4, 0.2, 0.08]
        harm_decays = [30.0, 45.0, 65.0, 90.0, 120.0]

        signal = np.zeros(n, dtype=np.float64)
        for h, amp, dec in zip(harmonics, harm_amps, harm_decays):
            freq = fundamental * h
            envelope = np.exp(-t * dec)
            signal += amp * np.sin(2 * np.pi * freq * t) * envelope

        # Sharp transient click at onset
        click_dur = min(int(0.003 * sr), n)
        if click_dur > 0:
            click = np.random.randn(click_dur) * 0.3
            click *= np.exp(-np.linspace(0, 8, click_dur))
            signal[:click_dur] += click

        return amplitude * signal

    def _chapu_nam(self, sr: int, amplitude: float = 0.35) -> np.ndarray:
        """Chapu/Nam — sharp edge slap with transient noise and pitched ring."""
        duration = 0.06
        n = int(sr * duration)
        t = np.linspace(0, duration, n, endpoint=False)

        # Noise burst transient (skin slap)
        noise = np.random.randn(n)
        # Bandpass the noise around 1–4 kHz for a sharp slap character
        noise_env = np.exp(-t * 80)
        slap = noise * noise_env * 0.6

        # Short pitched ring from membrane
        ring_freq = 420.0
        ring = 0.4 * np.sin(2 * np.pi * ring_freq * t) * np.exp(-t * 60)

        # Click transient
        click_len = min(int(0.002 * sr), n)
        click = np.zeros(n)
        if click_len > 0:
            click[:click_len] = np.linspace(0.8, 0, click_len)

        signal = slap + ring + click

        return amplitude * signal

    def _ta_di(self, sr: int, amplitude: float = 0.18) -> np.ndarray:
        """Ta/Di — soft finger stroke on membrane edge."""
        duration = 0.04
        n = int(sr * duration)
        t = np.linspace(0, duration, n, endpoint=False)

        # Very short, soft membrane excitation
        fundamental = 350.0
        signal = np.sin(2 * np.pi * fundamental * t) * np.exp(-t * 70)
        # Slight 2nd mode
        signal += 0.3 * np.sin(2 * np.pi * fundamental * 1.59 * t) * np.exp(-t * 100)
        # Tiny noise component
        signal += np.random.randn(n) * 0.05 * np.exp(-t * 150)

        # Gentle onset
        onset = min(int(0.001 * sr), n)
        if onset > 0:
            signal[:onset] *= np.linspace(0, 1, onset)

        return amplitude * signal
