"""
Commands and menu buttons. Every handler receives `lang` from the UiLanguage middleware;
only the owner gets this far (OwnerOnly).
"""
import html
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LinkPreviewOptions,
    Message,
    MessageOriginChannel,
)

from bot.keyboards import DIGEST_WINDOWS, button_texts, channels_keyboard, digest_menu, grid, main_menu
from bot.texts import t
from database.db import (
    SessionMaker,
    add_channel,
    get_settings,
    last_run,
    list_channels,
    remove_channel,
    update_settings,
)
from services.styles import STYLES, style_title
from services.digest import DigestService
from services.reader import Reader, ReaderError
from services.refs import ChannelRef, RefError, parse_channel_ref
from services.scheduler import next_run_at

logger = logging.getLogger(__name__)

NO_PREVIEW = LinkPreviewOptions(is_disabled=True)
_REF_IN_TEXT = re.compile(r"(?:https?://)?(?:t\.me|telegram\.me)/\S+|@[A-Za-z][A-Za-z0-9_]{3,31}", re.I)


def extract_refs(text: str | None) -> list[str]:
    return _REF_IN_TEXT.findall(text or "")


async def send_digest(bot: Bot, chat_id: int, service: DigestService, *, window_hours: int | None, trigger: str) -> None:
    """Build, deliver, and only then mark posts read."""
    async with service.lock:
        result = await service.build(window_hours=window_hours)
        for chunk in result.messages:
            await bot.send_message(chat_id, chunk, link_preview_options=NO_PREVIEW)
        await service.commit(result, trigger)
        _save_last_digest(result.messages)


def _save_last_digest(messages: list[str]) -> None:
    """Local copy of the latest digest (data/ is git-ignored) - handy for tuning styles."""
    try:
        path = Path("data/last_digest.txt")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n\n".join(messages), encoding="utf-8")
    except OSError:
        logger.warning("could not save the last digest")


