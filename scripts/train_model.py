"""Train SvaraTransformer on Carnatic svara sequences.

Usage:
    python -m scripts.train_model
    python -m scripts.train_model --epochs 100 --batch-size 64 --grad-accum 2
    python -m scripts.train_model --resume data/models/svara_transformer.pt
    python -m scripts.train_model --finetune pretrained.pt --data carnatic.jsonl --lr 1e-4

Run build_dataset.py first to generate data/training/svara_sequences.jsonl.
"""

import argparse
import logging
import math
import time
from pathlib import Path

import torch
import torch.nn as nn
from torch.optim import AdamW

from src.ml.data.dataset import SvaraDataset
from src.ml.model import SvaraTransformer
from src.ml.tokenizer import SvaraTokenizer

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False


def get_lr(step: int, warmup_steps: int, total_steps: int, max_lr: float, min_lr: float) -> float:
    """Linear warmup then cosine decay."""
    if step < warmup_steps:
        return max_lr * step / max(warmup_steps, 1)
    if step >= total_steps:
        return min_lr
    t = (step - warmup_steps) / (total_steps - warmup_steps)
    return min_lr + 0.5 * (max_lr - min_lr) * (1 + math.cos(math.pi * t))


def run_epoch(
    model: SvaraTransformer,
    loader,
    optimizer,
    scaler,
    device: torch.device,
    grad_clip: float,
    grad_accum: int,
    global_step: int,
    warmup_steps: int,
    total_steps: int,
    max_lr: float,
    min_lr: float,
    train: bool = True,
):
    model.train(train)
    total_loss = 0.0
    steps = 0
    accum_loss = 0.0

    it = tqdm(loader, leave=False, desc="train" if train else "val") if HAS_TQDM else loader

    with torch.set_grad_enabled(train):
        for batch_idx, batch in enumerate(it):
            input_ids = batch["input_ids"].to(device)
            labels = batch["labels"].to(device)

            with torch.amp.autocast(device_type="cuda", enabled=(device.type == "cuda")):
                out = model(input_ids, labels=labels)
                loss = out["loss"] / grad_accum

            if train:
                scaler.scale(loss).backward()
                accum_loss += loss.item()

                if (batch_idx + 1) % grad_accum == 0 or (batch_idx + 1) == len(loader):
                    scaler.unscale_(optimizer)
                    nn.utils.clip_grad_norm_(model.parameters(), grad_clip)

                    # Set LR for THIS step before stepping (so warmup actually warms up).
                    lr = get_lr(global_step, warmup_steps, total_steps, max_lr, min_lr)
                    for pg in optimizer.param_groups:
                        pg["lr"] = lr

                    scaler.step(optimizer)
                    scaler.update()
                    optimizer.zero_grad()

                    total_loss += accum_loss
                    accum_loss = 0.0
                    global_step += 1
                    steps += 1

                    if HAS_TQDM:
                        it.set_postfix(loss=f"{loss.item() * grad_accum:.4f}", lr=f"{lr:.2e}")
            else:
                total_loss += loss.item() * grad_accum
                steps += 1

    return total_loss / max(steps, 1), global_step


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="data/training/svara_sequences.jsonl")
    parser.add_argument("--output-dir", default="data/models")
    parser.add_argument("--resume", default=None, help="Resume from checkpoint path")
    parser.add_argument(
        "--finetune", default=None,
        help="Start from these weights with a fresh optimizer/LR schedule (new data)",
    )
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--grad-accum", type=int, default=1, help="Gradient accumulation steps")
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--min-lr", type=float, default=3e-5)
    parser.add_argument("--warmup-ratio", type=float, default=0.05)
    parser.add_argument("--weight-decay", type=float, default=0.01)
    parser.add_argument("--max-seq-len", type=int, default=256)
    parser.add_argument("--embed-dim", type=int, default=128)
    parser.add_argument("--num-heads", type=int, default=4)
    parser.add_argument("--num-layers", type=int, default=4)
    parser.add_argument("--dropout", type=float, default=0.1)
    parser.add_argument("--grad-clip", type=float, default=1.0)
    parser.add_argument("--val-split", type=float, default=0.1)
    parser.add_argument("--patience", type=int, default=10)
    parser.add_argument("--device", default=None)
    args = parser.parse_args()

    # device
    if args.device:
        device = torch.device(args.device)
    elif torch.cuda.is_available():
        device = torch.device("cuda")
    else:
        device = torch.device("cpu")

    logger.info("device: %s", device)
    if device.type == "cuda":
        logger.info("gpu: %s | vram: %.1f GB",
                    torch.cuda.get_device_name(0),
                    torch.cuda.get_device_properties(0).total_memory / 1e9)

    # data
    data_path = Path(args.data)
    if not data_path.exists():
        logger.error("no training data at %s — run build_dataset.py first", data_path)
        return

    # Pre-load checkpoint so we can restore the tokenizer vocab BEFORE building the
    # dataset — otherwise SvaraDataset.add_raga_tokens would re-derive ids from the
    # current data file and silently break the saved embedding rows.
    ckpt = None
    if args.resume and Path(args.resume).exists():
        logger.info("resuming from %s", args.resume)
        ckpt = torch.load(args.resume, map_location=device, weights_only=False)
    elif args.finetune:
        logger.info("fine-tuning from %s", args.finetune)
        ckpt = torch.load(args.finetune, map_location=device, weights_only=False)
        # Architecture comes from the checkpoint; saved config must describe this model
        cfg = ckpt["config"]
        args.embed_dim = cfg.get("embed_dim", args.embed_dim)
        args.num_heads = cfg.get("num_heads", args.num_heads)
        args.num_layers = cfg.get("num_layers", args.num_layers)
        args.max_seq_len = cfg.get("max_seq_len", args.max_seq_len)

    tokenizer = SvaraTokenizer()
    if ckpt is not None and "tokenizer_vocab" in ckpt:
        tokenizer.token_to_id = dict(ckpt["tokenizer_vocab"])
        tokenizer.id_to_token = {i: t for t, i in tokenizer.token_to_id.items()}
        tokenizer.vocab_size = len(tokenizer.token_to_id)
        logger.info("restored tokenizer vocab from checkpoint (%d tokens)", tokenizer.vocab_size)

    full_dataset = SvaraDataset(str(data_path), tokenizer, max_length=args.max_seq_len)
    logger.info("dataset: %d sequences | vocab: %d tokens", len(full_dataset), tokenizer.vocab_size)

    val_size = max(1, int(len(full_dataset) * args.val_split))
    # Deterministic split — resumed runs must see the same train/val partition
    # otherwise val_loss continuity and train/val isolation are both broken.
    split_gen = torch.Generator().manual_seed(42)
    train_dataset, val_dataset = torch.utils.data.random_split(
        full_dataset, [len(full_dataset) - val_size, val_size], generator=split_gen
    )

    loader_kw = dict(num_workers=0, pin_memory=(device.type == "cuda"))
    train_loader = torch.utils.data.DataLoader(
        train_dataset, batch_size=args.batch_size, shuffle=True, **loader_kw
    )
    val_loader = torch.utils.data.DataLoader(
        val_dataset, batch_size=args.batch_size, shuffle=False, **loader_kw
    )

    # model — build (optionally restoring weights from the pre-loaded checkpoint)
    start_epoch = 1
    best_val_loss = float("inf")
    global_step = 0

    if ckpt is not None:
        cfg = ckpt["config"]
        model = SvaraTransformer(
            vocab_size=cfg["vocab_size"],
            embed_dim=cfg.get("embed_dim", args.embed_dim),
            num_heads=cfg.get("num_heads", args.num_heads),
            num_layers=cfg.get("num_layers", args.num_layers),
            max_seq_len=cfg.get("max_seq_len", args.max_seq_len),
            dropout=args.dropout,
        ).to(device)
        model.load_state_dict(ckpt["model_state_dict"])
        if args.finetune:
            # New data may bring new raga tokens; grow the (tied) embedding, keeping old rows
            if tokenizer.vocab_size > cfg["vocab_size"]:
                old_emb = model.token_emb.weight.data
                new_emb = torch.nn.Embedding(
                    tokenizer.vocab_size, old_emb.shape[1], padding_idx=0
                ).to(device)
                torch.nn.init.normal_(new_emb.weight, mean=0.0, std=0.02)
                new_emb.weight.data[:cfg["vocab_size"]] = old_emb
                model.token_emb = new_emb
                model.head.weight = new_emb.weight
                model.vocab_size = tokenizer.vocab_size
                logger.info("vocab grown %d → %d", cfg["vocab_size"], tokenizer.vocab_size)
            ckpt = None  # fresh optimizer, scaler and LR schedule
        else:
            start_epoch = ckpt.get("epoch", 0) + 1
            best_val_loss = ckpt.get("val_loss", float("inf"))
            logger.info("resumed at epoch %d (best val_loss=%.4f)", start_epoch, best_val_loss)
    else:
        model = SvaraTransformer(
            vocab_size=tokenizer.vocab_size,
            embed_dim=args.embed_dim,
            num_heads=args.num_heads,
            num_layers=args.num_layers,
            max_seq_len=args.max_seq_len,
            dropout=args.dropout,
        ).to(device)

    n_params = model.count_parameters()
    logger.info("params: %s (%.2f MB)", f"{n_params:,}", n_params * 4 / 1e6)

    # optimizer + AMP scaler
    optimizer = AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    scaler = torch.amp.GradScaler("cuda", enabled=(device.type == "cuda"))

    if ckpt is not None and "optimizer_state_dict" in ckpt:
        optimizer.load_state_dict(ckpt["optimizer_state_dict"])
    if ckpt is not None and "scaler_state_dict" in ckpt:
        scaler.load_state_dict(ckpt["scaler_state_dict"])

    steps_per_epoch = math.ceil(len(train_loader) / args.grad_accum)
    total_steps = steps_per_epoch * args.epochs
    warmup_steps = max(1, int(total_steps * args.warmup_ratio))

    # Recover global_step. Old checkpoints (pre-resume support) lack it; estimate
    # from epoch so the LR schedule doesn't re-warm from zero on a trained model.
    if ckpt is not None:
        if "global_step" in ckpt:
            global_step = ckpt["global_step"]
        else:
            global_step = ckpt.get("epoch", 0) * steps_per_epoch
            logger.warning("checkpoint lacks global_step; estimated as %d", global_step)
    logger.info("total_steps: %d | warmup: %d | lr: %.2e → %.2e",
                total_steps, warmup_steps, args.lr, args.min_lr)

    # training loop
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = output_dir / "svara_transformer.pt"

    patience_counter = 0
    t0 = time.time()

    for epoch in range(start_epoch, args.epochs + 1):
        train_loss, global_step = run_epoch(
            model, train_loader, optimizer, scaler, device,
            args.grad_clip, args.grad_accum, global_step,
            warmup_steps, total_steps, args.lr, args.min_lr,
            train=True,
        )

        val_loss, _ = run_epoch(
            model, val_loader, optimizer, scaler, device,
            args.grad_clip, args.grad_accum, global_step,
            warmup_steps, total_steps, args.lr, args.min_lr,
            train=False,
        )

        elapsed = time.time() - t0
        lr_now = get_lr(global_step, warmup_steps, total_steps, args.lr, args.min_lr)
        logger.info(
            "epoch %3d/%d | train %.4f | val %.4f | lr %.2e | %.0fs",
            epoch, args.epochs, train_loss, val_loss, lr_now, elapsed,
        )

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            patience_counter = 0
            torch.save({
                "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "scaler_state_dict": scaler.state_dict(),
                "config": {
                    "vocab_size": tokenizer.vocab_size,
                    "embed_dim": args.embed_dim,
                    "num_heads": args.num_heads,
                    "num_layers": args.num_layers,
                    "max_seq_len": args.max_seq_len,
                    "dropout": 0.0,
                },
                "tokenizer_vocab": tokenizer.token_to_id,
                "epoch": epoch,
                "global_step": global_step,
                "val_loss": best_val_loss,
            }, checkpoint_path)
            logger.info("  saved (val_loss=%.4f)", best_val_loss)
        else:
            patience_counter += 1
            if patience_counter >= args.patience:
                logger.info("early stopping at epoch %d", epoch)
                break

    tokenizer.save_vocab(str(output_dir / "tokenizer_vocab.json"))
    logger.info("done in %.1f min | best val_loss: %.4f", (time.time() - t0) / 60, best_val_loss)

    # quick sanity check — generate a short sequence
    model.eval()
    prefix = tokenizer.encode_conditioning("shankarabharanam", "adi", "pallavi", "madhyama")
    with torch.no_grad():
        generated = model.generate(
            torch.tensor([prefix], device=device),
            max_new_tokens=32, temperature=0.8, top_k=15,
        )
    logger.info("sample: %s", " ".join(tokenizer.decode(generated[0].cpu().tolist())))


if __name__ == "__main__":
    main()
