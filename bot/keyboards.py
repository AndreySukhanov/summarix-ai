"""
Keyboards: the persistent main menu and the inline pickers.
"""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from bot.texts import TEXTS, t
from database.models import Channel

CHANNELS_PER_PAGE = 8
TIME_PRESETS = ["06:00", "07:00", "08:00", "09:00", "10:00", "12:00", "14:00", "18:00", "20:00", "22:00"]
DIGEST_WINDOWS = {"new": None, "24": 24, "48": 48, "168": 168}


def button_texts(key: str) -> set[str]:
    """A menu button's label in every UI language, so a switch of language never breaks the buttons."""
    return {table[key] for table in TEXTS.values()}


def main_menu(lang: str) -> ReplyKeyboardMarkup:
    b = lambda key: KeyboardButton(text=t(lang, key))  # noqa: E731
    return ReplyKeyboardMarkup(
        keyboard=[
            [b("menu_digest"), b("menu_channels")],
            [b("menu_add"), b("menu_settings")],
            [b("menu_status"), b("menu_help")],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def digest_menu(lang: str) -> InlineKeyboardMarkup:
    b = lambda key, data: InlineKeyboardButton(text=t(lang, key), callback_data=f"dg:{data}")  # noqa: E731
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [b("btn_unread", "new")],
            [b("btn_24h", "24"), b("btn_48h", "48"), b("btn_7d", "168")],
        ]
    )


def channels_keyboard(channels: list[Channel], page: int) -> InlineKeyboardMarkup:
    pages = max(1, -(-len(channels) // CHANNELS_PER_PAGE))
    page = min(max(page, 0), pages - 1)
    start = page * CHANNELS_PER_PAGE
    rows = []
    for i, channel in enumerate(channels[start : start + CHANNELS_PER_PAGE], start=start + 1):
        title = channel.title if len(channel.title) <= 32 else channel.title[:31] + "…"
        rows.append([InlineKeyboardButton(text=f"❌ {i}. {title}", callback_data=f"rm:{channel.peer_id}:{page}")])
    if pages > 1:
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton(text="◀", callback_data=f"ch:{page - 1}"))
        nav.append(InlineKeyboardButton(text=f"{page + 1}/{pages}", callback_data=f"ch:{page}"))
        if page < pages - 1:
            nav.append(InlineKeyboardButton(text="▶", callback_data=f"ch:{page + 1}"))
        rows.append(nav)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def grid(buttons: list[InlineKeyboardButton], per_row: int) -> list[list[InlineKeyboardButton]]:
    return [buttons[i : i + per_row] for i in range(0, len(buttons), per_row)]
