"""
Reading channels through the owner's own Telegram account (Telethon).

A bot can only read channels where it is an admin; a user account reads everything the
owner is subscribed to, private channels included. The session file created by
`python -m scripts.login` is full access to that account - keep it private.
"""
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable, Protocol

from services.refs import ChannelRef

logger = logging.getLogger(__name__)

MAX_POST_CHARS = 4000
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_IMAGES_PER_POST = 2


@dataclass
class ChannelInfo:
    peer_id: int
    title: str
    username: str | None


@dataclass
class Post:
    message_id: int
    date: datetime
    text: str
    link: str
    images: list[bytes] = field(default_factory=list)
    image_descriptions: list[str] = field(default_factory=list)


@dataclass
class Folder:
    title: str
    channels: list[ChannelInfo]
    skipped: list[str]  # private channels the account has not joined


class ReaderError(RuntimeError):
    pass


class Reader(Protocol):
    async def resolve(self, ref: ChannelRef) -> ChannelInfo: ...

    async def resolve_folder(self, slug: str) -> Folder: ...

    async def fetch_posts(
        self, channel: ChannelInfo, *, after_id: int, since: datetime, limit: int, with_images: bool
    ) -> list[Post]: ...


def post_link(channel: ChannelInfo, message_id: int) -> str:
    if channel.username:
        return f"https://t.me/{channel.username}/{message_id}"
    internal = str(abs(channel.peer_id))
    internal = internal[3:] if internal.startswith("100") else internal
    return f"https://t.me/c/{internal}/{message_id}"


def group_messages(messages: Iterable[Any]) -> list[list[Any]]:
    """Chronological groups; an album (same grouped_id) is one post. Service messages dropped."""
    ordered = sorted((m for m in messages if getattr(m, "action", None) is None), key=lambda m: m.id)
    groups: list[list[Any]] = []
    by_album: dict[int, list[Any]] = {}
    for message in ordered:
        album = getattr(message, "grouped_id", None)
        if album is None:
            groups.append([message])
        elif album in by_album:
            by_album[album].append(message)
        else:
            by_album[album] = [message]
            groups.append(by_album[album])
    return groups


class TelethonReader:
    def __init__(self, client: Any):
        self.client = client
        self._dialogs_loaded = False
        self._entities: dict[int, Any] = {}

    async def resolve(self, ref: ChannelRef) -> ChannelInfo:
        from telethon import utils
        from telethon.tl.functions.messages import CheckChatInviteRequest
        from telethon.tl.types import ChatInviteAlready

        if ref.kind == "invite":
            invite = await self.client(CheckChatInviteRequest(ref.value))
            if not isinstance(invite, ChatInviteAlready):  # a peek does not let us read history
                raise ReaderError("join this channel from your account first, then add it again")
            entity = invite.chat
        elif ref.kind == "id":
            entity = await self._entity_by_id(int(ref.value))
        else:
            try:
                entity = await self.client.get_entity(ref.value)
            except (ValueError, TypeError) as exc:
                raise ReaderError(f"channel @{ref.value} not found") from exc

        if not getattr(entity, "broadcast", False) and not getattr(entity, "megagroup", False):
            raise ReaderError("this is not a channel or a group")
        return ChannelInfo(utils.get_peer_id(entity), entity.title, getattr(entity, "username", None))

    async def resolve_folder(self, slug: str) -> Folder:
        """A shared folder (t.me/addlist/...). Public channels are readable without joining;
        private ones only if the account is already a member."""
        from telethon import utils
        from telethon.tl.functions.chatlists import CheckChatlistInviteRequest

        try:
            invite = await self.client(CheckChatlistInviteRequest(slug))
        except Exception as exc:
            raise ReaderError(f"folder link is invalid or expired ({type(exc).__name__})") from exc

        channels, skipped = [], []
        for chat in invite.chats:
            if not getattr(chat, "broadcast", False) and not getattr(chat, "megagroup", False):
                continue  # basic groups, forbidden channels
            username = getattr(chat, "username", None)
            if getattr(chat, "left", True) and not username:
                skipped.append(chat.title)
                continue
            channels.append(ChannelInfo(utils.get_peer_id(chat), chat.title, username))
        return Folder(getattr(invite, "title", None) or "", channels, skipped)

    async def fetch_posts(
        self, channel: ChannelInfo, *, after_id: int, since: datetime, limit: int, with_images: bool
    ) -> list[Post]:
        from telethon import errors

        entity = await self._entity_for(channel)
        raw = []
        try:
            async for message in self.client.iter_messages(entity, limit=limit, min_id=after_id):
                if message.date < since:
                    break
                raw.append(message)
        except errors.FloodWaitError as exc:
            if exc.seconds > 60:
                raise ReaderError(f"Telegram asks to wait {exc.seconds}s") from exc
            await asyncio.sleep(exc.seconds)
            return await self.fetch_posts(
                channel, after_id=after_id, since=since, limit=limit, with_images=with_images
            )

        posts = []
        for group in group_messages(raw):
            text = "\n".join(m.message for m in group if m.message).strip()
            images: list[bytes] = []
            if with_images:
                for m in group:
                    if m.photo and len(images) < MAX_IMAGES_PER_POST:
                        data = await self.client.download_media(m, file=bytes)
                        if data and len(data) <= MAX_IMAGE_BYTES:
                            images.append(data)
            has_photo = any(m.photo for m in group)
            if not text and not has_photo:
                continue  # stickers, polls, files without captions
            first = group[0]
            posts.append(
                Post(first.id, first.date, text[:MAX_POST_CHARS], post_link(channel, first.id), images)
            )
        return posts

    async def _entity_for(self, channel: ChannelInfo) -> Any:
        """Cheapest lookup first. Resolving @usernames is rate-limited by Telegram (flood waits
        after a few dozen in a row), so it is the last resort, and each result is kept for the process."""
        if channel.peer_id in self._entities:
            return self._entities[channel.peer_id]
        entity = None
        try:
            entity = await self.client.get_entity(channel.peer_id)  # Telethon's session cache, no request
        except ValueError:
            if channel.username:
                entity = await self.client.get_entity(channel.username)  # not subscribed: resolve once
            else:
                entity = await self._entity_by_id(channel.peer_id)
        self._entities[channel.peer_id] = entity
        return entity

    async def _entity_by_id(self, peer_id: int) -> Any:
        try:
            return await self.client.get_entity(peer_id)
        except ValueError:
            if self._dialogs_loaded:
                raise ReaderError("your account does not see this channel - are you subscribed?")
            await self.client.get_dialogs()  # fills Telethon's entity cache
            self._dialogs_loaded = True
            return await self._entity_by_id(peer_id)
