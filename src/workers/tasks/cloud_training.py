"""Celery tasks for cloud training job management.

Handles:
- Submitting training jobs to cloud platforms
- Polling job status periodically
- Downloading models when ready
- Cancelling jobs
"""

import asyncio
import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from celery import current_task
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from src.api.config import settings
from src.workers.celery_app import app
from src.db.repositories.cloud_training_job_repo import CloudTrainingJobRepository
from src.cloud_training.base import TrainingConfig

logger = logging.getLogger(__name__)


# Async session factory
async def get_async_session():
    """Create async DB session for Celery tasks."""
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
    )
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return async_session()


def _get_repo_sync(session):
    """Helper to get repository in sync context."""
    return CloudTrainingJobRepository(session)


@app.task(bind=True, name="submit_cloud_training", max_retries=2)
def submit_cloud_training_task(self, job_id: str, platform: str, config: dict):
    """Submit training job to cloud platform.

    Handles credential initialization, data upload, and job submission.
    """
    try:
        # Run async code
        asyncio.run(_submit_training_async(job_id, platform, config))
    except Exception as exc:
        logger.error(f"Failed to submit training job {job_id}: {exc}")
        # Retry up to max_retries times
        raise self.retry(exc=exc, countdown=60)


async def _submit_training_async(job_id: str, platform: str, config: dict):
    """Async handler for job submission."""
    session = await get_async_session()
    repo = _get_repo_sync(session)
    job_uuid = UUID(job_id)

    try:
        # Update status
        await repo.update_status(job_uuid, "queued", "preparing_data", 0.1)

        # Build training config
        train_config = TrainingConfig(**config)

        # Get appropriate trainer
        if platform == "aws":
            trainer = _get_aws_trainer(train_config)
        elif platform == "gcp":
            trainer = _get_gcp_trainer(train_config)
        elif platform == "azure":
            trainer = _get_azure_trainer(train_config)
        else:
            raise ValueError(f"Unknown platform: {platform}")

        # Validate credentials
        if not trainer.validate_credentials():
            raise RuntimeError(f"Invalid {platform.upper()} credentials")

        logger.info(f"Uploading training data for job {job_id}...")
        await repo.update_status(job_uuid, "queued", "uploading_data", 0.15)

        # Upload training data
        data_path = config.get("training_data_path", "data/training/svara_sequences.jsonl")
        if not Path(data_path).exists():
            raise FileNotFoundError(f"Training data not found: {data_path}")

        remote_path = f"data/training/svara_sequences.jsonl"
        if not trainer.upload_training_data(data_path, remote_path):
            raise RuntimeError("Failed to upload training data")

        logger.info(f"Submitting training job to {platform} for job {job_id}...")
        await repo.update_status(job_uuid, "queued", "submitting_job", 0.2)

        # Submit job
        cloud_job_id = trainer.submit_training_job(f"raaga-{job_id}")
        await repo.set_cloud_job_id(job_uuid, cloud_job_id)

        logger.info(f"Training job {job_id} submitted. Cloud job ID: {cloud_job_id}")
        await repo.update_status(job_uuid, "running", "training_started", 0.25)

        # Schedule polling task
        poll_cloud_training_task.apply_async(
            args=[job_id, platform, cloud_job_id],
            countdown=30,  # Start polling after 30 seconds
        )

    except Exception as e:
        logger.error(f"Error submitting training job {job_id}: {e}")
        await repo.update_status(
            job_uuid,
            "failed",
            error=f"Failed to submit: {str(e)}",
        )
        raise
    finally:
        await session.close()


@app.task(bind=True, name="poll_cloud_training", max_retries=999)
def poll_cloud_training_task(self, job_id: str, platform: str, cloud_job_id: str):
    """Poll cloud platform for job status.

    Runs periodically to check training progress and download model when ready.
    """
    try:
        asyncio.run(_poll_training_async(job_id, platform, cloud_job_id))
    except Exception as exc:
        logger.error(f"Error polling training job {job_id}: {exc}")
        # Retry every 60 seconds
        raise self.retry(exc=exc, countdown=60)


