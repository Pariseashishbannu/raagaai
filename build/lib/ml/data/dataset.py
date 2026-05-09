"""PyTorch Dataset for Carnatic svara sequences."""

import json
from pathlib import Path

import torch
from torch.utils.data import Dataset

from src.ml.tokenizer import SvaraTokenizer


class SvaraDataset(Dataset):
    """Dataset of tokenized svara sequences for causal language modeling.

    Each sample is encoded as:
        [<bos>, raga:ID, section, svaras..., <eos>]
    padded to max_length.

    Labels are input_ids shifted right by 1 (teacher forcing).
    Padding positions have label = -100 (ignored by CrossEntropyLoss).
    """

    def __init__(
        self,
        data_path: str,
        tokenizer: SvaraTokenizer,
        max_length: int = 256,
    ):
        self.tokenizer = tokenizer
        self.max_length = max_length
        self.samples: list[dict] = []

        path = Path(data_path)
        if path.exists():
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        self.samples.append(json.loads(line))

        # Register all raga/tala tokens found in the data
        raga_ids = list({s["raga_id"] for s in self.samples if s.get("raga_id")})
        self.tokenizer.add_raga_tokens(raga_ids)

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> dict[str, torch.Tensor]:
        sample = self.samples[idx]
        raga_id = sample.get("raga_id", "")
        section = sample.get("section", "pallavi")
        svaras = sample.get("svaras", [])

        # Build token sequence: <bos> raga:ID section svaras... <eos>
        tokens = ["<bos>"]
        if raga_id:
            tokens.append(f"raga:{raga_id}")
        tokens.append(section)
        tokens.extend(svaras)
        tokens.append("<eos>")

        # Truncate to max_length
        tokens = tokens[:self.max_length]

        # Encode to IDs
        input_ids = self.tokenizer.encode(tokens)

        # Pad
        pad_len = self.max_length - len(input_ids)
        input_ids = input_ids + [self.tokenizer.pad_id] * pad_len

        # Labels: shifted by 1, with -100 for padding
        labels = input_ids[1:] + [self.tokenizer.pad_id]
        labels = [l if l != self.tokenizer.pad_id else -100 for l in labels]

        return {
            "input_ids": torch.tensor(input_ids, dtype=torch.long),
            "labels": torch.tensor(labels, dtype=torch.long),
        }


def create_dataloader(
    data_path: str,
    tokenizer: SvaraTokenizer,
    batch_size: int = 32,
    max_length: int = 256,
    shuffle: bool = True,
    num_workers: int = 0,
) -> torch.utils.data.DataLoader:
    """Create a DataLoader for training."""
    dataset = SvaraDataset(data_path, tokenizer, max_length)
    return torch.utils.data.DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=shuffle,
        num_workers=num_workers,
        pin_memory=True,
    )
