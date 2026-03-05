# SvaraTransformer Training Guide

This guide explains how to train and fine-tune the `SvaraTransformer` model used for Carnatic melody generation.

## Overview

The `SvaraTransformer` is a small transformer-based language model that predicts the next svara (token) based on a raga, tala, and section context.

## 1. Dataset Preparation

The training data is stored in `data/training/svara_sequences.jsonl`. You can build it using the `build_dataset.py` script.

### Synthetic Generation
This is the fastest way to get started. It generates sequences based on the raga rules (arohanam/avarohanam).

```bash
python -m scripts.build_dataset --synthetic-per-raga 200
```

### External Data (Optional)
If you have the Saraga dataset or want to scrape `karnatik.com`:

```bash
# Saraga dataset
python -m scripts.build_dataset --saraga-dir /path/to/saraga

# Web scraping (karnatik.com)


```

## 2. Training the Model

Run the training script with default or custom hyperparameters.

### Basic Training
```bash
python -m scripts.train_model --epochs 50 --batch-size 32
```

### Hyperparameters
- `--lr`: Learning rate (default: 3e-4)
- `--embed-dim`: Embedding dimension (default: 128)
- `--num-layers`: Number of transformer layers (default: 4)
- `--num-heads`: Number of attention heads (default: 4)
- `--dropout`: Dropout rate (default: 0.1)

### Hardware Requirements
- **GPU (Recommended):** RTX 3050 (4GB VRAM) or better. Training takes ~15-30 mins.
- **CPU:** Possible but much slower. Use `--device cpu` to force.

## 3. Verification

After training, the script automatically saves:
- `data/models/svara_transformer.pt`: The model weights.
- `data/models/tokenizer_vocab.json`: The associated vocabulary.

The training script also performs a sample generation at the end to verify the model is producing musical sequences.

## 4. Troubleshooting

- **Out of Memory (OOM):** Reduce `--batch-size` or `--embed-dim`.
- **Loss not decreasing:** Try adjusting `--lr` or increasing `--epochs`.
- **Data not found:** Ensure `data/training/svara_sequences.jsonl` exists by running the dataset builder first.
