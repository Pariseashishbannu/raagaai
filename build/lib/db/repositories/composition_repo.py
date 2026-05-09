"""Repository for Composition queries."""

from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.models.composition import Composition
from src.db.repositories.base import BaseRepository


class CompositionRepository(BaseRepository[Composition]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Composition)

    async def get_by_user(self, user_id: UUID, limit: int = 50) -> list[Composition]:
        result = await self.session.execute(
            select(Composition)
            .where(Composition.user_id == user_id)
            .order_by(Composition.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_job_id(self, job_id: UUID) -> Composition | None:
        result = await self.session.execute(
            select(Composition).where(Composition.job_id == job_id)
        )
        return result.scalar_one_or_none()

    async def get_public(self, limit: int = 50) -> list[Composition]:
        result = await self.session.execute(
            select(Composition)
            .where(Composition.is_public.is_(True))
            .order_by(Composition.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
