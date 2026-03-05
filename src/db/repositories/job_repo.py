"""Repository for GenerationJob queries."""

from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.models.generation_job import GenerationJob
from src.db.repositories.base import BaseRepository


class JobRepository(BaseRepository[GenerationJob]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, GenerationJob)

    async def get_by_user(self, user_id: UUID, limit: int = 50) -> list[GenerationJob]:
        result = await self.session.execute(
            select(GenerationJob)
            .where(GenerationJob.user_id == user_id)
            .order_by(GenerationJob.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_pending_jobs(self, limit: int = 10) -> list[GenerationJob]:
        result = await self.session.execute(
            select(GenerationJob)
            .where(GenerationJob.status == "queued")
            .order_by(GenerationJob.created_at)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def update_status(
        self, job_id: UUID, status: str, stage: str | None = None, progress: float = 0.0
    ) -> GenerationJob | None:
        job = await self.get_by_id(job_id)
        if job:
            job.status = status
            job.current_stage = stage
            job.progress = progress
            await self.session.commit()
        return job
