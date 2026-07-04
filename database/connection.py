"""
Two session stacks:
- ASYNC (asyncpg/aiosqlite) — for the aiogram bot and anything with an event loop.
- SYNC (psycopg2) — for Celery tasks and Alembic, where blocking is fine.

Note: expire_on_commit=False means lazy loading of relationships does NOT work
in async sessions — use selectinload() when you need related objects.
"""
from contextlib import asynccontextmanager, contextmanager
from typing import AsyncGenerator, Generator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool, StaticPool

from config.settings import settings
from database.models import Base


def _to_async_url(url: str) -> str:
    if url.startswith(("postgresql+asyncpg://", "sqlite+aiosqlite://")):
        return url
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("sqlite://"):
        return url.replace("sqlite://", "sqlite+aiosqlite://", 1)
    return url


_is_sqlite = settings.database_url.startswith("sqlite")
_pool_kwargs = (
    {"poolclass": StaticPool, "connect_args": {"check_same_thread": False}}
    if _is_sqlite
    else {"poolclass": QueuePool, "pool_size": 10, "max_overflow": 20,
          "pool_pre_ping": True, "pool_recycle": 3600}
)

engine = create_engine(settings.database_url, echo=settings.debug, **_pool_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

_async_pool_kwargs = (
    {"poolclass": StaticPool, "connect_args": {"check_same_thread": False}}
    if _is_sqlite
    else {"pool_size": 10, "max_overflow": 20, "pool_pre_ping": True, "pool_recycle": 3600}
)
async_engine = create_async_engine(
    _to_async_url(settings.database_url), echo=settings.debug, **_async_pool_kwargs
)
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine, class_=AsyncSession, autoflush=False, expire_on_commit=False
)


def init_db():
    """Create tables (called once at startup; switch to Alembic as schema evolves)."""
    Base.metadata.create_all(bind=engine)


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """Sync session for Celery tasks: `with get_db() as db:`"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@asynccontextmanager
async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """Async session for bot handlers: `async with get_async_db() as db:`"""
    db = AsyncSessionLocal()
    try:
        yield db
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    finally:
        await db.close()