async def _poll_training_async(job_id: str, platform: str, cloud_job_id: str):
    """Async handler for job status polling."""
    session = await get_async_session()
    repo = _get_repo_sync(session)
    job_uuid = UUID(job_id)

    try:
        job = await repo.get_by_id(job_uuid)
        if not job:
            logger.warning(f"Job not found: {job_id}")
            return

        # Get trainer
        if platform == "aws":
            trainer = _get_aws_trainer(TrainingConfig(**job.config_json))
        elif platform == "gcp":
            trainer = _get_gcp_trainer(TrainingConfig(**job.config_json))
        elif platform == "azure":
            trainer = _get_azure_trainer(TrainingConfig(**job.config_json))
        else:
            raise ValueError(f"Unknown platform: {platform}")

        # Get status from cloud
        logger.info(f"Checking status of training job {job_id} on {platform}")
        status_info = trainer.get_job_status(cloud_job_id)
        cloud_status = status_info.get("status", "UNKNOWN")

        # Map cloud status to our status
        status_map = {
            "QUEUED": "queued",
            "RUNNING": "running",
            "SUCCESS": "completed",
            "FAILED": "failed",
            "CANCELLED": "cancelled",
        }
        our_status = status_map.get(cloud_status, "running")

        # Update job
        current_stage = _map_stage(cloud_status)
        progress = _calculate_progress(cloud_status)
        metrics = status_info.get("metrics", {})

        await repo.update_status(
            job_uuid,
            status=our_status,
            stage=current_stage,
            progress=progress,
            metrics=metrics,
        )

        logger.info(
            f"Training job {job_id}: status={our_status}, progress={progress:.1%}",
        )

        # If completed, download model
        if our_status == "completed":
            logger.info(f"Training job {job_id} completed. Downloading model...")
            await _download_model_async(job_id, platform, trainer)
        elif our_status == "failed":
            error_msg = status_info.get("error", "Unknown error")
            await repo.update_status(job_uuid, "failed", error=error_msg)
        else:
            # Keep polling
            poll_cloud_training_task.apply_async(
                args=[job_id, platform, cloud_job_id],
                countdown=60,  # Poll every 60 seconds
            )

    except Exception as e:
        logger.error(f"Error polling training job {job_id}: {e}")
        raise
    finally:
        await session.close()


async def _download_model_async(job_id: str, platform: str, trainer) -> None:
    """Download trained model from cloud storage."""
    session = await get_async_session()
    repo = _get_repo_sync(session)
    job_uuid = UUID(job_id)

    try:
        # Create local directory
        model_dir = Path("data/models") / job_id
        model_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Downloading model from {platform} to {model_dir}")

        # Download
        if trainer.download_model(str(job_uuid), str(model_dir)):
            model_path = model_dir / "svara_transformer.pt"
            if model_path.exists():
                # Generate download URL (simplified - in production, use signed URLs)
                download_url = f"/api/v1/training/cloud/{job_id}/model.pt"
                await repo.set_model_download_url(job_uuid, download_url)
                logger.info(f"Model downloaded for job {job_id}: {model_path}")
            else:
                logger.warning(f"Model file not found after download: {job_id}")
        else:
            logger.error(f"Failed to download model for job {job_id}")

    except Exception as e:
        logger.error(f"Error downloading model for job {job_id}: {e}")
    finally:
        await session.close()


@app.task(bind=True, name="cancel_cloud_training")
def cancel_cloud_training_task(self, job_id: str, platform: str, cloud_job_id: str):
    """Cancel a running training job on cloud platform."""
    try:
        asyncio.run(_cancel_training_async(job_id, platform, cloud_job_id))
    except Exception as exc:
        logger.error(f"Failed to cancel training job {job_id}: {exc}")
        raise


