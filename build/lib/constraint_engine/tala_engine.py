"""Tala prastara engine — rhythmic grid generation and validation."""

from dataclasses import dataclass, field
from src.core.constants import TALA_DEFINITIONS


@dataclass
class BeatPosition:
    index: int
    avartanam: int       # which cycle
    beat_in_cycle: int   # beat within the cycle
    is_sam: bool         # first beat of cycle
    stress: float        # 0.0 - 1.0 stress weight


@dataclass
class TalaGrid:
    tala_id: str
    beats_per_cycle: int
    total_beats: int
    num_avartanams: int
    positions: list[BeatPosition] = field(default_factory=list)
    eduppu: int = 0

    @property
    def sam_positions(self) -> list[int]:
        return [p.index for p in self.positions if p.is_sam]


@dataclass
class TalaSpec:
    id: str
    name: str
    beats: int
    jathi: str
    structure: list[str]


class TalaEngine:
    """Generates rhythmic grids and validates svara alignment with tala structure."""

    def __init__(self):
        self._talas: dict[str, TalaSpec] = {}
        for tid, tdata in TALA_DEFINITIONS.items():
            self._talas[tid] = TalaSpec(id=tid, **tdata)

    def get_tala(self, tala_id: str) -> TalaSpec | None:
        return self._talas.get(tala_id)

    def list_talas(self) -> list[TalaSpec]:
        return list(self._talas.values())

    def generate_grid(
        self, tala_id: str, num_avartanams: int, eduppu: int = 0
    ) -> TalaGrid:
        """Generate a rhythmic beat grid for the given tala and number of cycles."""
        tala = self._talas.get(tala_id)
        if not tala:
            raise ValueError(f"Unknown tala: {tala_id}")

        beats = tala.beats
        total = beats * num_avartanams
        positions = []

        for i in range(total):
            avartanam = i // beats
            beat_in_cycle = i % beats
            is_sam = beat_in_cycle == eduppu

            # Stress pattern: sam gets highest, then laghu boundaries
            if is_sam:
                stress = 1.0
            elif beat_in_cycle == 0:
                stress = 0.8
            elif beat_in_cycle % 2 == 0:
                stress = 0.5
            else:
                stress = 0.3

            positions.append(BeatPosition(
                index=i,
                avartanam=avartanam,
                beat_in_cycle=beat_in_cycle,
                is_sam=is_sam,
                stress=stress,
            ))

        return TalaGrid(
            tala_id=tala_id,
            beats_per_cycle=beats,
            total_beats=total,
            num_avartanams=num_avartanams,
            positions=positions,
            eduppu=eduppu,
        )

    def validate_rhythm(self, svara_sequence: list[str], tala_id: str) -> bool:
        """Check that svara count aligns with tala beat structure."""
        tala = self._talas.get(tala_id)
        if not tala:
            return False
        return len(svara_sequence) % tala.beats == 0

    def get_eduppu_options(self, tala_id: str) -> list[int]:
        """Valid starting beat positions for a tala."""
        tala = self._talas.get(tala_id)
        if not tala:
            return []
        return list(range(tala.beats))
