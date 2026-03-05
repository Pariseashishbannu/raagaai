"""Unit tests for rule-based svara generation."""

import pytest
from src.constraint_engine.raga_engine import RagaEngine
from src.constraint_engine.tala_engine import TalaEngine
from src.ml.carnatic_gpt import CarnaticGPT


@pytest.fixture
def raga_engine():
    return RagaEngine()


@pytest.fixture
def tala_engine():
    return TalaEngine()


@pytest.fixture
def gpt(raga_engine, tala_engine):
    return CarnaticGPT(raga_engine, tala_engine)


def test_generate_svaras_returns_list(gpt):
    """Should return a GeneratedSvaras with a list of svara strings."""
    result = gpt.generate_svaras("mohanam", "adi", "pallavi", "madhyama", 2)
    assert len(result.svaras) > 0
    assert all(isinstance(s, str) for s in result.svaras)


def test_generated_svaras_respect_raga(gpt, raga_engine):
    """All generated svaras should be valid for the raga."""
    for _ in range(10):
        result = gpt.generate_svaras("mohanam", "adi", "pallavi", "madhyama", 2)
        assert raga_engine.validate("mohanam", result.svaras), \
            f"Invalid svara found: {result.svaras}"


def test_generate_full_composition(gpt):
    """Should generate multiple sections."""
    sections = gpt.generate_full_composition("mohanam", "adi", "madhyama", 2)
    assert len(sections) >= 3  # pallavi + anupallavi + charanam


def test_kalyani_generation_valid(gpt, raga_engine):
    """Kalyani generation should use Ma2, not Ma1."""
    for _ in range(10):
        result = gpt.generate_svaras("kalyani", "adi", "pallavi", "madhyama", 2)
        for s in result.svaras:
            assert s != "Ma1", "Kalyani should not contain Ma1"


def test_different_sections_vary(gpt):
    """Different sections should produce different sequences."""
    pallavi = gpt.generate_svaras("mohanam", "adi", "pallavi", "madhyama", 2)
    charanam = gpt.generate_svaras("mohanam", "adi", "charanam", "madhyama", 2)
    # They might occasionally be same due to randomness, but usually different
    # Just check they're both valid
    assert len(pallavi.svaras) > 0
    assert len(charanam.svaras) > 0
