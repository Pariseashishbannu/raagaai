"""Svara-akshara alignment utilities."""

from dataclasses import dataclass


@dataclass
class AlignmentEntry:
    svara: str
    akshara: str
    beat_position: int


def align_aksharas_to_svaras(
    aksharas: list[str],
    svara_sequence: list[str],
) -> list[AlignmentEntry]:
    """Map each akshara to its corresponding svara position."""
    entries = []
    for i, svara in enumerate(svara_sequence):
        ak = aksharas[i] if i < len(aksharas) else "-"
        entries.append(AlignmentEntry(svara=svara, akshara=ak, beat_position=i))
    return entries
