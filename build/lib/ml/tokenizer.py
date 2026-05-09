"""Custom svara tokenizer for Carnatic music sequences."""

import json
from pathlib import Path

# Core vocabulary — fixed tokens that never change
SVARA_VOCAB = [
    "<pad>", "<bos>", "<eos>",
    "<raga>", "<tala>", "<section>", "<kala>",
    "Sa", "Ri1", "Ri2", "Ga1", "Ga2", "Ma1", "Ma2",
    "Pa", "Da1", "Da2", "Ni1", "Ni2",
    "<lower>", "<middle>", "<upper>",
    "<rest>", "<sustain>",
    "<kampita>", "<jaru>", "<nokku>", "<odukkal>",
    "<sphurita>", "<pratyahata>",
    # Section tokens
    "pallavi", "anupallavi", "charanam", "chittaswaram",
    # Kala tokens
    "vilamba", "madhyama", "druta",
]


class SvaraTokenizer:
    def __init__(self, vocab_path: str | None = None):
        if vocab_path and Path(vocab_path).exists():
            with open(vocab_path) as f:
                self.token_to_id = json.load(f)
        else:
            self.token_to_id = {tok: i for i, tok in enumerate(SVARA_VOCAB)}

        self.id_to_token = {v: k for k, v in self.token_to_id.items()}
        self.vocab_size = len(self.token_to_id)

    def _add_token(self, token: str) -> int:
        """Add a token to the vocabulary if it doesn't exist. Returns token ID."""
        if token not in self.token_to_id:
            new_id = len(self.token_to_id)
            self.token_to_id[token] = new_id
            self.id_to_token[new_id] = token
            self.vocab_size = len(self.token_to_id)
            return new_id
        return self.token_to_id[token]

    def add_raga_tokens(self, raga_ids: list[str]) -> None:
        """Register raga ID tokens (e.g. 'raga:shankarabharanam')."""
        for rid in raga_ids:
            self._add_token(f"raga:{rid}")

    def add_tala_tokens(self, tala_ids: list[str]) -> None:
        """Register tala ID tokens (e.g. 'tala:adi')."""
        for tid in tala_ids:
            self._add_token(f"tala:{tid}")

    def encode(self, svaras: list[str]) -> list[int]:
        return [self.token_to_id.get(s, self.token_to_id["<pad>"]) for s in svaras]

    def decode(self, ids: list[int]) -> list[str]:
        return [self.id_to_token.get(i, "<pad>") for i in ids]

    def encode_conditioning(
        self, raga_id: str, tala_id: str, section: str, kala: str
    ) -> list[int]:
        """Encode conditioning prefix: <bos> raga:ID [tala:ID] section kala.

        Only includes raga/tala tokens if they exist in the vocabulary.
        This prevents out-of-bounds embedding lookups at inference time.
        """
        raga_tok = f"raga:{raga_id}"
        tala_tok = f"tala:{tala_id}"
        tokens = ["<bos>"]
        if raga_tok in self.token_to_id:
            tokens.append(raga_tok)
        if tala_tok in self.token_to_id:
            tokens.append(tala_tok)
        tokens.extend([section, kala])
        return self.encode(tokens)

    @property
    def pad_id(self) -> int:
        return self.token_to_id["<pad>"]

    @property
    def bos_id(self) -> int:
        return self.token_to_id["<bos>"]

    @property
    def eos_id(self) -> int:
        return self.token_to_id["<eos>"]

    @property
    def svara_tokens(self) -> list[str]:
        return ["Sa", "Ri1", "Ri2", "Ga1", "Ga2", "Ma1", "Ma2",
                "Pa", "Da1", "Da2", "Ni1", "Ni2"]

    @property
    def svara_ids(self) -> list[int]:
        """Token IDs for the 12 core svaras."""
        return [self.token_to_id[s] for s in self.svara_tokens]

    def save_vocab(self, path: str):
        with open(path, "w") as f:
            json.dump(self.token_to_id, f, indent=2)
