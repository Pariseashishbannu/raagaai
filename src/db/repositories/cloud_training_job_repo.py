"""Repository for CloudTrainingJob queries."""

from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.models.cloud_training_job import CloudTrainingJob
from src.db.repositories.base import BaseRepository


class CloudTrainingJobRepository(BaseRepository[CloudTrainingJob]):
    """Repository for Cloud Training Job CRUD and queries."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, CloudTrainingJob)

    async def get_by_user(self, user_id: UUID, limit: int = 50) -> list[CloudTrainingJob]:
        """Get all training jobs for a user, ordered by newest first."""
        result = await self.session.execute(
            select(CloudTrainingJob)
            .where(CloudTrainingJob.user_id == user_id)
            .order_by(CloudTrainingJob.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_platform(self, platform: str, limit: int = 50) -> list[CloudTrainingJob]:
        """Get all training jobs on a specific platform."""
        result = await self.session.execute(
            select(CloudTrainingJob)
            .where(CloudTrainingJob.platform == platform)
            .order_by(CloudTrainingJob.submitted_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_pending_jobs(self, limit: int = 20) -> list[CloudTrainingJob]:
        """Get all jobs that are still running (submitted/queued/running)."""
        pending_statuses = ["submitted", "queued", "running"]
        result = await self.session.execute(
            select(CloudTrainingJob)
            .where(CloudTrainingJob.status.in_(pending_statuses))
            .order_by(CloudTrainingJob.submitted_at)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def update_status(
        self,
        job_id: UUID,
        status: str,
        stage: str | None = None,
        progress: float = 0.0,
        metrics: dict | None = None,
        error: str | None = None,
    ) -> CloudTrainingJob | None:
        """Update job status and optionally stage, progress, metrics, error."""
        job = await self.get_by_id(job_id)
        if job:
            job.status = status
            if stage is not None:
                job.current_stage = stage
            job.progress = progress
            if metrics is not None:
                job.metrics = metrics
            if error is not None:
                job.error_message = error
            await self.session.commit()
            await self.session.refresh(job)
        return job

    async def set_cloud_job_id(self, job_id: UUID, cloud_job_id: str) -> CloudTrainingJob | None:
        """Set the cloud platform job ID (ARN, resource name, etc.)."""
        job = await self.get_by_id(job_id)
        if job:
            job.cloud_job_id = cloud_job_id
            await self.session.commit()
            await self.session.refresh(job)
        return job

    async def set_model_download_url(self, job_id: UUID, url: str) -> CloudTrainingJob | None:
        """Set the URL for downloading the trained model."""
        job = await self.get_by_id(job_id)
        if job:
            job.model_download_url = url
            await self.session.commit()
            await self.session.refresh(job)
        return job

    async def get_by_cloud_job_id(self, cloud_job_id: str) -> CloudTrainingJob | None:
        """Get training job by its cloud platform job ID."""
        result = await self.session.execute(
            select(CloudTrainingJob).where(CloudTrainingJob.cloud_job_id == cloud_job_id)
        )
        return result.scalar_one_or_none()
