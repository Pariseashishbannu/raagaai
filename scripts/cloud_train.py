"""Cloud training launcher CLI.

Usage:
    python -m scripts.cloud_train [--platform aws|gcp|azure] [--config CONFIG.json]
    
Examples:
    # AWS SageMaker
    python -m scripts.cloud_train --platform aws --role-arn arn:aws:iam::ACCOUNT:role/ROLE --bucket my-bucket
    
    # GCP Vertex AI
    python -m scripts.cloud_train --platform gcp --project-id my-project --bucket my-bucket
    
    # Azure ML
    python -m scripts.cloud_train --platform azure --subscription-id <ID> --resource-group <RG> --workspace <WS>
"""

import argparse
import json
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def setup_aws_trainer(args):
    """Setup AWS SageMaker trainer."""
    from src.cloud_training.aws_sagemaker import SageMakerTrainer
    from src.cloud_training.base import TrainingConfig

    config_file = args.config or "cloud_config/aws_training_config.json"
    if Path(config_file).exists():
        with open(config_file) as f:
            config_dict = json.load(f)
        config = TrainingConfig(**config_dict)
    else:
        config = TrainingConfig()

    trainer = SageMakerTrainer(
        config=config, role_arn=args.role_arn, bucket=args.bucket
    )

    if not trainer.validate_credentials():
        logger.error("Failed to validate AWS credentials")
        return None

    return trainer


def setup_gcp_trainer(args):
    """Setup GCP Vertex AI trainer."""
    from src.cloud_training.gcp_vertex import VertexAITrainer
    from src.cloud_training.base import TrainingConfig

    config_file = args.config or "cloud_config/gcp_training_config.json"
    if Path(config_file).exists():
        with open(config_file) as f:
            config_dict = json.load(f)
        config = TrainingConfig(**config_dict)
    else:
        config = TrainingConfig()

    trainer = VertexAITrainer(
        config=config,
        project_id=args.project_id,
        bucket=args.bucket,
        region=args.region or "us-central1",
    )

    if not trainer.validate_credentials():
        logger.error("Failed to validate GCP credentials")
        return None

    return trainer


def setup_azure_trainer(args):
    """Setup Azure ML trainer."""
    from src.cloud_training.azure_ml import AzureMLTrainer
    from src.cloud_training.base import TrainingConfig

    config_file = args.config or "cloud_config/azure_training_config.json"
    if Path(config_file).exists():
        with open(config_file) as f:
            config_dict = json.load(f)
        config = TrainingConfig(**config_dict)
    else:
        config = TrainingConfig()

    trainer = AzureMLTrainer(
        config=config,
        subscription_id=args.subscription_id,
        resource_group=args.resource_group,
        workspace_name=args.workspace_name,
    )

    if not trainer.validate_credentials():
        logger.error("Failed to validate Azure ML credentials")
        return None

    return trainer


def upload_data(trainer, data_path: str) -> bool:
    """Upload training data to cloud."""
    if not Path(data_path).exists():
        logger.error(f"Training data not found: {data_path}")
        return False

    logger.info(f"Uploading training data from {data_path}...")
    remote_path = "data/training/svara_sequences.jsonl"
    return trainer.upload_training_data(data_path, remote_path)


def submit_job(trainer, job_name: str) -> str | None:
    """Submit training job to cloud."""
    logger.info(f"Submitting training job: {job_name}")
    try:
        job_id = trainer.submit_training_job(job_name)
        logger.info(f"✓ Job submitted successfully!")
        logger.info(f"  Job ID: {job_id}")
        return job_id
    except Exception as e:
        logger.error(f"✗ Failed to submit job: {e}")
        return None


def monitor_job(trainer, job_id: str):
    """Monitor training job status."""
    import time

    logger.info(f"Monitoring job {job_id}...")
    logger.info("(Press Ctrl+C to stop monitoring)\n")

    try:
        while True:
            status_info = trainer.get_job_status(job_id)
            status = status_info.get("status", "UNKNOWN")

            logger.info(f"Status: {status}")
            for key, value in status_info.items():
                if key != "status":
                    logger.info(f"  {key}: {value}")

            if status in ["SUCCESS", "FAILED", "CANCELLED"]:
                logger.info(f"\n✓ Job finished with status: {status}")
                break

            logger.info("  Checking again in 60 seconds...")
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("\nStopped monitoring.")


def download_model(trainer, job_id: str, output_dir: str) -> bool:
    """Download trained model from cloud."""
    logger.info(f"Downloading model to {output_dir}...")
    return trainer.download_model(job_id, output_dir)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="Cloud training launcher for SvaraTransformer")

    # Platform selection
    parser.add_argument(
        "--platform",
        choices=["aws", "gcp", "azure"],
        required=True,
        help="Cloud platform to use",
    )

    # Shared arguments
    parser.add_argument(
        "--config",
        type=str,
        help="Training config JSON file (defaults to platform-specific config)",
    )
    parser.add_argument(
        "--data",
        type=str,
        default="data/training/svara_sequences.jsonl",
        help="Path to training data",
    )
    parser.add_argument(
        "--job-name",
        type=str,
        default="raaga-ai-training",
        help="Name for the training job",
    )
    parser.add_argument(
        "--monitor",
        action="store_true",
        help="Monitor job status after submission",
    )
    parser.add_argument(
        "--download",
        type=str,
        help="Download model after training (specify output directory)",
    )

    # AWS arguments
    parser.add_argument("--role-arn", type=str, help="[AWS] SageMaker execution role ARN")
    parser.add_argument("--bucket", type=str, help="[AWS/GCP] Cloud storage bucket name")

    # GCP arguments
    parser.add_argument("--project-id", type=str, help="[GCP] GCP project ID")
    parser.add_argument("--region", type=str, help="[GCP] GCP region (default: us-central1)")

    # Azure arguments
    parser.add_argument("--subscription-id", type=str, help="[Azure] Azure subscription ID")
    parser.add_argument("--resource-group", type=str, help="[Azure] Azure resource group")
    parser.add_argument("--workspace-name", type=str, help="[Azure] Azure ML workspace name")

    args = parser.parse_args()

    # Setup trainer based on platform
    logger.info(f"Setting up {args.platform.upper()} training...")

    if args.platform == "aws":
        if not all([args.role_arn, args.bucket]):
            parser.error("AWS requires --role-arn and --bucket")
        trainer = setup_aws_trainer(args)
    elif args.platform == "gcp":
        if not all([args.project_id, args.bucket]):
            parser.error("GCP requires --project-id and --bucket")
        trainer = setup_gcp_trainer(args)
    elif args.platform == "azure":
        if not all([args.subscription_id, args.resource_group, args.workspace_name]):
            parser.error("Azure requires --subscription-id, --resource-group, and --workspace-name")
        trainer = setup_azure_trainer(args)

    if not trainer:
        logger.error("Failed to initialize trainer")
        sys.exit(1)

    # Upload training data
    if not upload_data(trainer, args.data):
        logger.error("Failed to upload training data")
        sys.exit(1)

    # Submit training job
    job_id = submit_job(trainer, args.job_name)
    if not job_id:
        sys.exit(1)

    # Monitor job if requested
    if args.monitor:
        monitor_job(trainer, job_id)

    # Download model if requested
    if args.download:
        if download_model(trainer, job_id, args.download):
            logger.info(f"✓ Model available at: {args.download}")
        else:
            logger.warning("Failed to download model")

    logger.info(f"\n✓ Training job ID: {job_id}")


if __name__ == "__main__":
    main()
