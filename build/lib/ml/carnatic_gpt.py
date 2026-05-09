"""Svara generation: neural model with raga-constrained decoding, or rule-based fallback."""

import logging
import random
from dataclasses import dataclass
from pathlib import Path

from src.constraint_engine.raga_engine import RagaEngine, RagaSpec
from src.constraint_engine.tala_engine import TalaEngine, TalaGrid
from src.core.constants import Kala, Section, SVARA_SEMITONES

logger = logging.getLogger(__name__)

DEFAULT_CHECKPOINT = "data/models/svara_transformer.pt"
DEFAULT_VOCAB = "data/models/tokenizer_vocab.json"


@dataclass
class GeneratedSvaras:
    svaras: list[str]
    section: str
    num_avartanams: int


class CarnaticGPT:
    """Svara generator — tries neural model first, falls back to weighted random walk."""

    def __init__(
        self,
        raga_engine: RagaEngine,
        tala_engine: TalaEngine,
        checkpoint_path: str = DEFAULT_CHECKPOINT,
    ):
        self.raga_engine = raga_engine
        self.tala_engine = tala_engine
        self._model = None
        self._tokenizer = None
        self._device = None

        self._try_load_model(checkpoint_path)

    def _try_load_model(self, checkpoint_path: str) -> None:
        """Load checkpoint if it exists. Silently no-ops on failure so fallback kicks in."""
        if not Path(checkpoint_path).exists():
            logger.info("No checkpoint at %s — using rule-based generation", checkpoint_path)
            return

        try:
            import torch

            from src.ml.model import load_model
            from src.ml.tokenizer import SvaraTokenizer

            device = "cuda" if torch.cuda.is_available() else "cpu"

            model, config = load_model(checkpoint_path, device=device)
            self._model = model
            self._device = device

            # Load tokenizer with saved vocab
            vocab_path = str(Path(checkpoint_path).parent / "tokenizer_vocab.json")
            if Path(vocab_path).exists():
                self._tokenizer = SvaraTokenizer(vocab_path=vocab_path)
            else:
                self._tokenizer = SvaraTokenizer()

            param_count = model.count_parameters()
            logger.info(
                "Loaded SvaraTransformer (%s params) on %s",
                f"{param_count:,}", device,
            )
        except Exception:
            logger.warning("Failed to load neural model, using fallback", exc_info=True)
            self._model = None
            self._tokenizer = None

    @property
    def has_neural_model(self) -> bool:
        return self._model is not None

    def generate_svaras(
        self,
        raga_id: str,
        tala_id: str,
        section: str,
        kala: str,
        num_avartanams: int = 4,
    ) -> GeneratedSvaras:
        raga = self.raga_engine.get_raga(raga_id)
        if not raga:
            raise ValueError(f"Unknown raga: {raga_id}")

        grid = self.tala_engine.generate_grid(tala_id, num_avartanams)
        total_svaras = grid.total_beats

        if self._model is not None and self._tokenizer is not None:
            svaras = self._generate_neural(raga, raga_id, tala_id, section, kala, total_svaras)
        else:
            svaras = self._generate_walk(raga, grid, section, total_svaras)

        return GeneratedSvaras(
            svaras=svaras,
            section=section,
            num_avartanams=num_avartanams,
        )

    def generate_full_composition(
        self,
        raga_id: str,
        tala_id: str,
        kala: str,
        num_charanams: int = 2,
        include_chittaswaram: bool = False,
    ) -> list[GeneratedSvaras]:
        """Generate a complete composition with pallavi, anupallavi, and charanams."""
        sections = []

        # Pallavi: 4 avartanams for a full verse
        sections.append(self.generate_svaras(raga_id, tala_id, "pallavi", kala, 4))

        # Anupallavi: 4 avartanams
        sections.append(self.generate_svaras(raga_id, tala_id, "anupallavi", kala, 4))

        # Charanams: 3 avartanams each
        for i in range(num_charanams):
            sections.append(self.generate_svaras(raga_id, tala_id, "charanam", kala, 3))

        if include_chittaswaram:
            sections.append(
                self.generate_svaras(raga_id, tala_id, "chittaswaram", kala, 3)
            )

        return sections

    def _generate_neural(
        self,
        raga: RagaSpec,
        raga_id: str,
        tala_id: str,
        section: str,
        kala: str,
        total_svaras: int,
    ) -> list[str]:
        import torch

        tokenizer = self._tokenizer
        model = self._model
        device = self._device

        prefix_ids = tokenizer.encode_conditioning(raga_id, tala_id, section, kala)
        input_tensor = torch.tensor([prefix_ids], device=device)

        # Mask out svaras that aren't in this raga; non-svara tokens stay unmasked
        allowed_svaras = raga.allowed_svaras
        logit_mask = torch.zeros(tokenizer.vocab_size, device=device)
        svara_tokens = tokenizer.svara_tokens
        for svara in svara_tokens:
            tok_id = tokenizer.token_to_id.get(svara)
            if tok_id is not None and svara not in allowed_svaras:
                logit_mask[tok_id] = float("-inf")

        generated = model.generate(
            input_tensor,
            max_new_tokens=total_svaras + 5,  # Slight buffer
            temperature=0.8,
            top_k=15,
            logit_mask=logit_mask,
            eos_token_id=tokenizer.eos_id,
        )

        all_tokens = tokenizer.decode(generated[0].cpu().tolist())
        svara_set = set(svara_tokens)
        svaras = [t for t in all_tokens if t in svara_set]

        # Pad or truncate to the exact beat count the tala demands
        while len(svaras) < total_svaras:
            svaras.append(svaras[-1] if svaras else "Sa")
        svaras = svaras[:total_svaras]

        return svaras

    def _generate_walk(
        self,
        raga: RagaSpec,
        grid: TalaGrid,
        section: str,
        total_svaras: int,
    ) -> list[str]:
        """Rule-based fallback: weighted random walk with melodic heuristics."""
        arohanam = raga.arohanam
        avarohanam = raga.avarohanam
        allowed = list(raga.allowed_svaras)

        if not allowed:
            return ["Sa"] * total_svaras

        svaras: list[str] = []
        direction = "up"  # Start ascending

        # Section-specific behavior
        if section == "pallavi":
            start_range = arohanam[:len(arohanam) // 2 + 1]
        elif section == "anupallavi":
            start_range = arohanam[len(arohanam) // 2:]
        elif section == "charanam":
            start_range = arohanam
        else:
            start_range = arohanam

        current = random.choice(start_range) if start_range else "Sa"
        svaras.append(current)

        for i in range(1, total_svaras):
            position = grid.positions[i] if i < len(grid.positions) else None
            candidates = self.raga_engine.get_valid_next(raga.id, svaras[-3:])

            if not candidates:
                candidates = allowed

            weights = []
            for c in candidates:
                w = 1.0
                # stepwise motion sounds more natural
                if current in arohanam and c in arohanam:
                    curr_idx = arohanam.index(current)
                    cand_idx = arohanam.index(c)
                    if abs(curr_idx - cand_idx) == 1:
                        w *= 3.0
                    elif abs(curr_idx - cand_idx) == 2:
                        w *= 1.5

                # sam (first beat) should land on strong svaras
                if position and position.is_sam:
                    if c in ("Sa", "Pa"):
                        w *= 4.0

                if position and position.stress > 0.7:
                    if c == current:
                        w *= 1.5

                # boost characteristic gamakas / phrases of this raga
                for phrase in raga.characteristic_phrases:
                    if len(svaras) >= len(phrase) - 1:
                        recent = svaras[-(len(phrase) - 1):]
                        if recent == phrase[:-1] and c == phrase[-1]:
                            w *= 5.0

                weights.append(w)

            if random.random() < 0.15:
                direction = "down" if direction == "up" else "up"

            if position and position.beat_in_cycle == 0:
                direction = "down" if direction == "up" else "up"

            current = random.choices(candidates, weights=weights, k=1)[0]
            svaras.append(current)

        return svaras
