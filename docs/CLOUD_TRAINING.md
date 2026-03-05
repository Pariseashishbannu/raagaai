"""
# Cloud Training Guide

This guide explains how to train the SvaraTransformer model on cloud platforms:
- AWS SageMaker
- Google Cloud Platform Vertex AI
- Microsoft Azure Machine Learning

## Overview

The cloud training infrastructure allows you to:
- Train models on powerful GPUs without local hardware
- Scale training across multiple instances
- Monitor training with cloud-native tools (CloudWatch, Vertex AI Workbench, Azure ML Studio)
- Automatically checkpoint and save models
- Handle large datasets efficiently

## Prerequisites

### All Platforms
- Training data at `data/training/svara_sequences.jsonl` (generate with `python -m scripts.build_dataset`)
- Docker installed (for building custom training container)
- Appropriate cloud SDK/CLI installed

### AWS SageMaker
```bash
pip install boto3
```

Setup:
1. Create AWS account and S3 bucket
2. Create IAM role with SageMaker permissions
3. Note role ARN: `arn:aws:iam::ACCOUNT:role/ROLE`

### GCP Vertex AI
```bash
pip install google-cloud-aiplatform google-cloud-storage
```

Setup:
1. Create GCP project and GCS bucket
2. Enable Vertex AI API
3. Set up Application Default Credentials:
   ```bash
   gcloud auth application-default login
   ```

### Azure ML
```bash
pip install azure-ai-ml azure-identity azure-storage-blob
```

Setup:
1. Create Azure subscription and resource group
2. Create Azure ML workspace
3. Authenticate:
   ```bash
   az login
   ```

## Quick Start

### 1. Prepare Training Data

```bash
# Generate synthetic training data
python -m scripts.build_dataset --synthetic-per-raga 200

# Or use full pipeline with web scraping
python -m scripts.build_dataset --synthetic-per-raga 500 --scrape-web --max-web-pages 100
```

### 2. Upload Code and Data to Cloud

#### AWS S3
```bash
aws s3 sync . s3://my-bucket/raaga-ai/ --exclude ".git/*" --exclude ".venv/*" --exclude "__pycache__/*"
```

#### GCS
```bash
gsutil -m cp -r . gs://my-bucket/raaga-ai/
```

#### Azure Blob Storage
```bash
az storage blob upload-batch -d raaga-ai -s . --connection-string "DefaultEndpointProtocol=https;..."
```

### 3. Submit Training Job

#### AWS SageMaker

```bash
python -m scripts.cloud_train \
  --platform aws \
  --role-arn arn:aws:iam::123456789:role/SageMakerRole \
  --bucket my-bucket \
  --job-name raaga-ai-training-001 \
  --monitor
```

**Configuration** (`cloud_config/aws_training_config.json`):
```json
{
  "epochs": 50,
  "batch_size": 32,
  "learning_rate": 0.0003,
  "machine_type": "ml.g4dn.xlarge",
  "num_gpus": 1
}
```

#### GCP Vertex AI

```bash
python -m scripts.cloud_train \
  --platform gcp \
  --project-id my-project \
  --bucket my-bucket \
  --region us-central1 \
  --job-name raaga-ai-training-001 \
  --monitor
```

**Configuration** (`cloud_config/gcp_training_config.json`):
```json
{
  "epochs": 50,
  "batch_size": 32,
  "learning_rate": 0.0003,
  "machine_type": "n1-standard-4",
  "gpu_type": "NVIDIA_TESLA_T4",
  "num_gpus": 1
}
```

#### Azure ML

```bash
python -m scripts.cloud_train \
  --platform azure \
  --subscription-id xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx \
  --resource-group my-rg \
  --workspace-name my-workspace \
  --job-name raaga-ai-training-001 \
  --monitor
```

**Configuration** (`cloud_config/azure_training_config.json`):
```json
{
  "epochs": 50,
  "batch_size": 32,
  "learning_rate": 0.0003,
  "machine_type": "Standard_NC6",
  "num_gpus": 1
}
```

### 4. Monitor Training

The CLI automatically monitors training when `--monitor` is used, but you can also check manually:

#### AWS CloudWatch
```bash
# View logs
aws logs tail /aws/sagemaker/TrainingJobs/raaga-ai-training-001 --follow

# Get job status
aws sagemaker describe-training-job --training-job-name raaga-ai-training-001
```

#### GCP Vertex AI
```bash
# View in console
gcloud ai custom-jobs describe "raaga-ai-training-001"

# Monitor logs
gcloud ai custom-jobs stream-logs "raaga-ai-training-001"
```

#### Azure ML
```bash
# View in portal or CLI
az ml job show -n raaga-ai-training-001 -g my-rg -w my-workspace

# Stream logs
az ml job stream -n raaga-ai-training-001 -g my-rg -w my-workspace
```

### 5. Download Trained Model

```bash
# After training completes
python -m scripts.cloud_train \
  --platform [aws|gcp|azure] \
  [platform-specific args] \
  --download ./models/
```

Or manually download from cloud storage:

#### AWS S3
```bash
aws s3 cp s3://my-bucket/models/svara_transformer.pt data/models/
```

#### GCS
```bash
gsutil cp gs://my-bucket/models/svara_transformer.pt data/models/
```

#### Azure Blob Storage
```bash
az storage blob download \
  --container-name raaga-ai \
  --name models/svara_transformer.pt \
  --file data/models/svara_transformer.pt \
  --connection-string "..."
```

## Advanced Configuration

### Custom Hyperparameters

Edit the platform-specific JSON config files:

```json
{
  "epochs": 100,
  "batch_size": 64,
  "learning_rate": 0.0001,
  "embed_dim": 256,
  "num_heads": 8,
  "num_layers": 6,
  "dropout": 0.2,
  "grad_clip": 1.0,
  "max_seq_len": 512,
  "val_split": 0.1,
  "patience": 15
}
```

Then submit with:
```bash
python -m scripts.cloud_train --platform [platform] --config cloud_config/custom_config.json [args...]
```

### Multi-GPU Training

To enable multi-GPU training, modify the config:

**AWS SageMaker:**
```json
{
  "machine_type": "ml.p3.8xlarge",
  "num_gpus": 4
}
```

**GCP Vertex AI:**
```json
{
  "machine_type": "n1-standard-32",
  "gpu_type": "NVIDIA_TESLA_V100",
  "num_gpus": 4
}
```

**Azure ML:**
```json
{
  "machine_type": "Standard_ND40s_v2",
  "num_gpus": 8
}
```

### TensorBoard Monitoring

Training now automatically logs to TensorBoard. Access it:

#### AWS SageMaker
Logs saved to `s3://bucket/tb-logs/` - download and view locally:
```bash
aws s3 sync s3://my-bucket/tb-logs/ ./tb-logs/
tensorboard --logdir ./tb-logs/
```

#### GCP Vertex AI
View directly in Vertex AI Workbench or the web UI.

#### Azure ML
View in Azure ML Studio under "Jobs" → "Metrics".

## Cost Optimization

### Spot Instances (AWS)
Reduce costs by 70%+ using spot instances:

In AWS config, add to `create_training_job`:
```python
UseSpotInstances=True,
MaxWaitTimeInSeconds=86400,
```

### Preemptible VMs (GCP)
Use preemptible nodes for 70%+ savings. Modify `machine_type`:
```json
{
  "machine_type": "n1-standard-4-preemptible"
}
```

### Low-Priority VMs (Azure)
Edit Azure ML config to use low-priority VMs.

## Troubleshooting

### Issue: "Credentials validation failed"

**AWS:**
```bash
aws sts get-caller-identity  # Verify credentials
```

**GCP:**
```bash
gcloud auth list  # Check active account
gcloud config list  # Check project
```

**Azure:**
```bash
az account show  # Verify subscription
```

### Issue: "Training data not found"

Ensure data is uploaded to cloud storage first:

```bash
# AWS S3
aws s3 ls s3://my-bucket/data/training/

# GCS
gsutil ls gs://my-bucket/data/training/

# Azure
az storage blob list -c raaga-ai --prefix data/training/
```

### Issue: "Out of memory (OOM)"

Reduce batch size in config:
```json
{
  "batch_size": 16
}
```

Or use a larger instance type.

### Issue: "Job cancelled/timeout"

For very large models, increase job timeout. For AWS SageMaker:
```python
StoppingCondition={"MaxRuntimeInSeconds": 172800}  # 48 hours
```

## File Structure

The cloud training module integrates with the existing Raaga.AI structure:

```
src/cloud_training/          # New cloud training module
  __init__.py
  base.py                    # Base trainer interface + TrainingConfig
  aws_sagemaker.py          # AWS SageMaker adapter
  gcp_vertex.py             # GCP Vertex AI adapter
  azure_ml.py               # Azure ML adapter

scripts/
  cloud_train.py            # Cloud training CLI launcher
  train_model.py            # (existing) Local training script
  build_dataset.py          # (existing) Dataset builder

cloud_config/               # New cloud configuration
  aws_training_config.json
  gcp_training_config.json
  azure_training_config.json

infra/docker/
  Dockerfile.cloud-training # New cloud training Docker image
```

## Integration with CI/CD

You can trigger cloud training from GitHub Actions, GitLab CI, or cloud-native CI tools:

### GitHub Actions Example

```yaml
name: Cloud Training

on:
  workflow_dispatch:
    inputs:
      platform:
        description: 'Cloud platform (aws|gcp|azure)'
        required: true
      epochs:
        description: 'Number of epochs'
        required: false
        default: '50'

jobs:
  cloud-train:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Build training data
        run: python -m scripts.build_dataset
      
      - name: Submit to cloud
        run: |
          python -m scripts.cloud_train \
            --platform ${{ github.event.inputs.platform }} \
            --job-name "raaga-training-${{ github.run_id }}" \
            --monitor
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          GCP_PROJECT_ID: ${{ secrets.GCP_PROJECT_ID }}
          GCP_SERVICE_ACCOUNT: ${{ secrets.GCP_SERVICE_ACCOUNT }}
```

## Next Steps

1. **Monitor training** - Use cloud platform dashboards
2. **Download model** - Save to local `data/models/`
3. **Evaluate model** - Run inference tests
4. **Update API** - Deploy updated model to production
5. **Cleanup resources** - Delete training jobs and temporary storage

See [docs/model_training.md](../docs/model_training.md) for local training reference.
"""
