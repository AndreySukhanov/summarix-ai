"""
/settings: style, digest language, interface language, time, timezone, custom prompt.
Everything is a button; free input is a command: /time 08:30, /tz Europe/Astrakhan, /prompt ...
"""
import asyncio
import html
import re
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.keyboards import TIME_PRESETS, button_texts, grid, main_menu
from bot.texts import UI_LANGUAGES, t
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


def build_settings_router(*, sessions: SessionMaker, defaults: dict, wake: asyncio.Event) -> Router:
    router = Router()

    def back(lang: str) -> list[InlineKeyboardButton]:
        return [InlineKeyboardButton(text=t(lang, "back"), callback_data="set:main")]

    async def main_view(lang: str) -> tuple[str, InlineKeyboardMarkup]:
        async with sessions() as db:
            s = await get_settings(db, defaults)
        style = style_title(s.style, lang)
        if s.custom_prompt:
            style += f" ({t(lang, 'custom_prompt_on')})"
        text = t(
            lang,
            "settings",
            style=style,
            language=LANGUAGES.get(s.language, LANGUAGES["en"])[0],
            ui_language=LANGUAGES.get(s.ui_language, LANGUAGES["en"])[0],
            time=s.digest_time,
            tz=f"{s.timezone} ({utc_offset(s.timezone)})",
        )
        b = lambda key, data: InlineKeyboardButton(text=t(lang, key), callback_data=data)  # noqa: E731
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [b("btn_style", "set:style"), b("btn_prompt", "set:prompt")],
                [b("btn_language", "set:lang"), b("btn_ui_language", "set:ui")],
                [b("btn_time", "set:time"), b("btn_tz", "set:tz")],
            ]
        )
        return text, kb

    async def show_main(target: Message | CallbackQuery, lang: str) -> None:
        text, kb = await main_view(lang)
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

    async def picker(call: CallbackQuery, lang: str, title_key: str, buttons: list[InlineKeyboardButton], per_row: int):
        await call.message.edit_text(
            t(lang, title_key), reply_markup=InlineKeyboardMarkup(inline_keyboard=grid(buttons, per_row) + [back(lang)])
        )
        await call.answer()

    @router.message(Command("settings"))
    @router.message(F.text.in_(button_texts("menu_settings")))
    async def cmd_settings(message: Message, lang: str) -> None:
        await show_main(message, lang)

    @router.callback_query(F.data == "set:main")
    async def cb_main(call: CallbackQuery, lang: str) -> None:
        await show_main(call, lang)

    # style
    @router.callback_query(F.data == "set:style")
    async def cb_styles(call: CallbackQuery, lang: str) -> None:
        buttons = [InlineKeyboardButton(text=style_title(k, lang), callback_data=f"style:{k}") for k in STYLES]
        await picker(call, lang, "choose_style", buttons, 2)

    @router.callback_query(F.data.startswith("style:"))
    async def cb_style(call: CallbackQuery, lang: str) -> None:
        key = call.data.split(":", 1)[1]
        if key in STYLES:
            await save(style=key, custom_prompt=None)
        await show_main(call, lang)

    # digest language
    @router.callback_query(F.data == "set:lang")
    async def cb_languages(call: CallbackQuery, lang: str) -> None:
        buttons = [InlineKeyboardButton(text=title, callback_data=f"lang:{code}") for code, (title, _) in LANGUAGES.items()]
        await picker(call, lang, "choose_language", buttons, 2)

    @router.callback_query(F.data.startswith("lang:"))
    async def cb_language(call: CallbackQuery, lang: str) -> None:
        code = call.data.split(":", 1)[1]
        if code in LANGUAGES:
            await save(language=code)
        await show_main(call, lang)

    # interface language
    @router.callback_query(F.data == "set:ui")
    async def cb_ui_languages(call: CallbackQuery, lang: str) -> None:
        buttons = [InlineKeyboardButton(text=LANGUAGES[code][0], callback_data=f"ui:{code}") for code in UI_LANGUAGES]
        await picker(call, lang, "choose_ui_language", buttons, 2)

    @router.callback_query(F.data.startswith("ui:"))
    async def cb_ui_language(call: CallbackQuery) -> None:
        code = call.data.split(":", 1)[1]
        if code not in UI_LANGUAGES:
            code = "en"
        await save(ui_language=code)
        await show_main(call, code)
        # the reply keyboard can only be replaced by sending a new message
        await call.message.answer(t(code, "menu_settings"), reply_markup=main_menu(code))

    # time
    @router.callback_query(F.data == "set:time")
    async def cb_times(call: CallbackQuery, lang: str) -> None:
        buttons = [InlineKeyboardButton(text=v, callback_data=f"time:{v}") for v in TIME_PRESETS]
        await picker(call, lang, "choose_time", buttons, 5)

    @router.callback_query(F.data.startswith("time:"))
    async def cb_time(call: CallbackQuery, lang: str) -> None:
        value = parse_time(call.data.split(":", 1)[1])
        if value:
            await save(digest_time=value)
        await show_main(call, lang)

    @router.message(Command("time"))
    async def cmd_time(message: Message, command: CommandObject, lang: str) -> None:
        value = parse_time(command.args or "")
        if not value:
            await message.answer(t(lang, "time_hint"))
            return
        await save(digest_time=value)
        await show_main(message, lang)

    # timezone
    @router.callback_query(F.data == "set:tz")
    async def cb_timezones(call: CallbackQuery, lang: str) -> None:
        buttons = [
            InlineKeyboardButton(text=f"{name.split('/')[-1].replace('_', ' ')} {utc_offset(name)}", callback_data=f"tz:{name}")
            for name in TIMEZONE_PRESETS
        ]
        await picker(call, lang, "choose_tz", buttons, 2)

    @router.callback_query(F.data.startswith("tz:"))
    async def cb_timezone(call: CallbackQuery, lang: str) -> None:
        name = call.data.split(":", 1)[1]
        if valid_timezone(name):
            await save(timezone=name)
        await show_main(call, lang)

    @router.message(Command("tz"))
    async def cmd_tz(message: Message, command: CommandObject, lang: str) -> None:
        name = (command.args or "").strip()
        if not valid_timezone(name):
            await message.answer(t(lang, "tz_invalid", tz=html.escape(name)))
            return
        await save(timezone=name)
        await show_main(message, lang)

    # custom prompt
    @router.callback_query(F.data == "set:prompt")
    async def cb_prompt(call: CallbackQuery, lang: str) -> None:
        async with sessions() as db:
            current = (await get_settings(db, defaults)).custom_prompt
        text = t(lang, "prompt_hint")
        if current:
            text += f"\n\n<i>{html.escape(current)}</i>"
        await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[back(lang)]))
        await call.answer()

    @router.message(Command("prompt"))
    async def cmd_prompt(message: Message, command: CommandObject, lang: str) -> None:
        text = (command.args or "").strip()
        if not text:
            await message.answer(t(lang, "prompt_hint"))
            return
        if text.lower() in ("off", "выкл", "сброс"):
            await save(custom_prompt=None)
        else:
            await save(custom_prompt=text[:MAX_PROMPT_CHARS])
        await show_main(message, lang)

    return router
