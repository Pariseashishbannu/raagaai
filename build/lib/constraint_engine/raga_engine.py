"""Raga constraint engine — loads raga definitions and validates svara sequences."""

import json
from pathlib import Path
from dataclasses import dataclass, field

from src.core.constants import ALL_SVARAS


@dataclass
class RagaSpec:
    id: str
    name_english: str
    name_telugu: str = ""
    melakarta_number: int | None = None
    arohanam: list[str] = field(default_factory=list)
    avarohanam: list[str] = field(default_factory=list)
    varja_svaras: list[str] = field(default_factory=list)
    characteristic_phrases: list[list[str]] = field(default_factory=list)
    gamaka_rules: dict[str, list[str]] = field(default_factory=dict)
    janya_of: str | None = None
    rasa_tags: list[str] = field(default_factory=list)

    @property
    def allowed_svaras(self) -> set[str]:
        """Set of svaras allowed in this raga (arohanam + avarohanam unique)."""
        return set(self.arohanam) | set(self.avarohanam)


class RagaEngine:

    def __init__(self, data_dir: str = "data/ragas"):
        self._ragas: dict[str, RagaSpec] = {}
        self._load_ragas(data_dir)

    def _load_ragas(self, data_dir: str):
        data_path = Path(data_dir)
        for json_file in data_path.glob("*.json"):
            with open(json_file, encoding="utf-8") as f:
                ragas_data = json.load(f)
            if isinstance(ragas_data, list):
                for r in ragas_data:
                    spec = RagaSpec(**r)
                    self._ragas[spec.id] = spec
            elif isinstance(ragas_data, dict):
                for rid, rdata in ragas_data.items():
                    if "id" not in rdata:
                        rdata["id"] = rid
                    spec = RagaSpec(**rdata)
                    self._ragas[spec.id] = spec

    def get_raga(self, raga_id: str) -> RagaSpec | None:
        return self._ragas.get(raga_id)

    def list_ragas(self) -> list[RagaSpec]:
        return list(self._ragas.values())

    def validate(self, raga_id: str, svara_sequence: list[str]) -> bool:
        raga = self._ragas.get(raga_id)
        if not raga:
            return False

        allowed = raga.allowed_svaras
        for svara in svara_sequence:
            if svara not in allowed:
                return False
        return True

    def get_valid_next(self, raga_id: str, context: list[str]) -> list[str]:
        """Valid next svaras from context, biased toward arohanam/avarohanam neighbors."""
        raga = self._ragas.get(raga_id)
        if not raga:
            return []

        allowed = raga.allowed_svaras
        if not context:
            return [s for s in raga.arohanam[:3]]

        last = context[-1]
        valid = []

        arohanam_set = raga.arohanam
        avarohanam_set = raga.avarohanam

        if last in arohanam_set:
            idx = arohanam_set.index(last)
            if idx + 1 < len(arohanam_set):
                valid.append(arohanam_set[idx + 1])
            if idx + 2 < len(arohanam_set):
                valid.append(arohanam_set[idx + 2])

        if last in avarohanam_set:
            idx = avarohanam_set.index(last)
            if idx + 1 < len(avarohanam_set):
                valid.append(avarohanam_set[idx + 1])
            if idx + 2 < len(avarohanam_set):
                valid.append(avarohanam_set[idx + 2])

        # always allow staying, and jumping to vadi/samvadi (Sa, Pa)
        if last not in valid:
            valid.append(last)
        if "Sa" not in valid and "Sa" in allowed:
            valid.append("Sa")
        if "Pa" not in valid and "Pa" in allowed:
            valid.append("Pa")

        # Filter to only allowed svaras
        return [s for s in valid if s in allowed]

    def get_logit_mask(self, raga_id: str, context: list[str], vocab: list[str]) -> list[float]:
        """0.0 for valid svaras, -inf for invalid — ready to add to logits."""
        valid = set(self.get_valid_next(raga_id, context))
        return [0.0 if tok in valid else float("-inf") for tok in vocab]
