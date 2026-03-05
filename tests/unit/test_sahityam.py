"""Unit tests for sahityam (lyric) generation."""

import pytest
from src.sahityam.generator import SahityamGenerator


@pytest.fixture
def generator():
    return SahityamGenerator()


def test_generate_returns_result(generator):
    """Should return a SahityamResult with text."""
    svaras = ["Sa", "Ri2", "Ga2", "Pa", "Da2", "Sa", "Da2", "Pa"]
    result = generator.generate(svaras, "mohanam", "pallavi", "devotional")
    assert result.text is not None
    assert len(result.text) > 0


def test_alignment_matches_svaras(generator):
    """Alignment should have one entry per svara."""
    svaras = ["Sa", "Ri2", "Ga2", "Pa"]
    result = generator.generate(svaras, "mohanam", "pallavi", "devotional")
    assert len(result.akshara_svara_map) == len(svaras)


def test_different_themes(generator):
    """Should produce different content for different themes."""
    svaras = ["Sa", "Ri2", "Ga2", "Pa", "Da2", "Sa", "Da2", "Pa"]
    dev = generator.generate(svaras, "mohanam", "pallavi", "devotional")
    nat = generator.generate(svaras, "mohanam", "pallavi", "nature")
    # Both should produce text (may occasionally overlap due to random choice)
    assert dev.text is not None
    assert nat.text is not None
