"""
Channels you follow, the groups they are sorted into, your settings, and a log of digest runs.
Telegram peer IDs exceed int32, hence BigInteger.
"""
from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Channel(Base):
    __tablename__ = "channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    peer_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Highest message id already included in a delivered digest; 0 = never read.
    last_message_id: Mapped[int] = mapped_column(BigInteger, default=0)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Group(Base):
    """A set of channels with its own digest: one per shared folder, plus one for channels added by hand."""

    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(16))  # "manual" | "folder"
    title: Mapped[str] = mapped_column(String(128), default="")  # empty for manual: localized at render time
    folder_slug: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class GroupChannel(Base):
    """Membership. A channel can sit in several groups; it is read once per digest of each."""

    __tablename__ = "group_channels"

    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), primary_key=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id"), primary_key=True)


class BotSettings(Base):
    """One row (id=1): what the owner changed in /settings. Seeded from .env on first start."""

    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    style: Mapped[str] = mapped_column(String(32))
    language: Mapped[str] = mapped_column(String(8))  # digest language
    ui_language: Mapped[str] = mapped_column(String(8), default="ru")  # buttons and bot messages
    digest_time: Mapped[str] = mapped_column(String(5))
    timezone: Mapped[str] = mapped_column(String(64))
    custom_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)


class DigestRun(Base):
    __tablename__ = "digest_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    trigger: Mapped[str] = mapped_column(String(16))  # "schedule" | "manual"
    channels: Mapped[int] = mapped_column(Integer, default=0)
    posts: Mapped[int] = mapped_column(Integer, default=0)
    images: Mapped[int] = mapped_column(Integer, default=0)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[str | None] = mapped_column(Text, nullable=True)
