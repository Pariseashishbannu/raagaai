"""Tambura drone generator using Karplus-Strong plucked string synthesis."""

import numpy as np
from scipy.signal import lfilter

from src.synthesis.gamaka_renderer import svara_to_hz


def _karplus_strong(
    freq_hz: float,
    duration_sec: float,
    sample_rate: int,
    decay: float = 0.998,
    brightness: float = 0.5,
) -> np.ndarray:
    """Karplus-Strong string synthesis: noise burst → delay line → LP filter.

    Args:
        freq_hz: Fundamental frequency of the string.
        duration_sec: Duration in seconds.
        sample_rate: Audio sample rate.
        decay: Controls sustain length (0.99 = short, 0.999 = long).
        brightness: Low-pass blend (0 = mellow, 1 = bright).
    """
    delay_len = max(int(sample_rate / freq_hz), 2)
    num_samples = int(sample_rate * duration_sec)

    # Initial noise burst excitation (band-limited)
    noise = np.random.uniform(-1.0, 1.0, delay_len)
    # Gentle low-pass on excitation for warmer attack
    noise = np.convolve(noise, [0.25, 0.5, 0.25], mode="same")

    out = np.zeros(num_samples, dtype=np.float64)
    out[:delay_len] = noise

    # Delay-line feedback with averaging low-pass filter
    for i in range(delay_len, num_samples):
        # Two-point average (Karplus-Strong LP)
        avg = brightness * out[i - delay_len] + (1.0 - brightness) * out[i - delay_len + 1]
        out[i] = decay * avg

    return out


def _apply_jiva(signal: np.ndarray, amount: float = 0.15) -> np.ndarray:
    """Simulate jiva svaras (bridge buzzing) via nonlinear waveshaping.

    The tambura bridge causes sympathetic buzzing — modeled as soft clipping
    that adds upper harmonics characteristic of the instrument.
    """
    # Soft-clip waveshaping: tanh with drive
    drive = 1.0 + amount * 8.0
    shaped = np.tanh(drive * signal)
    # Blend original with shaped signal
    return signal * (1.0 - amount) + shaped * amount


def generate_tambura_drone(
    tonic_hz: float,
    duration_sec: float,
    sample_rate: int = 44100,
) -> np.ndarray:
    """Generate a tambura drone using Karplus-Strong plucked string model.

    Traditional 4-string tuning: Sa(low), Pa, Sa, Sa.
    Strings are plucked in staggered fashion and re-plucked periodically.
    """
    num_samples = int(sample_rate * duration_sec)

    sa_hz = tonic_hz
    pa_hz = tonic_hz * (2.0 ** (7.0 / 12.0))  # perfect fifth
    sa_low = tonic_hz / 2.0

    # 4-string tambura tuning: Sa(low), Pa, Sa, Sa
    strings = [
        (sa_low, 0.30, 0.997, 0.40),   # low Sa — warm, longer decay
        (pa_hz, 0.22, 0.996, 0.50),     # Pa — slightly brighter
        (sa_hz, 0.32, 0.996, 0.45),     # Sa — main drone
        (sa_hz, 0.28, 0.996, 0.45),     # Sa — doubled, slight detune
    ]

    drone = np.zeros(num_samples, dtype=np.float64)
    repluck_interval = 4.0  # re-pluck every ~4 seconds
    stagger_offset = 0.3     # seconds between string plucks

    for str_idx, (freq, amp, decay, brightness) in enumerate(strings):
        # Slight detune on the 4th string for richness
        if str_idx == 3:
            freq *= 1.002

        string_signal = np.zeros(num_samples, dtype=np.float64)
        pluck_time = str_idx * stagger_offset  # stagger initial plucks

        while pluck_time < duration_sec:
            pluck_sample = int(pluck_time * sample_rate)
            remaining = duration_sec - pluck_time
            # Each pluck rings for the repluck interval (or until end)
            pluck_dur = min(repluck_interval + 1.0, remaining)

            if pluck_dur <= 0:
                break

            segment = _karplus_strong(freq, pluck_dur, sample_rate, decay, brightness)
            segment = _apply_jiva(segment, amount=0.12)

            # Fade in each pluck slightly to avoid click
            fade_in = min(int(0.005 * sample_rate), len(segment))
            if fade_in > 0:
                segment[:fade_in] *= np.linspace(0, 1, fade_in)

            end_sample = min(pluck_sample + len(segment), num_samples)
            length = end_sample - pluck_sample
            if length > 0:
                # Crossfade with existing signal to avoid discontinuities
                xfade = min(int(0.01 * sample_rate), length)
                if pluck_sample > 0 and xfade > 0:
                    fade_out = np.linspace(1, 0, xfade)
                    fade_in_curve = np.linspace(0, 1, xfade)
                    string_signal[pluck_sample:pluck_sample + xfade] *= fade_out
                    segment[:xfade] *= fade_in_curve
                string_signal[pluck_sample:end_sample] += segment[:length]

            # Next pluck with slight timing variation
            pluck_time += repluck_interval + np.random.uniform(-0.2, 0.2)

        drone += amp * string_signal

    # Gentle high-frequency rolloff for warmth
    # Simple one-pole low-pass: y[n] = alpha * x[n] + (1-alpha) * y[n-1]
    alpha = 0.15
    b_lp = [alpha]
    a_lp = [1.0, -(1.0 - alpha)]
    drone = lfilter(b_lp, a_lp, drone)

    # Normalize to keep quieter than melody
    peak = np.max(np.abs(drone))
    if peak > 0:
        drone = drone / peak * 0.3
    return drone
