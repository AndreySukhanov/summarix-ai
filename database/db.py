"""
Async SQLite engine and the handful of queries the bot needs.
"""
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from database.models import Base, BotSettings, Channel, DigestRun, Group, GroupChannel

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
        # create_all never alters existing tables: add columns introduced after the first release
        columns = {row[1] for row in (await conn.exec_driver_sql("PRAGMA table_info(settings)")).fetchall()}
        if "ui_language" not in columns:
            await conn.exec_driver_sql("ALTER TABLE settings ADD COLUMN ui_language VARCHAR(8) NOT NULL DEFAULT 'ru'")
    # channels added before groups existed go to the manual group
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as db:
        ungrouped = (
            await db.execute(select(Channel).where(Channel.id.not_in(select(GroupChannel.channel_id))))
        ).scalars().all()
        if ungrouped:
            group = await manual_group(db)
            for channel in ungrouped:
                db.add(GroupChannel(group_id=group.id, channel_id=channel.id))
            await db.commit()


# ---- channels ----


async def list_channels(db: AsyncSession) -> list[Channel]:
    return list((await db.execute(select(Channel).order_by(Channel.id))).scalars())


async def get_channel(db: AsyncSession, peer_id: int) -> Channel | None:
    return (await db.execute(select(Channel).where(Channel.peer_id == peer_id))).scalars().first()


async def add_channel(db: AsyncSession, peer_id: int, title: str, username: str | None) -> tuple[Channel, bool]:
    """Returns (channel, created). A known channel gets its current title and username: a renamed
    channel would otherwise keep old links, or links to whoever took its old username."""
    existing = await get_channel(db, peer_id)
    if existing:
        existing.title, existing.username = title, username
        return existing, False
    channel = Channel(peer_id=peer_id, title=title, username=username)
    db.add(channel)
    await db.flush()
    return channel, True


async def remove_channel(db: AsyncSession, peer_id: int) -> bool:
    """Remove a channel from the bot entirely, from every group."""
    channel = await get_channel(db, peer_id)
    if not channel:
        return False
    await db.execute(delete(GroupChannel).where(GroupChannel.channel_id == channel.id))
    await db.delete(channel)
    return True


# ---- groups ----


async def manual_group(db: AsyncSession) -> Group:
    group = (await db.execute(select(Group).where(Group.kind == "manual"))).scalars().first()
    if group is None:
        group = Group(kind="manual", title="")
        db.add(group)
        await db.flush()
    return group


async def folder_group(db: AsyncSession, slug: str, title: str) -> Group:
    group = (await db.execute(select(Group).where(Group.folder_slug == slug))).scalars().first()
    if group is None:
        group = Group(kind="folder", folder_slug=slug, title=title or slug)
        db.add(group)
        await db.flush()
    elif title and group.title != title:
        group.title = title
    return group


async def get_group(db: AsyncSession, group_id: int) -> Group | None:
    return await db.get(Group, group_id)


async def list_groups(db: AsyncSession) -> list[tuple[Group, int]]:
    """Groups with their channel counts, the manual group first."""
    counts = (
        select(GroupChannel.group_id, func.count().label("n")).group_by(GroupChannel.group_id).subquery()
    )
    rows = await db.execute(
        select(Group, func.coalesce(counts.c.n, 0))
        .outerjoin(counts, counts.c.group_id == Group.id)
        .order_by((Group.kind != "manual"), Group.id)
    )
    return [(group, int(n)) for group, n in rows.all()]


async def group_channels(db: AsyncSession, group_id: int) -> list[Channel]:
    rows = await db.execute(
        select(Channel)
        .join(GroupChannel, GroupChannel.channel_id == Channel.id)
        .where(GroupChannel.group_id == group_id)
        .order_by(Channel.id)
    )
    return list(rows.scalars())


async def add_to_group(
    db: AsyncSession, group: Group, peer_id: int, title: str, username: str | None
) -> tuple[Channel, bool]:
    """Returns (channel, newly in this group)."""
    channel, _ = await add_channel(db, peer_id, title, username)
    if await db.get(GroupChannel, (group.id, channel.id)):
        return channel, False
    db.add(GroupChannel(group_id=group.id, channel_id=channel.id))
    await db.flush()
    return channel, True


async def _drop_orphans(db: AsyncSession, channel_ids: list[int]) -> None:
    for channel_id in channel_ids:
        still = (await db.execute(select(GroupChannel).where(GroupChannel.channel_id == channel_id))).first()
        if still is None:
            channel = await db.get(Channel, channel_id)
            if channel:
                await db.delete(channel)


async def remove_from_group(db: AsyncSession, group_id: int, channel_id: int) -> Channel | None:
    """Take a channel out of one group; a channel left in no group is removed from the bot."""
    link = await db.get(GroupChannel, (group_id, channel_id))
    if link is None:
        return None
    channel = await db.get(Channel, channel_id)
    await db.delete(link)
    await db.flush()
    await _drop_orphans(db, [channel_id])
    return channel


async def delete_group(db: AsyncSession, group_id: int) -> Group | None:
    group = await db.get(Group, group_id)
    if group is None:
        return None
    channel_ids = [c.id for c in await group_channels(db, group_id)]
    await db.execute(delete(GroupChannel).where(GroupChannel.group_id == group_id))
    await db.flush()
    await _drop_orphans(db, channel_ids)
    await db.delete(group)
    return group


# ---- settings and runs ----


async def get_settings(db: AsyncSession, defaults: dict) -> BotSettings:
    """The single settings row, created from `defaults` (style, language, digest_time, timezone) if missing."""
    row = await db.get(BotSettings, 1)
    if row is None:
        row = BotSettings(id=1, **defaults)
        db.add(row)
        await db.commit()
    return row


async def update_settings(db: AsyncSession, defaults: dict, **changes) -> BotSettings:
    row = await get_settings(db, defaults)
    for key, value in changes.items():
        setattr(row, key, value)
    await db.commit()
    return row


async def last_run(db: AsyncSession) -> DigestRun | None:
    return (await db.execute(select(DigestRun).order_by(DigestRun.id.desc()).limit(1))).scalars().first()

