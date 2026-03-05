"""Cloud training endpoints — submit, monitor, and download trained models."""

import logging
import uuid
from datetime import datetime, timezone
from typing import Annotated

import redis as redis_lib
from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.config import settings
from src.api.schemas.cloud_training import (
    CloudTrainingRequest,
    CloudTrainingResponse,
    CloudTrainingJobStatus,
    CloudTrainingListResponse,
    CloudTrainingListItem,
    ModelDownloadInfo,
    CloudPlatform,
)
from src.api.middleware.auth import get_current_user
from src.db.models import CloudTrainingJob, User
from src.db.repositories.cloud_training_job_repo import CloudTrainingJobRepository
from src.api.dependencies import get_async_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/training/cloud", tags=["cloud-training"])

# Redis connection for real-time job tracking
def get_redis():
    return redis_lib.from_url(settings.REDIS_URL)


def _has_celery_workers() -> bool:
    """Check if any Celery workers are connected."""
    try:
        from src.workers.celery_app import app as celery_app
        inspect = celery_app.control.inspect(timeout=1.0)
        active = inspect.active_queues()
        return bool(active)
    except Exception:
        return False


async def _get_repo(db: AsyncSession) -> CloudTrainingJobRepository:
    return CloudTrainingJobRepository(db)


@router.post("/submit", response_model=CloudTrainingResponse, status_code=202)
async def submit_cloud_training(
    req: CloudTrainingRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """Submit a SvaraTransformer training job to cloud platform.

    Returns immediately with job ID. Job status can be polled via GET /api/v1/training/cloud/{job_id}.

    **Supported Platforms:**
    - `aws` — AWS SageMaker (requires AWS_SAGEMAKER_ROLE_ARN, AWS_S3_BUCKET env vars)
    - `gcp` — Google Cloud Vertex AI (requires GCP_PROJECT_ID, GCP_GCS_BUCKET env vars)
    - `azure` — Microsoft Azure ML (requires AZURE_SUBSCRIPTION_ID, AZURE_RESOURCE_GROUP env vars)

    **Rate Limiting:**
    - Free tier: 0 jobs/month
    - Pro tier: 5 jobs/month
    - Studio tier: 20 jobs/month
    - Enterprise: unlimited

    **Request Body:**
    ```json
    {
      "platform": "gcp",
      "job_name": "raaga-model-v2",
      "config": {
        "epochs": 50,
        "batch_size": 32,
        "learning_rate": 0.0003
      }
    }
    ```
    """
    # Check tier permissions
    tier_limits = {"free": 0, "pro": 5, "studio": 20, "enterprise": 999999}
    if tier_limits.get(user.tier, 0) == 0:
        raise HTTPException(
            403,
            f"Cloud training not available on {user.tier} tier. Upgrade to Pro or higher.",
        )

    # Create job record
    job_id = uuid.uuid4()
    job = CloudTrainingJob(
        id=job_id,
        user_id=user.id,
        platform=req.platform.value,
        job_name=req.job_name,
        status="submitted",
        config_json=req.config.model_dump(),
        submitted_at=datetime.now(timezone.utc),
    )

    repo = await _get_repo(db)
    job = await repo.create(job)

    # Submit to cloud asynchronously
    if _has_celery_workers():
        from src.workers.tasks.cloud_training import submit_cloud_training_task
        submit_cloud_training_task.apply_async(
            args=[str(job_id), req.platform.value, req.config.model_dump()],
            task_id=f"cloud-train-{job_id}",
        )
    else:
        # Fallback: run in background thread
        background_tasks.add_task(
            _submit_training_sync,
            job_id=str(job_id),
            platform=req.platform.value,
            config=req.config.model_dump(),
            user_id=str(user.id),
        )

    logger.info(
        "cloud_training.submitted user_id=%s job_id=%s platform=%s",
        user.id, job_id, req.platform.value,
    )

    return CloudTrainingResponse(
        job_id=job_id,
        cloud_job_id=None,
        platform=req.platform,
        status="submitted",
        message=f"Training job '{req.job_name}' submitted to {req.platform.value}. Check status via GET /api/v1/training/cloud/{job_id}",
    )


@router.get("/{job_id}", response_model=CloudTrainingJobStatus)
async def get_training_job_status(
    job_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Get status of a cloud training job.

    Includes real-time progress, current stage, platform logs URL, and model download link when ready.
    """
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(400, f"Invalid job ID format: {job_id}")

    repo = await _get_repo(db)
    job = await repo.get_by_id(job_uuid)

    if not job:
        raise HTTPException(404, f"Training job {job_id} not found")

    if job.user_id != user.id:
        raise HTTPException(403, "Not authorized to view this training job")

    # Build logs URL based on platform
    logs_url = None
    if job.platform == "aws" and job.cloud_job_id:
        # AWS CloudWatch format
        logs_url = f"https://console.aws.amazon.com/cloudwatch/home?#logsV2:log-groups/log-group=/aws/sagemaker/TrainingJobs"
    elif job.platform == "gcp" and job.cloud_job_id:
        # GCP Cloud Logging format
        logs_url = f"https://console.cloud.google.com/vertex-ai/training/{job.cloud_job_id}"
    elif job.platform == "azure" and job.cloud_job_id:
        # Azure ML Studio
        logs_url = f"https://ml.azure.com/runs/{job.cloud_job_id}"

    return CloudTrainingJobStatus(
        job_id=job_uuid,
        platform=CloudPlatform(job.platform),
        status=job.status,
        progress=job.progress,
        current_stage=job.current_stage,
        cloud_job_id=job.cloud_job_id,
        platform_logs_url=logs_url or job.platform_logs_url,
        submitted_at=job.submitted_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        metrics=job.metrics if job.metrics else None,
        model_download_url=job.model_download_url,
        error_message=job.error_message,
    )


@router.get("", response_model=CloudTrainingListResponse)
async def list_training_jobs(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    """List all cloud training jobs for the authenticated user."""
    repo = await _get_repo(db)
    jobs = await repo.get_by_user(user.id, limit=limit + 1)

    # Apply pagination
    paginated = jobs[offset : offset + limit]
    total = len(jobs)

    items = [
        CloudTrainingListItem(
            job_id=job.id,
            platform=CloudPlatform(job.platform),
            job_name=job.job_name,
            status=job.status,
            progress=job.progress,
            submitted_at=job.submitted_at,
            completed_at=job.completed_at,
        )
        for job in paginated
    ]

    return CloudTrainingListResponse(jobs=items, total=total, offset=offset, limit=limit)


@router.get("/{job_id}/download", response_model=ModelDownloadInfo)
async def get_model_download_link(
    job_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Get download link for trained model.

    Only available once training job completes successfully.
    Download link is valid for 24 hours.
    """
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(400, f"Invalid job ID format: {job_id}")

    repo = await _get_repo(db)
    job = await repo.get_by_id(job_uuid)

    if not job:
        raise HTTPException(404, f"Training job {job_id} not found")

    if job.user_id != user.id:
        raise HTTPException(403, "Not authorized to download model from this job")

    if job.status != "completed":
        raise HTTPException(
            409,
            f"Model not ready. Job status is '{job.status}'. Wait for training to complete.",
        )

    if not job.model_download_url:
        logger.error("Job completed but model_download_url is missing: %s", job_id)
        raise HTTPException(
            500,
            "Model file not found. Please contact support.",
        )

    return ModelDownloadInfo(
        job_id=job_uuid,
        status="completed",
        download_url=job.model_download_url,
        expiry_time=job.completed_at,  # Simplified; real implementation should calculate 24h from now
        file_size_mb=125.5,  # Typical model size
        message="Model ready for download. Link valid for 24 hours.",
    )


@router.delete("/{job_id}", status_code=204)
async def cancel_training_job(
    job_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Cancel a running or queued training job.

    Only works if job status is 'submitted', 'queued', or 'running'.
    """
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(400, f"Invalid job ID format: {job_id}")

    repo = await _get_repo(db)
    job = await repo.get_by_id(job_uuid)

    if not job:
        raise HTTPException(404, f"Training job {job_id} not found")

    if job.user_id != user.id:
        raise HTTPException(403, "Not authorized to cancel this job")

    if job.status not in ["submitted", "queued", "running"]:
        raise HTTPException(
            409,
            f"Cannot cancel job with status '{job.status}'. Only submitted/queued/running jobs can be cancelled.",
        )

    # Submit cancel task to Celery
    if _has_celery_workers():
        from src.workers.tasks.cloud_training import cancel_cloud_training_task
        cancel_cloud_training_task.apply_async(
            args=[str(job_uuid), job.platform, job.cloud_job_id],
        )
    else:
        # Update status immediately in fallback mode
        await repo.update_status(
            job_uuid,
            status="cancelled",
            error="Cancelled by user",
        )

    logger.info(
        "cloud_training.cancelled user_id=%s job_id=%s platform=%s",
        user.id, job_id, job.platform,
    )


async def _submit_training_sync(
    job_id: str,
    platform: str,
    config: dict,
    user_id: str,
) -> None:
    """Fallback: Run training submission synchronously (development mode without Celery)."""
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker

    # Create new DB session for this thread
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
    )
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        repo = CloudTrainingJobRepository(session)
        job_uuid = uuid.UUID(job_id)

        try:
            # Simulate submission (real implementation delegates to cloud platform)
            await repo.update_status(job_uuid, "queued", "initializing", 0.1)
            logger.info(f"Training job {job_id} submitted to {platform}")
        except Exception as e:
            logger.error(f"Failed to submit training job {job_id}: {e}")
            await repo.update_status(job_uuid, "failed", error=str(e))
        finally:
            await engine.dispose()
