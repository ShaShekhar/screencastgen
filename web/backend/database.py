"""SQLAlchemy async engine and session factory."""

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from .config import settings

async_engine = create_async_engine(settings.DATABASE_URL, echo=False)
async_session_factory = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)

sync_engine = create_engine(settings.SYNC_DATABASE_URL, echo=False)
sync_session_factory = sessionmaker(sync_engine, class_=Session, expire_on_commit=False)


async def get_async_session():
    async with async_session_factory() as session:
        yield session


def get_sync_session() -> Session:
    return sync_session_factory()
