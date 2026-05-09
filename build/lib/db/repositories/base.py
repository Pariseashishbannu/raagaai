"""Generic CRUD repository base."""

from typing import TypeVar, Generic, Type
from uuid import UUID
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    def __init__(self, session: AsyncSession, model: Type[ModelT]):
        self.session = session
        self.model = model

    async def get_by_id(self, id_val) -> ModelT | None:
        return await self.session.get(self.model, id_val)

    async def get_all(self, limit: int = 100, offset: int = 0) -> list[ModelT]:
        result = await self.session.execute(
            select(self.model).limit(limit).offset(offset)
        )
        return list(result.scalars().all())

    async def create(self, obj: ModelT) -> ModelT:
        self.session.add(obj)
        await self.session.commit()
        await self.session.refresh(obj)
        return obj

    async def update(self, obj: ModelT) -> ModelT:
        await self.session.commit()
        await self.session.refresh(obj)
        return obj

    async def delete_by_id(self, id_val) -> bool:
        obj = await self.get_by_id(id_val)
        if obj:
            await self.session.delete(obj)
            await self.session.commit()
            return True
        return False
