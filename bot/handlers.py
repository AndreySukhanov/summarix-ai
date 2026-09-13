"""
Commands. Everything here runs only for the owner - see OwnerOnly.
"""
import html
import logging
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware, Bot, F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import LinkPreviewOptions, Message, MessageOriginChannel, TelegramObject

from bot.texts import t
from database.db import SessionMaker, add_channel, last_run, list_channels, remove_channel
from services.digest import DigestService
from services.reader import Reader, ReaderError
from services.refs import ChannelRef, RefError, parse_channel_ref
from services.scheduler import next_run_at

logger = logging.getLogger(__name__)

NO_PREVIEW = LinkPreviewOptions(is_disabled=True)


class OwnerOnly(BaseMiddleware):
    """Silently drops every update that does not come from the owner."""

    def __init__(self, owner_id: int):
        self.owner_id = owner_id

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = getattr(event, "from_user", None)
        if user is None or user.id != self.owner_id:
            return None
        return await handler(event, data)


async def send_digest(bot: Bot, chat_id: int, service: DigestService, *, window_hours: int | None, trigger: str) -> None:
    """Build, deliver, and only then mark posts read."""
    async with service.lock:
        result = await service.build(window_hours=window_hours)
        for chunk in result.messages:
            await bot.send_message(chat_id, chunk, link_preview_options=NO_PREVIEW)
        await service.commit(result, trigger)


def build_router(
    *,
    sessions: SessionMaker,
    reader: Reader,
    service: DigestService,
    lang: str,
    digest_time: str,
    timezone_name: str,
    model: str,
) -> Router:
    router = Router()

    async def add_ref(message: Message, ref: ChannelRef, shown: str) -> None:
        try:
            info = await reader.resolve(ref)
        except (ReaderError, ValueError) as exc:
            await message.answer(t(lang, "add_failed", ref=html.escape(shown), reason=html.escape(str(exc))))
            return
        async with sessions() as db:
            channel, created = await add_channel(db, info.peer_id, info.title, info.username)
            await db.commit()
        key = "added" if created else "already"
        await message.answer(t(lang, key, title=html.escape(channel.title)))

    @router.message(Command("start", "help"))
    async def cmd_help(message: Message) -> None:
        await message.answer(t(lang, "help", time=digest_time, tz=timezone_name))

    @router.message(Command("add"))
    async def cmd_add(message: Message, command: CommandObject) -> None:
        raw = (command.args or "").split()
        if not raw:
            await message.answer(t(lang, "add_usage"))
            return
        for item in raw:
            try:
                ref = parse_channel_ref(item)
            except RefError as exc:
                await message.answer(t(lang, "add_failed", ref=html.escape(item), reason=html.escape(str(exc))))
                continue
            await add_ref(message, ref, item)

    @router.message(F.forward_origin.as_("origin"))
    async def forwarded(message: Message, origin: Any) -> None:
        if isinstance(origin, MessageOriginChannel):
            await add_ref(message, ChannelRef("id", str(origin.chat.id)), origin.chat.title or "")

    @router.message(Command("channels"))
    async def cmd_channels(message: Message) -> None:
        async with sessions() as db:
            channels = await list_channels(db)
        if not channels:
            await message.answer(t(lang, "no_channels"))
            return
        lines = [t(lang, "channels_header", count=len(channels))]
        for i, c in enumerate(channels, start=1):
            name = html.escape(c.title)
            lines.append(f'{i}. <a href="https://t.me/{c.username}">{name}</a>' if c.username else f"{i}. {name}")
        await message.answer("\n".join(lines), link_preview_options=NO_PREVIEW)

    @router.message(Command("remove"))
    async def cmd_remove(message: Message, command: CommandObject) -> None:
        arg = (command.args or "").strip()
        async with sessions() as db:
            channels = await list_channels(db)
            target = None
            if arg.isdigit() and 1 <= int(arg) <= len(channels):
                target = channels[int(arg) - 1]
            elif arg:
                try:
                    ref = parse_channel_ref(arg)
                    target = next((c for c in channels if ref.kind == "username" and c.username
                                   and c.username.lower() == ref.value), None)
                except RefError:
                    target = None
            if target is None:
                await message.answer(t(lang, "not_found"))
                return
            await remove_channel(db, target.peer_id)
            await db.commit()
        await message.answer(t(lang, "removed", title=html.escape(target.title)))

    @router.message(Command("digest"))
    async def cmd_digest(message: Message, command: CommandObject, bot: Bot) -> None:
        arg = (command.args or "").strip()
        window = int(arg) if arg.isdigit() and int(arg) > 0 else None
        if service.lock.locked():
            await message.answer(t(lang, "busy"))
            return
        await message.answer(t(lang, "collecting"))
        try:
            await send_digest(bot, message.chat.id, service, window_hours=window, trigger="manual")
        except Exception as exc:
            logger.exception("manual digest failed")
            await message.answer(t(lang, "error", reason=html.escape(str(exc))))

    @router.message(Command("status"))
    async def cmd_status(message: Message) -> None:
        async with sessions() as db:
            channels = await list_channels(db)
            run = await last_run(db)
        next_local = next_run_at(datetime.now(timezone.utc), digest_time, timezone_name)
        last = t(lang, "never")
        if run:
            last = t(
                lang,
                "last_run",
                when=run.started_at.strftime("%d.%m %H:%M UTC"),
                posts=run.posts,
                images=run.images,
                tokens=run.input_tokens + run.output_tokens,
            )
        await message.answer(
            t(
                lang,
                "status",
                model=html.escape(model),
                channels=len(channels),
                next_run=next_local.strftime("%d.%m %H:%M UTC"),
                last=last,
            )
        )

    return router
