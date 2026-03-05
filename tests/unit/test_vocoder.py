"""Tests for HiFi-GAN neural vocoder module."""

import numpy as np
import pytest

from src.synthesis import vocoder


def test_is_available_returns_bool():
    """is_available() should always return a bool regardless of torch install status."""
    result = vocoder.is_available()
    assert isinstance(result, bool)


@pytest.mark.skipif(not vocoder.is_available(), reason="torch/torchaudio not installed")
class TestWithTorch:
    """Tests that require torch + torchaudio."""

    def test_enhance_preserves_length(self):
        """Vocoder output should be approximately the same length as input."""
        sr = 44100
        duration = 1.0
        t = np.linspace(0, duration, int(sr * duration), endpoint=False)
        waveform = (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)

        result = vocoder.enhance_vocal(waveform, source_sr=sr, target_sr=sr)

        # Allow 10% tolerance due to resampling / hop alignment
        assert abs(len(result) - len(waveform)) < len(waveform) * 0.10

    def test_enhance_produces_nonzero(self):
        """Vocoder should produce non-silent output from a non-silent input."""
        sr = 44100
        duration = 0.5
        t = np.linspace(0, duration, int(sr * duration), endpoint=False)
        waveform = (0.5 * np.sin(2 * np.pi * 300 * t)).astype(np.float32)

        result = vocoder.enhance_vocal(waveform, source_sr=sr, target_sr=sr)

        assert np.max(np.abs(result)) > 0.01


def test_pipeline_fallback_without_torch(monkeypatch):
    """Pipeline should work fine when torch is not available (fallback to additive synth)."""
    monkeypatch.setattr(vocoder, "_HAS_TORCH", False)

    assert not vocoder.is_available()

    # Pipeline init with vocoder disabled should not fail
    from src.synthesis.pipeline import SynthesisPipeline

    pipeline = SynthesisPipeline()
    assert not pipeline.use_vocoder
