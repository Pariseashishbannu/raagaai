"""Train the SvaraTransformer on collected Carnatic svara sequences.

Usage:
    python -m scripts.train_model [--epochs 50] [--batch-size 32] [--lr 3e-4]

Requirements:
    - PyTorch with CUDA (pip install torch --index-url https://download.pytorch.org/whl/cu121)
    - Training data at data/training/svara_sequences.jsonl (run build_dataset.py first)

On RTX 3050 (4GB VRAM):
    - ~1.5M params, ~200MB VRAM with batch_size=32
    - Training takes ~10-30 min for 50 epochs
"""

import argparse
import logging
import math
import time
from pathlib import Path

import torch
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR

from src.ml.data.dataset import SvaraDataset, create_dataloader
from src.ml.model import SvaraTransformer
from src.ml.tokenizer import SvaraTokenizer

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Train SvaraTransformer")
    parser.add_argument("--data", type=str, default="data/training/svara_sequences.jsonl")
    parser.add_argument("--output-dir", type=str, default="data/models")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--max-seq-len", type=int, default=256)
    parser.add_argument("--embed-dim", type=int, default=128)
    parser.add_argument("--num-heads", type=int, default=4)
    parser.add_argument("--num-layers", type=int, default=4)
    parser.add_argument("--dropout", type=float, default=0.1)
    parser.add_argument("--grad-clip", type=float, default=1.0)
    parser.add_argument("--val-split", type=float, default=0.1)
    parser.add_argument("--patience", type=int, default=10, help="Early stopping patience")
    parser.add_argument("--device", type=str, default=None, help="Force device (cuda/cpu)")
    args = parser.parse_args()

    # Device selection
    if args.device:
        device = torch.device(args.device)
    elif torch.cuda.is_available():
        device = torch.device("cuda")
    else:
        device = torch.device("cpu")
    logger.info("Using device: %s", device)

    if device.type == "cuda":
        logger.info("GPU: %s", torch.cuda.get_device_name(0))
        logger.info("VRAM: %.1f GB", torch.cuda.get_device_properties(0).total_memory / 1e9)

    # Load data
    data_path = Path(args.data)
    if not data_path.exists():
        logger.error("Training data not found at %s. Run build_dataset.py first.", data_path)
        return

    tokenizer = SvaraTokenizer()

    # Create dataset and split into train/val
    full_dataset = SvaraDataset(str(data_path), tokenizer, max_length=args.max_seq_len)
    logger.info("Dataset size: %d sequences", len(full_dataset))
    logger.info("Vocab size: %d tokens", tokenizer.vocab_size)

    val_size = max(1, int(len(full_dataset) * args.val_split))
    train_size = len(full_dataset) - val_size
    train_dataset, val_dataset = torch.utils.data.random_split(
        full_dataset, [train_size, val_size]
    )

    train_loader = torch.utils.data.DataLoader(
        train_dataset,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=0,
        pin_memory=(device.type == "cuda"),
    )
    val_loader = torch.utils.data.DataLoader(
        val_dataset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=0,
        pin_memory=(device.type == "cuda"),
    )

    # Create model
    model = SvaraTransformer(
        vocab_size=tokenizer.vocab_size,
        embed_dim=args.embed_dim,
        num_heads=args.num_heads,
        num_layers=args.num_layers,
        max_seq_len=args.max_seq_len,
        dropout=args.dropout,
    ).to(device)

    param_count = model.count_parameters()
    logger.info("Model parameters: %s (%.2f MB)", f"{param_count:,}", param_count * 4 / 1e6)

    # Optimizer and scheduler
    optimizer = AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)
    scheduler = CosineAnnealingLR(optimizer, T_max=args.epochs, eta_min=args.lr * 0.1)

    # Training loop
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = output_dir / "svara_transformer.pt"

    best_val_loss = float("inf")
    patience_counter = 0
    start_time = time.time()

    logger.info("Starting training loop...")
    for epoch in range(1, args.epochs + 1):
        # Train
        model.train()
        train_loss = 0.0
        train_steps = 0
        logger.info("Epoch %d: Training...", epoch)

        for batch in train_loader:
            input_ids = batch["input_ids"].to(device)
            labels = batch["labels"].to(device)

            output = model(input_ids, labels=labels)
            loss = output["loss"]

            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), args.grad_clip)
            optimizer.step()

            train_loss += loss.item()
            train_steps += 1

            if train_steps % 100 == 0:
                logger.info("  Step %d/%d | loss: %.4f", train_steps, len(train_loader), loss.item())

        scheduler.step()
        avg_train_loss = train_loss / max(train_steps, 1)

        # Validate
        model.eval()
        val_loss = 0.0
        val_steps = 0

        with torch.no_grad():
            for batch in val_loader:
                input_ids = batch["input_ids"].to(device)
                labels = batch["labels"].to(device)
                output = model(input_ids, labels=labels)
                val_loss += output["loss"].item()
                val_steps += 1

        avg_val_loss = val_loss / max(val_steps, 1)

        # Logging
        elapsed = time.time() - start_time
        lr_now = scheduler.get_last_lr()[0]
        logger.info(
            "Epoch %3d/%d | train_loss: %.4f | val_loss: %.4f | lr: %.2e | elapsed: %.0fs",
            epoch, args.epochs, avg_train_loss, avg_val_loss, lr_now, elapsed,
        )

        # Save best model
        if avg_val_loss < best_val_loss:
            best_val_loss = avg_val_loss
            patience_counter = 0

            torch.save({
                "model_state_dict": model.state_dict(),
                "config": {
                    "vocab_size": tokenizer.vocab_size,
                    "embed_dim": args.embed_dim,
                    "num_heads": args.num_heads,
                    "num_layers": args.num_layers,
                    "max_seq_len": args.max_seq_len,
                    "dropout": 0.0,  # No dropout at inference
                },
                "tokenizer_vocab": tokenizer.token_to_id,
                "epoch": epoch,
                "val_loss": best_val_loss,
            }, checkpoint_path)
            logger.info("  → Saved best model (val_loss=%.4f)", best_val_loss)
        else:
            patience_counter += 1
            if patience_counter >= args.patience:
                logger.info("Early stopping at epoch %d (no improvement for %d epochs)",
                            epoch, args.patience)
                break

    # Save tokenizer vocab alongside model
    tokenizer.save_vocab(str(output_dir / "tokenizer_vocab.json"))

    total_time = time.time() - start_time
    logger.info("Training complete in %.1f minutes", total_time / 60)
    logger.info("Best val_loss: %.4f", best_val_loss)
    logger.info("Checkpoint saved to: %s", checkpoint_path)

    # Generate a sample to verify
    logger.info("\n--- Sample generation ---")
    model.eval()
    prefix = tokenizer.encode_conditioning("shankarabharanam", "adi", "pallavi", "madhyama")
    prefix_tensor = torch.tensor([prefix], device=device)

    generated = model.generate(
        prefix_tensor,
        max_new_tokens=32,
        temperature=0.8,
        top_k=15,
    )
    tokens = tokenizer.decode(generated[0].cpu().tolist())
    logger.info("Generated: %s", " ".join(tokens))


if __name__ == "__main__":
    main()
