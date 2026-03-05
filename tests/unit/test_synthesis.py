"""Unit tests for audio synthesis pipeline."""

import pytest
from src.synthesis.gamaka_renderer import svara_to_hz, GamakaRenderer
from src.synthesis.vocal_synth import VocalSynthesizer
from src.synthesis.tambura import generate_tambura_drone
from src.synthesis.pipeline import SynthesisPipeline


def test_svara_to_hz_sa():
    """Sa at default tonic should be ~261.63 Hz."""
    hz = svara_to_hz("Sa")
    assert abs(hz - 261.63) < 0.01


def test_svara_to_hz_pa():
    """Pa should be a perfect fifth above Sa."""
    sa = svara_to_hz("Sa")
    pa = svara_to_hz("Pa")
    ratio = pa / sa
    assert abs(ratio - 1.498) < 0.01  # 2^(7/12) ≈ 1.498


def test_gamaka_renderer():
    """Should produce pitch contours for each svara."""
    renderer = GamakaRenderer()
    svaras = ["Sa", "Ri2", "Ga2", "Pa"]
    contours = renderer.render(svaras, "mohanam", "madhyama")
    assert len(contours) == 4
    assert all(len(c) > 0 for c in contours)


def test_vocal_synth():
    """Should produce audio samples from pitch contours."""
    import numpy as np
    renderer = GamakaRenderer()
    synth = VocalSynthesizer()
    contours = renderer.render(["Sa", "Pa"], "mohanam", "madhyama")
    audio = synth.synthesize(contours)
    assert len(audio) > 0
    assert isinstance(audio, np.ndarray)


def test_tambura_drone():
    """Should produce a drone of the requested duration."""
    import numpy as np
    drone = generate_tambura_drone(261.63, 2.0, 44100)
    assert isinstance(drone, np.ndarray)
    expected_samples = int(2.0 * 44100)
    assert abs(len(drone) - expected_samples) < 100


def test_full_pipeline():
    """End-to-end: should produce WAV bytes."""
    pipeline = SynthesisPipeline()
    svara_sections = {
        "pallavi": ["Sa", "Ri2", "Ga2", "Pa", "Da2", "Sa", "Da2", "Pa"],
        "anupallavi": ["Pa", "Da2", "Sa", "Da2", "Pa", "Ga2", "Ri2", "Sa"],
    }
    output = pipeline.render(
        svara_sections=svara_sections,
        raga_id="mohanam",
        tala_id="adi",
        kala="madhyama",
    )
    assert output.wav_bytes is not None
    assert len(output.wav_bytes) > 1000  # Should be a real WAV
    assert output.duration_seconds > 0
    # Check WAV header
    assert output.wav_bytes[:4] == b"RIFF"
