from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from app.config import settings

engine = create_async_engine(settings.database_url, future=True)
_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def create_all() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with _session_factory() as session:
        yield session
