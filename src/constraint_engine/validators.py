"""High-level validators combining raga and tala engines."""

from .raga_engine import RagaEngine
from .tala_engine import TalaEngine
from src.core.exceptions import RagaValidationError, TalaValidationError


def validate_composition(
    raga_engine: RagaEngine,
    tala_engine: TalaEngine,
    raga_id: str,
    tala_id: str,
    svara_sequence: list[str],
) -> bool:
    """Full validation: raga rules + tala alignment."""
    if not raga_engine.validate(raga_id, svara_sequence):
        raise RagaValidationError(
            f"Svara sequence contains invalid svaras for raga '{raga_id}'"
        )

    if not tala_engine.validate_rhythm(svara_sequence, tala_id):
        raise TalaValidationError(
            f"Svara count ({len(svara_sequence)}) doesn't align with tala '{tala_id}'"
        )

    return True
