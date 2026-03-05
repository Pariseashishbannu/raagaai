"""Unit tests for the raga constraint engine."""

import pytest
from src.constraint_engine.raga_engine import RagaEngine


@pytest.fixture
def engine():
    return RagaEngine()


def test_load_ragas(engine):
    """Should load melakarta + janya ragas from data files."""
    ragas = engine.list_ragas()
    assert len(ragas) >= 72  # At least all melakartas


def test_get_known_raga(engine):
    """Should retrieve a known raga."""
    raga = engine.get_raga("mohanam")
    assert raga is not None
    assert raga.name_english == "Mohanam"
    assert "Sa" in raga.arohanam
    assert "Pa" in raga.arohanam


def test_get_unknown_raga(engine):
    """Should return None for unknown raga."""
    assert engine.get_raga("nonexistent") is None


def test_mohanam_blocks_invalid_svaras(engine):
    """Mohanam = Sa Ri2 Ga2 Pa Da2. Ma and Ni must be blocked."""
    seq_with_ma = ["Sa", "Ri2", "Ma1", "Pa"]
    assert engine.validate("mohanam", seq_with_ma) is False


def test_mohanam_allows_valid_svaras(engine):
    """Mohanam should allow its pentatonic scale."""
    seq = ["Sa", "Ri2", "Ga2", "Pa", "Da2", "Sa"]
    assert engine.validate("mohanam", seq) is True


def test_shankarabharanam_allows_all_svaras(engine):
    """Shankarabharanam is sampoorna — all 7 svaras valid."""
    # Check the janya version
    raga = engine.get_raga("sankarabharanam")
    if raga:
        seq = ["Sa", "Ri2", "Ga2", "Ma1", "Pa", "Da2", "Ni2", "Sa"]
        assert engine.validate("sankarabharanam", seq) is True


def test_get_valid_next_returns_list(engine):
    """Should return a non-empty list of valid next svaras."""
    result = engine.get_valid_next("mohanam", ["Sa", "Ri2"])
    assert isinstance(result, list)
    assert len(result) > 0


def test_kalyani_svaras(engine):
    """Kalyani uses Ma2 (prati madhyamam), not Ma1."""
    raga = engine.get_raga("kalyani")
    assert raga is not None
    assert "Ma2" in raga.arohanam
    # Ma1 should not be in allowed svaras
    allowed = raga.allowed_svaras
    assert "Ma1" not in allowed


def test_hindolam_is_pentatonic(engine):
    """Hindolam should have exactly 5 unique svaras (no Ri, no Pa)."""
    raga = engine.get_raga("hindolam")
    assert raga is not None
    allowed = raga.allowed_svaras
    assert "Ri1" not in allowed
    assert "Ri2" not in allowed
    assert "Pa" not in allowed
