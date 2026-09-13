"""
Commands and menu buttons. Every handler receives `lang` from the UiLanguage middleware;
only the owner gets this far (OwnerOnly).
"""
import html
import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    LinkPreviewOptions,
    Message,
    MessageOriginChannel,
)

from bot.keyboards import (
    DIGEST_WINDOWS,
    button_texts,
    delete_confirm_keyboard,
    digest_menu,
    digest_period_menu,
    group_keyboard,
    group_title,
    groups_keyboard,
    main_menu,
    styles_keyboard,
)
from bot.texts import t
from database.db import (
    SessionMaker,
    add_to_group,
    delete_group,
    folder_group,
    get_group,
    get_settings,
    group_channels,
    last_run,
    list_channels,
    list_groups,
    manual_group,
    remove_channel,
    remove_from_group,
    update_settings,
)
from services.digest import DigestResult, DigestService
from services.reader import Reader, ReaderError
from services.refs import ChannelRef, RefError, parse_channel_ref
from services.scheduler import next_run_at
from services.styles import STYLES, style_title

logger = logging.getLogger(__name__)

NO_PREVIEW = LinkPreviewOptions(is_disabled=True)
_REF_IN_TEXT = re.compile(r"(?:https?://)?(?:t\.me|telegram\.me)/\S+|@[A-Za-z][A-Za-z0-9_]{3,31}", re.I)
PENDING_TTL_S = 15 * 60
LAST_DIGEST_PATH = Path("data/last_digest.txt")


def extract_refs(text: str | None) -> list[str]:
    return _REF_IN_TEXT.findall(text or "")


async def send_digest(
    bot: Bot,
    chat_id: int,
    service: DigestService,
    *,
    window_hours: int | None,
    trigger: str,
    group_id: int | None = None,
) -> None:
    """One digest per group (group_id=None: every group that has channels).
    Each is delivered and only then its posts are marked read. Groups with nothing new stay silent,
    unless every group is silent - then one "no new posts" message."""
    async with service.lock:
        async with service.sessions() as db:
            groups = [g for g, n in await list_groups(db) if n and (group_id is None or g.id == group_id)]
        sent: list[str] = []
        quiet: DigestResult | None = None
        for group in groups:
            result = await service.build(window_hours=window_hours, group_id=group.id)
            if result.channels_with_news == 0 and not result.errors and (group_id is None or len(groups) > 1):
                quiet = quiet or result
                continue
            for chunk in result.messages:
                await bot.send_message(chat_id, chunk, link_preview_options=NO_PREVIEW)
            sent.extend(result.messages)
            await service.commit(result, trigger)
        if not sent:
            fallback = quiet.messages if quiet else (await service.build(window_hours=window_hours)).messages
            for chunk in fallback:
                await bot.send_message(chat_id, chunk, link_preview_options=NO_PREVIEW)
            sent = fallback
        _save_last_digest(sent)


def _save_last_digest(messages: list[str]) -> None:
    """Local copy of the latest digest (data/ is git-ignored) - handy for tuning styles."""
    try:
        LAST_DIGEST_PATH.parent.mkdir(parents=True, exist_ok=True)
        LAST_DIGEST_PATH.write_text("\n\n".join(messages), encoding="utf-8")
    except OSError:
        logger.warning("could not save the last digest")


