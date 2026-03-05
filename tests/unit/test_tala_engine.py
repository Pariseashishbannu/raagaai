"""Unit tests for the tala engine."""

import pytest
from src.constraint_engine.tala_engine import TalaEngine


@pytest.fixture
def engine():
    return TalaEngine()


def test_list_talas(engine):
    """Should have at least the 7 standard talas."""
    talas = engine.list_talas()
    assert len(talas) >= 7


def test_adi_tala(engine):
    """Adi tala should have 8 beats."""
    tala = engine.get_tala("adi")
    assert tala is not None
    assert tala.beats == 8
    assert tala.jathi == "chatusra"


def test_rupaka_tala(engine):
    """Rupaka tala should have 3 beats."""
    tala = engine.get_tala("rupaka")
    assert tala is not None
    assert tala.beats == 3


def test_generate_grid(engine):
    """Grid should have correct total beats."""
    grid = engine.generate_grid("adi", 4)
    assert grid.total_beats == 32
    assert grid.num_avartanams == 4
    assert len(grid.positions) == 32


def test_validate_rhythm_correct(engine):
    """Sequence divisible by beat count should be valid."""
    seq = ["Sa"] * 16  # 16 = 8 * 2 avartanams
    assert engine.validate_rhythm(seq, "adi") is True


def test_validate_rhythm_incorrect(engine):
    """Sequence not divisible by beat count should be invalid."""
    seq = ["Sa"] * 13  # 13 not divisible by 8
    assert engine.validate_rhythm(seq, "adi") is False


def test_unknown_tala(engine):
    """Should return None for unknown tala."""
    assert engine.get_tala("nonexistent") is None
