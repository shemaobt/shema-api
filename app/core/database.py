from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings
from app.core.db_url import async_database_url, ssl_connect_args


class Base(DeclarativeBase):
    pass


settings = get_settings()
_raw_url = settings.database_url
engine = create_async_engine(
    async_database_url(_raw_url),
    pool_pre_ping=True,
    connect_args=ssl_connect_args(_raw_url),
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def init_db() -> None:
    return None


async def close_db() -> None:
    await engine.dispose()
