"""
/settings: style, digest language, time, timezone, custom prompt.
Buttons for the common choices, commands for free input: /time 08:30, /tz Europe/Astrakhan, /prompt ...
"""
import asyncio
import html
import re
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.texts import t
from database.db import SessionMaker, get_settings, update_settings
from services.styles import LANGUAGES, STYLES, TIMEZONE_PRESETS, style_title

_TIME = re.compile(r"^([01]?\d|2[0-3])[:.]([0-5]\d)$")
MAX_PROMPT_CHARS = 1500


def parse_time(raw: str) -> str | None:
    match = _TIME.match(raw.strip())
    return f"{int(match.group(1)):02d}:{match.group(2)}" if match else None


def valid_timezone(name: str) -> bool:
    try:
        ZoneInfo(name)
        return True
    except (ZoneInfoNotFoundError, ValueError):
        return False


def utc_offset(tz_name: str) -> str:
    offset = datetime.now(ZoneInfo(tz_name)).utcoffset()
    minutes = int(offset.total_seconds() // 60) if offset else 0
    sign = "+" if minutes >= 0 else "-"
    hours, mins = divmod(abs(minutes), 60)
    return f"UTC{sign}{hours}" + (f":{mins:02d}" if mins else "")


def _grid(buttons: list[InlineKeyboardButton], per_row: int) -> list[list[InlineKeyboardButton]]:
    return [buttons[i : i + per_row] for i in range(0, len(buttons), per_row)]


def build_settings_router(*, sessions: SessionMaker, defaults: dict, lang: str, wake: asyncio.Event) -> Router:
    router = Router()
    back = InlineKeyboardButton(text=t(lang, "back"), callback_data="set:main")

    async def summary_text() -> str:
        async with sessions() as db:
            s = await get_settings(db, defaults)
        prompt = t(lang, "custom_prompt_on") if s.custom_prompt else t(lang, "custom_prompt_off")
        return t(
            lang,
            "settings",
            style=style_title(s.style, lang) + (f" ({prompt})" if s.custom_prompt else ""),
            language=LANGUAGES.get(s.language, LANGUAGES["en"])[0],
            time=s.digest_time,
            tz=f"{s.timezone} ({utc_offset(s.timezone)})",
        )

    def main_keyboard() -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text=t(lang, "btn_style"), callback_data="set:style"),
                    InlineKeyboardButton(text=t(lang, "btn_language"), callback_data="set:lang"),
                ],
                [
                    InlineKeyboardButton(text=t(lang, "btn_time"), callback_data="set:time"),
                    InlineKeyboardButton(text=t(lang, "btn_tz"), callback_data="set:tz"),
                ],
                [InlineKeyboardButton(text=t(lang, "btn_prompt"), callback_data="set:prompt")],
            ]
        )

    async def show_main(target: Message | CallbackQuery) -> None:
        text, kb = await summary_text(), main_keyboard()
        if isinstance(target, CallbackQuery):
            await target.message.edit_text(text, reply_markup=kb)
            await target.answer()
        else:
            await target.answer(text, reply_markup=kb)

    async def save(**changes) -> None:
        async with sessions() as db:
            await update_settings(db, defaults, **changes)
        if "digest_time" in changes or "timezone" in changes:
            wake.set()  # scheduler recomputes the next run right away

    @router.message(Command("settings"))
    async def cmd_settings(message: Message) -> None:
        await show_main(message)

    @router.callback_query(F.data == "set:main")
    async def cb_main(call: CallbackQuery) -> None:
        await show_main(call)

    @router.callback_query(F.data == "set:style")
    async def cb_styles(call: CallbackQuery) -> None:
        buttons = [InlineKeyboardButton(text=style_title(k, lang), callback_data=f"style:{k}") for k in STYLES]
        await call.message.edit_text(
            t(lang, "choose_style"), reply_markup=InlineKeyboardMarkup(inline_keyboard=_grid(buttons, 2) + [[back]])
        )
        await call.answer()

    @router.callback_query(F.data.startswith("style:"))
    async def cb_style(call: CallbackQuery) -> None:
        key = call.data.split(":", 1)[1]
        if key in STYLES:
            await save(style=key, custom_prompt=None)
        await show_main(call)

    @router.callback_query(F.data == "set:lang")
    async def cb_languages(call: CallbackQuery) -> None:
        buttons = [InlineKeyboardButton(text=title, callback_data=f"lang:{code}") for code, (title, _) in LANGUAGES.items()]
        await call.message.edit_text(
            t(lang, "choose_language"), reply_markup=InlineKeyboardMarkup(inline_keyboard=_grid(buttons, 2) + [[back]])
        )
        await call.answer()

    @router.callback_query(F.data.startswith("lang:"))
    async def cb_language(call: CallbackQuery) -> None:
        code = call.data.split(":", 1)[1]
        if code in LANGUAGES:
            await save(language=code)
        await show_main(call)

    @router.callback_query(F.data == "set:tz")
    async def cb_timezones(call: CallbackQuery) -> None:
        buttons = [
            InlineKeyboardButton(text=f"{name.split('/')[-1].replace('_', ' ')} {utc_offset(name)}", callback_data=f"tz:{name}")
            for name in TIMEZONE_PRESETS
        ]
        await call.message.edit_text(
            t(lang, "choose_tz"), reply_markup=InlineKeyboardMarkup(inline_keyboard=_grid(buttons, 2) + [[back]])
        )
        await call.answer()

    @router.callback_query(F.data.startswith("tz:"))
    async def cb_timezone(call: CallbackQuery) -> None:
        name = call.data.split(":", 1)[1]
        if valid_timezone(name):
            await save(timezone=name)
        await show_main(call)

    @router.callback_query(F.data == "set:time")
    async def cb_time(call: CallbackQuery) -> None:
        await call.message.edit_text(t(lang, "time_hint"), reply_markup=InlineKeyboardMarkup(inline_keyboard=[[back]]))
        await call.answer()

    @router.callback_query(F.data == "set:prompt")
    async def cb_prompt(call: CallbackQuery) -> None:
        await call.message.edit_text(t(lang, "prompt_hint"), reply_markup=InlineKeyboardMarkup(inline_keyboard=[[back]]))
        await call.answer()

    @router.message(Command("time"))
    async def cmd_time(message: Message, command: CommandObject) -> None:
        value = parse_time(command.args or "")
        if not value:
            await message.answer(t(lang, "time_hint"))
            return
        await save(digest_time=value)
        await show_main(message)

    @router.message(Command("tz"))
    async def cmd_tz(message: Message, command: CommandObject) -> None:
        name = (command.args or "").strip()
        if not valid_timezone(name):
            await message.answer(t(lang, "tz_invalid", tz=html.escape(name)))
            return
        await save(timezone=name)
        await show_main(message)

    @router.message(Command("prompt"))
    async def cmd_prompt(message: Message, command: CommandObject) -> None:
        text = (command.args or "").strip()
        if not text:
            await message.answer(t(lang, "prompt_hint"))
            return
        if text.lower() in ("off", "выкл", "сброс"):
            await save(custom_prompt=None)
        else:
            await save(custom_prompt=text[:MAX_PROMPT_CHARS])
        await show_main(message)

    return router