def build_router(*, sessions: SessionMaker, reader: Reader, service: DigestService, defaults: dict, model: str) -> Router:
    router = Router()
    # "➕ Add here" in a group: the next links go to that group for a while
    pending: dict[str, float | int] = {}

    def pending_group_id() -> int | None:
        if pending and time.monotonic() < pending["until"]:
            return int(pending["group_id"])
        pending.clear()
        return None

    # ---- adding channels ----

    async def add_ref(message: Message, lang: str, ref: ChannelRef, shown: str) -> None:
        try:
            info = await reader.resolve(ref)
        except (ReaderError, ValueError) as exc:
            await message.answer(t(lang, "add_failed", ref=html.escape(shown), reason=html.escape(str(exc))))
            return
        async with sessions() as db:
            target = pending_group_id()
            group = (await get_group(db, target) if target else None) or await manual_group(db)
            channel, created = await add_to_group(db, group, info.peer_id, info.title, info.username)
            await db.commit()
        key = "added_to" if created else "already_in"
        await message.answer(
            t(lang, key, group=html.escape(group_title(group, lang)), title=html.escape(channel.title))
        )

    async def add_folder(message: Message, lang: str, slug: str, shown: str) -> None:
        try:
            folder = await reader.resolve_folder(slug)
        except (ReaderError, ValueError) as exc:
            await message.answer(t(lang, "add_failed", ref=html.escape(shown), reason=html.escape(str(exc))))
            return
        added = existing = 0
        async with sessions() as db:
            group = await folder_group(db, slug, folder.title)
            mine = await manual_group(db)
            for info in folder.channels:
                channel, created = await add_to_group(db, group, info.peer_id, info.title, info.username)
                added += created
                existing += not created
                # a channel that sat in "My channels" (e.g. from before groups existed) moves to its folder
                await remove_from_group(db, mine.id, channel.id)
            await db.commit()
        lines = [t(lang, "folder_added", title=html.escape(group.title), added=added, existing=existing)]
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
        pending.clear()  # the plain "Add" button means "my channels"
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

    # ---- groups and channels ----

    async def groups_view(lang: str) -> tuple[str, Any]:
        async with sessions() as db:
            groups = [(g, n) for g, n in await list_groups(db) if n or g.kind == "manual"]
        if not any(n for _, n in groups):
            return t(lang, "no_channels"), None
        return t(lang, "groups_header", count=len(groups)), groups_keyboard(groups, lang)

    async def group_view(lang: str, group_id: int, page: int) -> tuple[str, Any]:
        async with sessions() as db:
            group = await get_group(db, group_id)
            if group is None:
                return await groups_view(lang)
            channels = await group_channels(db, group_id)
        title = html.escape(group_title(group, lang))
        text = (
            t(lang, "group_header", title=title, count=len(channels))
            if channels
            else t(lang, "group_empty", title=title)
        )
        return text, group_keyboard(group, channels, page, lang)

    @router.message(Command("channels"))
    @router.message(F.text.in_(button_texts("menu_channels")))
    async def cmd_channels(message: Message, lang: str) -> None:
        text, kb = await groups_view(lang)
        await message.answer(text, reply_markup=kb)

    @router.callback_query(F.data == "grps")
    async def cb_groups(call: CallbackQuery, lang: str) -> None:
        text, kb = await groups_view(lang)
        await call.message.edit_text(text, reply_markup=kb)
        await call.answer()

    @router.callback_query(F.data.startswith("grp:"))
    async def cb_group(call: CallbackQuery, lang: str) -> None:
        _, group_id, page = call.data.split(":")
        text, kb = await group_view(lang, int(group_id), int(page))
        await call.message.edit_text(text, reply_markup=kb)
        await call.answer()

    @router.callback_query(F.data.startswith("rmg:"))
    async def cb_remove_from_group(call: CallbackQuery, lang: str) -> None:
        _, group_id, channel_id, page = call.data.split(":")
        async with sessions() as db:
            channel = await remove_from_group(db, int(group_id), int(channel_id))
            await db.commit()
        text, kb = await group_view(lang, int(group_id), int(page))
        await call.message.edit_text(text, reply_markup=kb)
        await call.answer(t(lang, "removed", title=channel.title).replace("<b>", "").replace("</b>", "") if channel else "")

    @router.callback_query(F.data.startswith("gadd:"))
    async def cb_group_add(call: CallbackQuery, lang: str) -> None:
        group_id = int(call.data.split(":")[1])
        async with sessions() as db:
            group = await get_group(db, group_id)
        if group is None:
            await call.answer()
            return
        pending.update(group_id=group_id, until=time.monotonic() + PENDING_TTL_S)
        await call.message.answer(t(lang, "group_add_prompt", title=html.escape(group_title(group, lang))))
        await call.answer()

    @router.callback_query(F.data.startswith("gdel:"))
    async def cb_group_delete(call: CallbackQuery, lang: str) -> None:
        async with sessions() as db:
            group = await get_group(db, int(call.data.split(":")[1]))
        if group is None:
            await call.answer()
            return
        await call.message.edit_text(
            t(lang, "group_delete_confirm", title=html.escape(group_title(group, lang))),
            reply_markup=delete_confirm_keyboard(group, lang),
        )
        await call.answer()

    @router.callback_query(F.data.startswith("gdelok:"))
    async def cb_group_delete_ok(call: CallbackQuery, lang: str) -> None:
        async with sessions() as db:
            group = await delete_group(db, int(call.data.split(":")[1]))
            await db.commit()
        if group is not None:
            pending.clear()
            await call.message.answer(t(lang, "group_deleted", title=html.escape(group_title(group, lang))))
        text, kb = await groups_view(lang)
        await call.message.edit_text(text, reply_markup=kb)
        await call.answer()

    @router.message(Command("remove"))
    async def cmd_remove(message: Message, command: CommandObject, lang: str) -> None:
        arg = (command.args or "").strip()
        async with sessions() as db:
            channels = await list_channels(db)
            target = None
            if arg:
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

    async def run_digest(bot: Bot, chat_id: int, lang: str, answer, window: int | None, group_id: int | None) -> None:
        if service.lock.locked():
            await answer(t(lang, "busy"))
            return
        await answer(t(lang, "collecting"))
        try:
            await send_digest(bot, chat_id, service, window_hours=window, trigger="manual", group_id=group_id)
        except Exception as exc:
            logger.exception("manual digest failed")
            await answer(t(lang, "error", reason=html.escape(str(exc))))

    async def digest_keyboard(lang: str) -> InlineKeyboardMarkup:
        async with sessions() as db:
            prefs = await get_settings(db, defaults)
            groups = await list_groups(db)
        style = style_title(prefs.style, lang) + (" ✍️" if prefs.custom_prompt else "")
        return digest_menu(lang, style, groups)

    @router.message(Command("digest"))
    async def cmd_digest(message: Message, command: CommandObject, bot: Bot, lang: str) -> None:
        arg = (command.args or "").strip()
        window = int(arg) if arg.isdigit() and int(arg) > 0 else None
        await run_digest(bot, message.chat.id, lang, message.answer, window, None)

    @router.message(F.text.in_(button_texts("menu_digest")))
    async def btn_digest(message: Message, lang: str) -> None:
        await message.answer(t(lang, "digest_choose_group"), reply_markup=await digest_keyboard(lang))

    @router.callback_query(F.data == "dgm")
    async def cb_digest_main(call: CallbackQuery, lang: str) -> None:
        await call.message.edit_text(t(lang, "digest_choose_group"), reply_markup=await digest_keyboard(lang))
        await call.answer()

    async def current_style(lang: str) -> tuple[str, str]:
        async with sessions() as db:
            prefs = await get_settings(db, defaults)
        return prefs.style, style_title(prefs.style, lang) + (" ✍️" if prefs.custom_prompt else "")

    @router.message(F.text.in_(button_texts("menu_style")))
    async def btn_style(message: Message, lang: str) -> None:
        key, title = await current_style(lang)
        await message.answer(
            t(lang, "style_current", style=html.escape(title)), reply_markup=styles_keyboard(lang, key, "sty:")
        )

    @router.callback_query(F.data.startswith("sty:"))
    async def cb_style_pick(call: CallbackQuery, lang: str) -> None:
        key = call.data.split(":", 1)[1]
        if key in STYLES:
            async with sessions() as db:
                await update_settings(db, defaults, style=key, custom_prompt=None)
        _, title = await current_style(lang)
        await call.message.edit_text(t(lang, "style_set", style=html.escape(title)))
        await call.answer()

    @router.callback_query(F.data == "dg:style")
    async def cb_digest_styles(call: CallbackQuery, lang: str) -> None:
        key, _ = await current_style(lang)
        await call.message.edit_text(t(lang, "choose_style"), reply_markup=styles_keyboard(lang, key, "dgs:"))
        await call.answer()

    @router.callback_query(F.data.startswith("dgs:"))
    async def cb_digest_style(call: CallbackQuery, lang: str) -> None:
        key = call.data.split(":", 1)[1]
        if key in STYLES:
            async with sessions() as db:
                await update_settings(db, defaults, style=key, custom_prompt=None)
        await call.message.edit_text(t(lang, "digest_choose_group"), reply_markup=await digest_keyboard(lang))
        await call.answer()

    @router.callback_query(F.data.startswith("dgg:"))
    async def cb_digest_group(call: CallbackQuery, lang: str) -> None:
        group_id = int(call.data.split(":")[1])
        title = t(lang, "btn_all_groups")
        if group_id:
            async with sessions() as db:
                group = await get_group(db, group_id)
            if group is None:
                await call.answer()
                return
            title = group_title(group, lang)
        _, style = await current_style(lang)
        await call.message.edit_text(
            t(lang, "digest_choose_period", title=html.escape(title)),
            reply_markup=digest_period_menu(lang, group_id, style),
        )
        await call.answer()

    @router.callback_query(F.data.startswith("dgp:"))
    async def cb_digest_period(call: CallbackQuery, bot: Bot, lang: str) -> None:
        _, group_id, key = call.data.split(":")
        await call.answer()
        if key not in DIGEST_WINDOWS:
            return
        await call.message.edit_reply_markup(reply_markup=None)
        await run_digest(
            bot, call.message.chat.id, lang, call.message.answer, DIGEST_WINDOWS[key], int(group_id) or None
        )

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
