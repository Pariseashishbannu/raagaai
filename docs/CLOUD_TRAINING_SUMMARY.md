"""
# Cloud Training - Ready for Deployment

This directory contains all files needed to run SvaraTransformer training on cloud platforms.

## New Files Added

### Cloud Training Module (`src/cloud_training/`)
- **`base.py`** - Base trainer interface + TrainingConfig dataclass
- **`aws_sagemaker.py`** - AWS SageMaker adapter  
- **`gcp_vertex.py`** - Google Cloud Vertex AI adapter
- **`azure_ml.py`** - Microsoft Azure ML adapter
- **`__init__.py`** - Module exports

### Cloud Training CLI (`scripts/`)
- **`cloud_train.py`** - CLI launcher for submitting jobs to cloud platforms

### Configuration (`cloud_config/`)
- **`aws_training_config.json`** - AWS SageMaker training config
- **`gcp_training_config.json`** - GCP Vertex AI training config
- **`azure_training_config.json`** - Azure ML training config

### Docker (`infra/docker/`)
- **`Dockerfile.cloud-training`** - Multi-cloud training container

### Documentation (`docs/`)
- **`CLOUD_TRAINING.md`** - Comprehensive cloud training guide

## Quick Start

### 1. Prepare Data
```bash
python -m scripts.build_dataset --synthetic-per-raga 200
```

### 2. AWS SageMaker
```bash
pip install boto3

python -m scripts.cloud_train \
  --platform aws \
  --role-arn arn:aws:iam::123456789:role/SageMakerRole \
  --bucket my-bucket \
  --monitor
```

### 3. GCP Vertex AI
```bash
pip install google-cloud-aiplatform google-cloud-storage
gcloud auth application-default login

python -m scripts.cloud_train \
  --platform gcp \
  --project-id my-project \
  --bucket my-bucket \
  --monitor
```

### 4. Azure ML
```bash
pip install azure-ai-ml azure-identity
az login

python -m scripts.cloud_train \
  --platform azure \
  --subscription-id <ID> \
  --resource-group <RG> \
  --workspace-name <WS> \
  --monitor
```

## Features

✅ **Multi-Cloud Support** - AWS, GCP, Azure with single CLI interface  
✅ **Standard Config** - Unified TrainingConfig across platforms  
✅ **Automatic Monitoring** - Real-time job status and logs  
✅ **Model Download** - Auto-download trained models  
✅ **Data Upload** - Automatic training data sync to cloud  
✅ **Hyperparameter Control** - Full support for custom hyperparameters  
✅ **Docker Ready** - Pre-built image for cloud deployment  
✅ **Production Ready** - Error handling, logging, validation  

## Architecture

```
User CLI (cloud_train.py)
        ↓
BaseCloudTrainer (ABC)
    ↙        ↓        ↖
  AWS      GCP      Azure
SageMaker Vertex   Machine
         AI       Learning
```

Each trainer implements:
- `validate_credentials()` - Verify cloud access
- `upload_training_data()` - Sync data to cloud storage
- `submit_training_job()` - Launch training on cloud
- `get_job_status()` - Monitor job progress
- `download_model()` - Retrieve trained model
- `cancel_job()` - Stop running jobs

## Installation

Cloud SDKs are optional (only install what you need):

```bash
# AWS
pip install boto3

# GCP
pip install google-cloud-aiplatform google-cloud-storage

# Azure
pip install azure-ai-ml azure-identity azure-storage-blob

# All platforms
pip install boto3 google-cloud-aiplatform azure-ai-ml
```

## Environment Setup

### AWS
```bash
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export AWS_REGION=us-east-1
```

### GCP
```bash
gcloud auth application-default login
export GCP_PROJECT=your-project
```

### Azure
```bash
az login
export AZURE_SUBSCRIPTION_ID=your-id
```

## File Summary

| File | Purpose |
|------|---------|
| `src/cloud_training/base.py` | Abstract base trainer + config |
| `src/cloud_training/aws_sagemaker.py` | AWS SageMaker implementation |
| `src/cloud_training/gcp_vertex.py` | GCP Vertex AI implementation |
| `src/cloud_training/azure_ml.py` | Azure ML implementation |
| `scripts/cloud_train.py` | CLI entry point |
| `cloud_config/*.json` | Platform-specific configs |
| `docs/CLOUD_TRAINING.md` | Full documentation |
| `infra/docker/Dockerfile.cloud-training` | Training container image |

## Testing Cloud Trainers

```python
from src.cloud_training.base import TrainingConfig
from src.cloud_training.aws_sagemaker import SageMakerTrainer

# AWS
config = TrainingConfig(epochs=50, batch_size=32)
trainer = SageMakerTrainer(config, role_arn="...", bucket="...")
trainer.validate_credentials()  # Check connection
job_id = trainer.submit_training_job("test-job")
status = trainer.get_job_status(job_id)
```

## Troubleshooting

- **Import Error**: Install cloud SDK with `pip install boto3` (AWS), `pip install google-cloud-aiplatform` (GCP), etc.
- **Auth Failed**: Check credentials (AWS IAM, GCP service account, Azure CLI)
- **Job Fails**: Check logs on cloud platform dashboard
- **Model Not Found**: Verify training completed and model was saved to cloud storage

See `docs/CLOUD_TRAINING.md` for detailed troubleshooting.

## Next: Convert Local Training to Use Cloud

To integrate cloud training into your main API:

```python
# In src/api/routers/training.py (new endpoint)
from src.cloud_training.aws_sagemaker import SageMakerTrainer

@router.post("/training/cloud")
async def start_cloud_training(
    platform: str,  # "aws", "gcp", "azure"
    config: TrainingConfig,
    credentials: dict
):
    trainer = CloudTrainerFactory.create(platform, config, credentials)
    job_id = trainer.submit_training_job(f"raaga-{datetime.now()}")
    return {"job_id": job_id, "status": "SUBMITTED"}
```

## Related Files

- [docs/model_training.md](model_training.md) - Local training guide
- [docs/BACKEND_ARCHITECTURE.md](BACKEND_ARCHITECTURE.md) - System architecture
- [scripts/train_model.py](../scripts/train_model.py) - Original training script
- [scripts/build_dataset.py](../scripts/build_dataset.py) - Dataset preparation
"""