async def _cancel_training_async(job_id: str, platform: str, cloud_job_id: str):
    """Async handler for job cancellation."""
    session = await get_async_session()
    repo = _get_repo_sync(session)
    job_uuid = UUID(job_id)

    try:
        # Get trainer
        job = await repo.get_by_id(job_uuid)
        if not job:
            logger.warning(f"Job not found: {job_id}")
            return

        trainer_config = TrainingConfig(**job.config_json)

        if platform == "aws":
            trainer = _get_aws_trainer(trainer_config)
        elif platform == "gcp":
            trainer = _get_gcp_trainer(trainer_config)
        elif platform == "azure":
            trainer = _get_azure_trainer(trainer_config)
        else:
            raise ValueError(f"Unknown platform: {platform}")

        # Cancel job
        if trainer.cancel_job(cloud_job_id):
            await repo.update_status(job_uuid, "cancelled")
            logger.info(f"Training job {job_id} cancelled successfully")
        else:
            logger.error(f"Failed to cancel training job {job_id} on {platform}")

    except Exception as e:
        logger.error(f"Error cancelling training job {job_id}: {e}")
        raise
    finally:
        await session.close()


def _get_aws_trainer(config: TrainingConfig):
    """Create AWS SageMaker trainer."""
    from src.cloud_training.aws_sagemaker import SageMakerTrainer

    role_arn = os.getenv("AWS_SAGEMAKER_ROLE_ARN")
    bucket = os.getenv("AWS_S3_BUCKET")

    if not role_arn or not bucket:
        raise ValueError(
            "AWS_SAGEMAKER_ROLE_ARN and AWS_S3_BUCKET environment variables required"
        )

    return SageMakerTrainer(config=config, role_arn=role_arn, bucket=bucket)


def _get_gcp_trainer(config: TrainingConfig):
    """Create GCP Vertex AI trainer."""
    from src.cloud_training.gcp_vertex import VertexAITrainer

    project_id = os.getenv("GCP_PROJECT_ID")
    bucket = os.getenv("GCP_GCS_BUCKET")
    region = os.getenv("GCP_REGION", "us-central1")

    if not project_id or not bucket:
        raise ValueError(
            "GCP_PROJECT_ID and GCP_GCS_BUCKET environment variables required"
        )

    return VertexAITrainer(config=config, project_id=project_id, bucket=bucket, region=region)


def _get_azure_trainer(config: TrainingConfig):
    """Create Azure ML trainer."""
    from src.cloud_training.azure_ml import AzureMLTrainer

    subscription_id = os.getenv("AZURE_SUBSCRIPTION_ID")
    resource_group = os.getenv("AZURE_RESOURCE_GROUP")
    workspace_name = os.getenv("AZURE_WORKSPACE_NAME")

    if not all([subscription_id, resource_group, workspace_name]):
        raise ValueError(
            "AZURE_SUBSCRIPTION_ID, AZURE_RESOURCE_GROUP, AZURE_WORKSPACE_NAME required"
        )

    return AzureMLTrainer(
        config=config,
        subscription_id=subscription_id,
        resource_group=resource_group,
        workspace_name=workspace_name,
    )


def _map_stage(cloud_status: str) -> str:
    """Map cloud platform status to training stage."""
    stage_map = {
        "QUEUED": "queued",
        "PREPARING": "initializing_model",
        "RUNNING": "training",
        "FINALIZING": "finalizing_model",
        "SUCCESS": "completed",
        "FAILED": "failed",
    }
    return stage_map.get(cloud_status, "training")


def _calculate_progress(cloud_status: str) -> float:
    """Estimate progress based on cloud status."""
    progress_map = {
        "QUEUED": 0.1,
        "PREPARING": 0.2,
        "RUNNING": 0.5,
        "FINALIZING": 0.9,
        "SUCCESS": 1.0,
        "FAILED": 0.0,
    }
    return progress_map.get(cloud_status, 0.5)