def build_router(*, sessions: SessionMaker, reader: Reader, service: DigestService, defaults: dict, model: str) -> Router:
    router = Router()

    # ---- adding channels ----

    async def add_ref(message: Message, lang: str, ref: ChannelRef, shown: str) -> None:
        try:
            info = await reader.resolve(ref)
        except (ReaderError, ValueError) as exc:
            await message.answer(t(lang, "add_failed", ref=html.escape(shown), reason=html.escape(str(exc))))
            return
        async with sessions() as db:
            channel, created = await add_channel(db, info.peer_id, info.title, info.username)
            await db.commit()
        await message.answer(t(lang, "added" if created else "already", title=html.escape(channel.title)))

    async def add_folder(message: Message, lang: str, slug: str, shown: str) -> None:
        try:
            folder = await reader.resolve_folder(slug)
        except (ReaderError, ValueError) as exc:
            await message.answer(t(lang, "add_failed", ref=html.escape(shown), reason=html.escape(str(exc))))
            return
        added = existing = 0
        async with sessions() as db:
            for info in folder.channels:
                _, created = await add_channel(db, info.peer_id, info.title, info.username)
                added += created
                existing += not created
            await db.commit()
        lines = [t(lang, "folder_added", title=html.escape(folder.title or slug), added=added, existing=existing)]
        if folder.skipped:
            lines.append(t(lang, "folder_skipped", items=html.escape(", ".join(folder.skipped))))
        await message.answer("\n".join(lines))

    async def add_items(message: Message, lang: str, raw: list[str]) -> None:
        for item in raw:
            try:
                ref = parse_channel_ref(item)
            except RefError as exc:
                await message.answer(t(lang, "add_failed", ref=html.escape(item), reason=html.escape(str(exc))))
                continue
            if ref.kind == "folder":
                await add_folder(message, lang, ref.value, item)
            else:
                await add_ref(message, lang, ref, item)

    @router.message(Command("add"))
    async def cmd_add(message: Message, command: CommandObject, lang: str) -> None:
        raw = (command.args or "").split()
        if raw:
            await add_items(message, lang, raw)
        else:
            await message.answer(t(lang, "add_prompt"))

    @router.message(F.text.in_(button_texts("menu_add")))
    async def btn_add(message: Message, lang: str) -> None:
        await message.answer(t(lang, "add_prompt"))

    @router.message(F.forward_origin.as_("origin"))
    async def forwarded(message: Message, origin: Any, lang: str) -> None:
        if isinstance(origin, MessageOriginChannel):
            await add_ref(message, lang, ChannelRef("id", str(origin.chat.id)), origin.chat.title or "")

    # ---- help / start ----

    @router.message(Command("start", "help"))
    @router.message(F.text.in_(button_texts("menu_help")))
    async def cmd_help(message: Message, lang: str) -> None:
        async with sessions() as db:
            prefs = await get_settings(db, defaults)
        await message.answer(t(lang, "help", time=prefs.digest_time, tz=prefs.timezone), reply_markup=main_menu(lang))

    # ---- channels ----

    async def channels_view(lang: str, page: int) -> tuple[str, Any]:
        async with sessions() as db:
            channels = await list_channels(db)
        if not channels:
            return t(lang, "no_channels"), None
        text = t(lang, "channels_header", count=len(channels)) + "\n" + t(lang, "channels_hint")
        return text, channels_keyboard(channels, page)

    @router.message(Command("channels"))
    @router.message(F.text.in_(button_texts("menu_channels")))
    async def cmd_channels(message: Message, lang: str) -> None:
        text, kb = await channels_view(lang, 0)
        await message.answer(text, reply_markup=kb)

    @router.callback_query(F.data.startswith("ch:"))
    async def cb_channels_page(call: CallbackQuery, lang: str) -> None:
        text, kb = await channels_view(lang, int(call.data.split(":")[1]))
        await call.message.edit_text(text, reply_markup=kb)
        await call.answer()

    @router.callback_query(F.data.startswith("rm:"))
    async def cb_remove(call: CallbackQuery, lang: str) -> None:
        _, peer_id, page = call.data.split(":")
        async with sessions() as db:
            channels = {c.peer_id: c for c in await list_channels(db)}
            target = channels.get(int(peer_id))
            if target:
                await remove_channel(db, target.peer_id)
                await db.commit()
        text, kb = await channels_view(lang, int(page))
        await call.message.edit_text(text, reply_markup=kb)
        await call.answer(t(lang, "removed", title=target.title).replace("<b>", "").replace("</b>", "") if target else "")

    @router.message(Command("remove"))
    async def cmd_remove(message: Message, command: CommandObject, lang: str) -> None:
        arg = (command.args or "").strip()
        async with sessions() as db:
            channels = await list_channels(db)
            target = None
            if arg.isdigit() and 1 <= int(arg) <= len(channels):
                target = channels[int(arg) - 1]
            elif arg:
                try:
                    ref = parse_channel_ref(arg)
                    target = next(
                        (c for c in channels if ref.kind == "username" and c.username and c.username.lower() == ref.value),
                        None,
                    )
                except RefError:
                    target = None
            if target is None:
                await message.answer(t(lang, "not_found"))
                return
            await remove_channel(db, target.peer_id)
            await db.commit()
        await message.answer(t(lang, "removed", title=html.escape(target.title)))

    # ---- digest ----

    async def run_digest(bot: Bot, chat_id: int, lang: str, answer, window: int | None) -> None:
        if service.lock.locked():
            await answer(t(lang, "busy"))
            return
        await answer(t(lang, "collecting"))
        try:
            await send_digest(bot, chat_id, service, window_hours=window, trigger="manual")
        except Exception as exc:
            logger.exception("manual digest failed")
            await answer(t(lang, "error", reason=html.escape(str(exc))))

    @router.message(Command("digest"))
    async def cmd_digest(message: Message, command: CommandObject, bot: Bot, lang: str) -> None:
        arg = (command.args or "").strip()
        window = int(arg) if arg.isdigit() and int(arg) > 0 else None
        await run_digest(bot, message.chat.id, lang, message.answer, window)

    @router.message(F.text.in_(button_texts("menu_digest")))
    async def btn_digest(message: Message, lang: str) -> None:
        await message.answer(t(lang, "digest_choose"), reply_markup=await digest_keyboard(lang))

    async def digest_keyboard(lang: str) -> InlineKeyboardMarkup:
        async with sessions() as db:
            prefs = await get_settings(db, defaults)
        style = style_title(prefs.style, lang) + (" ✍️" if prefs.custom_prompt else "")
        return digest_menu(lang, style)

    @router.callback_query(F.data == "dg:style")
    async def cb_digest_styles(call: CallbackQuery, lang: str) -> None:
        buttons = [InlineKeyboardButton(text=style_title(k, lang), callback_data=f"dgs:{k}") for k in STYLES]
        await call.message.edit_text(t(lang, "choose_style"), reply_markup=InlineKeyboardMarkup(inline_keyboard=grid(buttons, 2)))
        await call.answer()

    @router.callback_query(F.data.startswith("dgs:"))
    async def cb_digest_style(call: CallbackQuery, lang: str) -> None:
        key = call.data.split(":", 1)[1]
        if key in STYLES:
            async with sessions() as db:
                await update_settings(db, defaults, style=key, custom_prompt=None)
        await call.message.edit_text(t(lang, "digest_choose"), reply_markup=await digest_keyboard(lang))
        await call.answer()

    @router.callback_query(F.data.startswith("dg:"))
    async def cb_digest(call: CallbackQuery, bot: Bot, lang: str) -> None:
        key = call.data.split(":", 1)[1]
        await call.answer()
        if key not in DIGEST_WINDOWS:
            return
        await call.message.edit_reply_markup(reply_markup=None)
        await run_digest(bot, call.message.chat.id, lang, call.message.answer, DIGEST_WINDOWS[key])

    # ---- status ----

    @router.message(Command("status"))
    @router.message(F.text.in_(button_texts("menu_status")))
    async def cmd_status(message: Message, lang: str) -> None:
        async with sessions() as db:
            channels = await list_channels(db)
            run = await last_run(db)
            prefs = await get_settings(db, defaults)
        next_utc = next_run_at(datetime.now(timezone.utc), prefs.digest_time, prefs.timezone)
        next_local = next_utc.astimezone(ZoneInfo(prefs.timezone))
        last = t(lang, "never")
        if run:
            last = t(
                lang,
                "last_run",
                when=run.started_at.astimezone(ZoneInfo(prefs.timezone)).strftime("%d.%m %H:%M"),
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
                next_run=f"{next_local:%d.%m %H:%M} ({prefs.timezone})",
                last=last,
            )
        )

    # ---- anything else: links become /add ----

    @router.message(F.text & ~F.text.startswith("/"))
    async def plain_links(message: Message, lang: str) -> None:
        """A message with just links or @names is treated as /add - nobody remembers the command."""
        items = extract_refs(message.text)
        if items:
            await add_items(message, lang, items)
        else:
            await message.answer(t(lang, "add_prompt"), reply_markup=main_menu(lang))

    return router
