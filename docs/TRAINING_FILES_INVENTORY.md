"""
# Training Files Inventory

## Summary

The Raaga.AI training pipeline consists of multiple files organized to support both local and cloud-based training. Below is a complete inventory of all training-related files.

## Training Files Overview

### Local Training (Original)

```
scripts/
  ├── train_model.py          # Main training script (PyTorch)
  ├── build_dataset.py        # Dataset preparation from multiple sources
  └── maestro_to_svara.py     # MIDI to svara conversion

src/ml/
  ├── model.py                # SvaraTransformer model architecture
  ├── tokenizer.py            # Svara tokenizer
  ├── carnatic_gpt.py         # Inference engine
  └── data/
      ├── dataset.py          # PyTorch dataset class
      ├── scraper.py          # Data scraping (Saraga, web, synthetic)
      └── __init__.py

data/
  ├── training/
  │   └── svara_sequences.jsonl  # Training data
  ├── models/
  │   ├── svara_transformer.pt   # Trained model
  │   └── tokenizer_vocab.json   # Tokenizer vocabulary
  ├── ragas/
  │   ├── melakarta.json         # Melakarta definitions
  │   └── janya.json             # Janya raga definitions
  └── talas/
      └── talas.json             # Tala definitions

docs/
  └── model_training.md       # Local training documentation
```

### NEW: Cloud Training

```
src/cloud_training/           # NEW: Cloud training module
  ├── __init__.py
  ├── base.py                 # Base trainer interface + TrainingConfig
  ├── aws_sagemaker.py        # AWS SageMaker adapter
  ├── gcp_vertex.py           # GCP Vertex AI adapter
  ├── azure_ml.py             # Azure ML adapter
  └── README.md               # Cloud training module docs

scripts/
  └── cloud_train.py          # NEW: Cloud training CLI launcher

cloud_config/                 # NEW: Cloud-specific configs
  ├── aws_training_config.json
  ├── gcp_training_config.json
  └── azure_training_config.json

infra/docker/
  └── Dockerfile.cloud-training  # NEW: Cloud training container

.github/workflows/
  └── cloud-training.yml      # NEW: GitHub Actions CI/CD

docs/
  ├── CLOUD_TRAINING.md       # NEW: Cloud training guide
  └── CLOUD_TRAINING_SUMMARY.md  # NEW: Cloud training summary

.env.cloud.example            # NEW: Cloud credential templates
requirements-cloud.txt        # NEW: Cloud dependencies

Makefile                       # UPDATED: Added cloud targets
```

## Training File Details

### Core Training Files

#### `scripts/train_model.py` (229 lines)
**Purpose:** Main training script for SvaraTransformer  
**Flow:** Load data → Create dataset → Split train/val → Initialize model → Training loop → Save checkpoints  
**Arguments:**
- `--epochs` (50) - Number of training epochs
- `--batch-size` (32) - Training batch size
- `--lr` (3e-4) - Learning rate
- `--embed-dim` (128) - Embedding dimension
- `--num-heads` (4) - Attention heads
- `--num-layers` (4) - Transformer layers
- `--max-seq-len` (256) - Maximum sequence length
- `--val-split` (0.1) - Validation split ratio
- `--patience` (10) - Early stopping patience
- `--device` - Force device (cuda/cpu)

**Output:** `data/models/svara_transformer.pt`, `data/models/tokenizer_vocab.json`

#### `scripts/build_dataset.py` (134 lines)
**Purpose:** Build training dataset from multiple sources  
**Sources:**
1. Synthetic sequences from local raga definitions (always)
2. Saraga dataset (optional, if --saraga-dir provided)
3. karnatik.com web scraping (optional, if --scrape-web)
4. Data augmentation (transpositions & repetitions)

**Arguments:**
- `--saraga-dir` - Path to Saraga dataset
- `--scrape-web` - Enable web scraping
- `--max-web-pages` (50) - Max pages to scrape
- `--synthetic-per-raga` (200) - Synthetic sequences per raga
- `--no-augment` - Skip augmentation
- `--output` - Output JSONL path

**Output:** `data/training/svara_sequences.jsonl`

#### `scripts/maestro_to_svara.py` (283 lines)
**Purpose:** Convert MAESTRO v2.0.0 MIDI files to svara sequences  
**Process:** MIDI tokens → MIDI notes → Svara mapping → Phrase segmentation → Raga assignment  
**Input:** MAESTRO .pt files (in `maestro-v2.0.0/` directory)  
**Output:** Svara sequences in JSONL format

#### `src/ml/model.py`
**Contains:** `SvaraTransformer` class - Transformer model for sequential svara generation
- Attention mechanism
- Position embeddings
- Feed-forward layers
- Generate function with temperature/top-k sampling

#### `src/ml/tokenizer.py`
**Contains:** `SvaraTokenizer` class - Handles svara encoding/decoding
- Token-to-ID mapping
- Conditioning tokens (raga, tala, section)
- Vocabulary management

#### `src/ml/data/dataset.py`
**Contains:** `SvaraDataset` class - PyTorch dataset for loading training data
- JSONL parsing
- Tokenization
- Batch creation

#### `src/ml/data/scraper.py`
**Contains:**
- `LocalRagaSynthesizer` - Generate synthetic sequences
- `SaragaScraper` - Parse Saraga annotations
- `KarnatikScraper` - Scrape karnatik.com
- `augment_sequences()` - Data augmentation

### NEW: Cloud Training Files

#### `src/cloud_training/base.py`
**Contains:**
- `TrainingConfig` dataclass - Unified config for all platforms
- `BaseCloudTrainer` ABC - Interface all trainers implement

**Methods:**
- `validate_credentials()` - Check cloud access
- `upload_training_data()` - Sync data to cloud
- `submit_training_job()` - Launch training
- `get_job_status()` - Monitor progress
- `download_model()` - Retrieve model
- `cancel_job()` - Stop job

#### `src/cloud_training/aws_sagemaker.py`
**Purpose:** AWS SageMaker training adapter  
**Dependencies:** `boto3`  
**Features:**
- SageMaker API integration
- S3 data upload
- Training job submission
- CloudWatch monitoring
- Model download from S3

**Hyperparameters passed to SageMaker:**
- epochs, batch_size, lr, embed_dim, num_heads, num_layers, dropout

#### `src/cloud_training/gcp_vertex.py`
**Purpose:** Google Cloud Vertex AI adapter  
**Dependencies:** `google-cloud-aiplatform`, `google-cloud-storage`  
**Features:**
- Vertex AI CustomTrainingJob
- GCS data upload
- Training with GPU/CPU selection
- TensorBoard integration
- Model download

#### `src/cloud_training/azure_ml.py`
**Purpose:** Microsoft Azure ML adapter  
**Dependencies:** `azure-ai-ml`, `azure-identity`, `azure-storage-blob`  
**Features:**
- Azure ML SDK integration
- Blob storage data upload
- Command job submission
- Job monitoring
- Model download

#### `scripts/cloud_train.py` (CLI launcher)
**Purpose:** Unified CLI for submitting jobs to any cloud platform

**Usage:**
```bash
python -m scripts.cloud_train --platform [aws|gcp|azure] [options]
```

**Commands:**
1. Validate credentials
2. Upload training data
3. Submit job
4. Monitor status (optional)
5. Download model (optional)

### Configuration Files

#### `cloud_config/aws_training_config.json`
**Example config for AWS SageMaker**

#### `cloud_config/gcp_training_config.json`
**Example config for GCP Vertex AI**

#### `cloud_config/azure_training_config.json`
**Example config for Azure ML**

All configs use `TrainingConfig` schema:
```json
{
  "epochs": 50,
  "batch_size": 32,
  "learning_rate": 0.0003,
  "embed_dim": 128,
  "num_heads": 4,
  "num_layers": 4,
  "dropout": 0.1,
  "grad_clip": 1.0,
  "max_seq_len": 256,
  "val_split": 0.1,
  "patience": 10
}
```

### Data Files

#### `data/training/svara_sequences.jsonl`
**Format:** JSONL (JSON Lines) - one sequence per line  
**Schema:**
```json
{
  "raga": "shankarabharanam",
  "tala": "adi",
  "section": "pallavi",
  "svaras": ["Sa", "Ri2", "Ga2", "Ma1", "Pa", ...],
  "duration_ms": 4800
}
```

#### `data/models/svara_transformer.pt`
**PyTorch checkpoint containing:**
- Model state dict
- Config (vocab_size, embed_dim, etc.)
- Tokenizer vocabulary
- Training metadata (epoch, val_loss)

#### `data/ragas/{melakarta,janya}.json`
**Raga definitions:**
```json
{
  "shankarabharanam": {
    "raga_id": "shankarabharanam",
    "arohanam": ["Sa", "Ri2", "Ga2", "Ma1", "Pa", "Da2", "Ni2", "Sa"],
    "avarohanam": ["Sa", "Ni2", "Da2", "Pa", "Ma1", "Ga2", "Ri2", "Sa"]
  }
}
```

#### `data/talas/talas.json`
**Tala patterns and definitions**

### Documentation

#### `docs/model_training.md`
Local training guide with:
- Dataset preparation
- Training commands
- Hyperparameter explanations
- Hardware requirements

#### `docs/CLOUD_TRAINING.md`
Comprehensive cloud training guide with:
- Platform setup (AWS, GCP, Azure)
- Quick start commands
- Advanced configuration
- Cost optimization
- Troubleshooting
- CI/CD integration

#### `docs/CLOUD_TRAINING_SUMMARY.md`
High-level overview of cloud training with quick reference

### Environment & Dependencies

#### `.env.cloud.example`
Template for cloud credentials:
- AWS: ACCESS_KEY_ID, SECRET_ACCESS_KEY, REGION, ROLE_ARN, BUCKET
- GCP: PROJECT_ID, REGION, GCS_BUCKET
- Azure: SUBSCRIPTION_ID, RESOURCE_GROUP, WORKSPACE_NAME

#### `requirements-cloud.txt`
Cloud-specific Python packages:
- `boto3` (AWS)
- `google-cloud-aiplatform` (GCP)
- `azure-ai-ml` (Azure)
- `tensorboard`, `wandb` (monitoring)

### CI/CD

#### `.github/workflows/cloud-training.yml`
GitHub Actions workflow for automated cloud training:
- Build dataset
- Authenticate to cloud
- Upload data
- Submit training
- Monitor job
- Notify on completion

### Infrastructure

#### `infra/docker/Dockerfile.cloud-training`
Multi-cloud training Docker image:
- NVIDIA CUDA 12.1
- Python 3.12
- All ML dependencies
- Cloud SDKs (boto3, GCP SDK, Azure SDK)
- Entrypoint: Python training script

### Makefile Targets

#### New cloud training targets:
```makefile
make cloud-deps              # Install cloud dependencies
make cloud-train-aws         # AWS SageMaker (requires ROLE_ARN, BUCKET)
make cloud-train-gcp         # GCP Vertex AI (requires PROJECT_ID, BUCKET)
make cloud-train-azure       # Azure ML (requires SUBSCRIPTION_ID, RESOURCE_GROUP, WORKSPACE)
```

Example:
```bash
make ROLE_ARN=arn:... BUCKET=my-bucket cloud-train-aws --monitor
```

## Training Pipeline Summary

### Local Training Flow
```
build_dataset.py
    ↓
data/training/svara_sequences.jsonl
    ↓
train_model.py
    ↓
data/models/svara_transformer.pt
```

### Cloud Training Flow
```
build_dataset.py
    ↓
cloud_train.py --platform [aws|gcp|azure]
    ↓
Upload to cloud storage
    ↓
Cloud platform training service
    ↓
Download model locally
    ↓
data/models/svara_transformer.pt
```

## Total Training Files Created

**New files:** 12
**Updated files:** 2 (Makefile, pyproject.toml)
**Total training-related files:** 30+

## Dependencies to Install

### Local Only
```bash
pip install -e ".[neural]"  # torch, torchaudio
pip install -r requirements.txt
```

### Cloud Support
```bash
pip install -r requirements-cloud.txt
```

### Specific Platforms
```bash
pip install boto3                              # AWS
pip install google-cloud-aiplatform            # GCP
pip install azure-ai-ml azure-identity         # Azure
```

## Quick Reference

### Build Dataset
```bash
python -m scripts.build_dataset
```

### Train Locally
```bash
python -m scripts.train_model --epochs 50 --batch-size 32
```

### Train on AWS
```bash
python -m scripts.cloud_train --platform aws --role-arn <ARN> --bucket <BUCKET>
```

### Train on GCP
```bash
python -m scripts.cloud_train --platform gcp --project-id <PROJECT> --bucket <BUCKET>
```

### Train on Azure
```bash
python -m scripts.cloud_train --platform azure --subscription-id <ID> --resource-group <RG> --workspace-name <WS>
```

## Next Steps

1. Copy `.env.cloud.example` to `.env.cloud` and add credentials
2. Install cloud dependencies: `pip install -r requirements-cloud.txt`
3. Build training data: `python -m scripts.build_dataset`
4. Submit cloud job: `python -m scripts.cloud_train --platform [platform] [args]`
5. Monitor training and download model when complete
"""
