"""Async SQLAlchemy session factory."""

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from src.api.config import settings

engine = create_async_engine(
    settings.DATABASE_URL, echo=settings.APP_DEBUG, pool_size=5,
    connect_args={"timeout": 3},
)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    """Import models so they register with Base.metadata."""
    from src.db.models import user, composition, generation_job, raga, tala  # noqa: F401


async def close_db():
    await engine.dispose()


async def get_session():
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
