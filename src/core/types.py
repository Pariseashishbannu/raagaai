"""Type aliases for the Raaga.AI domain."""

from typing import NewType

RagaId = NewType("RagaId", str)
TalaId = NewType("TalaId", str)
JobId = NewType("JobId", str)
UserId = NewType("UserId", str)
SvaraSequence = list[str]
PitchContour = list[float]  # Hz values over time
