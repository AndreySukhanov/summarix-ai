"""
Async SQLite engine and the handful of queries the bot needs.
"""
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from database.models import Base, Channel, DigestRun

SessionMaker = async_sessionmaker[AsyncSession]


def make_sessionmaker(url: str) -> tuple[AsyncEngine, SessionMaker]:
    if ":memory:" in url:  # tests: one shared connection, or every session sees an empty DB
        engine = create_async_engine(url, poolclass=StaticPool)
        return engine, async_sessionmaker(engine, expire_on_commit=False)
    if url.startswith("sqlite"):
        Path(url.split(":///", 1)[-1]).parent.mkdir(parents=True, exist_ok=True)
    engine = create_async_engine(url)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def init_models(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def list_channels(db: AsyncSession) -> list[Channel]:
    return list((await db.execute(select(Channel).order_by(Channel.id))).scalars())


async def get_channel(db: AsyncSession, peer_id: int) -> Channel | None:
    return (await db.execute(select(Channel).where(Channel.peer_id == peer_id))).scalars().first()


async def add_channel(db: AsyncSession, peer_id: int, title: str, username: str | None) -> tuple[Channel, bool]:
    """Returns (channel, created)."""
    existing = await get_channel(db, peer_id)
    if existing:
        return existing, False
    channel = Channel(peer_id=peer_id, title=title, username=username)
    db.add(channel)
    await db.flush()
    return channel, True


async def remove_channel(db: AsyncSession, peer_id: int) -> bool:
    channel = await get_channel(db, peer_id)
    if not channel:
        return False
    await db.delete(channel)
    return True


async def last_run(db: AsyncSession) -> DigestRun | None:
    return (await db.execute(select(DigestRun).order_by(DigestRun.id.desc()).limit(1))).scalars().first()
