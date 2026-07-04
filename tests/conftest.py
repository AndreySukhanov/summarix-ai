"""
Test infrastructure: per-test in-memory async SQLite, no external services.
"""
import os

# Env vars must be set BEFORE any project import triggers Settings()
os.environ.setdefault("BOT_TOKEN", "0:TEST")
os.environ.setdefault("OPENAI_API_KEY", "sk-test")
os.environ.setdefault("ADMIN_ID", "1")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from config.constants import SubStatus, Tier
from database.models import Base, Subscription, User


@pytest_asyncio.fixture()
async def db_session():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    TestSession = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    session = TestSession()
    yield session
    await session.close()
    await engine.dispose()


async def create_user(db: AsyncSession, telegram_id: int = 100001, **kwargs) -> User:
    user = User(telegram_id=telegram_id, username="test", first_name="Test", **kwargs)
    db.add(user)
    await db.flush()
    return user


async def create_subscription(
    db: AsyncSession, user: User, tier: Tier = Tier.FREE
) -> Subscription:
    sub = Subscription(user_id=user.id, tier=tier, status=SubStatus.ACTIVE)
    db.add(sub)
    await db.flush()
    return sub
