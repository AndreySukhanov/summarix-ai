"""
Keyboards: the persistent main menu and the inline pickers.
"""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from bot.texts import TEXTS, t
from database.models import Channel, Group

CHANNELS_PER_PAGE = 8
TIME_PRESETS = ["06:00", "07:00", "08:00", "09:00", "10:00", "12:00", "14:00", "18:00", "20:00", "22:00"]
DIGEST_WINDOWS = {"new": None, "24": 24, "48": 48, "168": 168}


def button_texts(key: str) -> set[str]:
    """A menu button's label in every UI language, so a switch of language never breaks the buttons."""
    return {table[key] for table in TEXTS.values()}


def group_title(group: Group, lang: str) -> str:
    return t(lang, "group_manual") if group.kind == "manual" else f"📁 {group.title}"


def _short(text: str, limit: int = 32) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def main_menu(lang: str) -> ReplyKeyboardMarkup:
    b = lambda key: KeyboardButton(text=t(lang, key))  # noqa: E731
    return ReplyKeyboardMarkup(
        keyboard=[
            [b("menu_digest"), b("menu_style")],
            [b("menu_channels"), b("menu_add")],
            [b("menu_settings"), b("menu_status")],
            [b("menu_help")],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def grid(buttons: list[InlineKeyboardButton], per_row: int) -> list[list[InlineKeyboardButton]]:
    return [buttons[i : i + per_row] for i in range(0, len(buttons), per_row)]


def styles_keyboard(lang: str, current: str, callback_prefix: str) -> InlineKeyboardMarkup:
    from services.styles import STYLES, style_title

    buttons = [
        InlineKeyboardButton(
            text=("✅ " if key == current else "") + style_title(key, lang), callback_data=f"{callback_prefix}{key}"
        )
        for key in STYLES
    ]
    return InlineKeyboardMarkup(inline_keyboard=grid(buttons, 2))


# ---- groups and channels ----


def groups_keyboard(groups: list[tuple[Group, int]], lang: str) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=f"{_short(group_title(g, lang), 40)} ({n})", callback_data=f"grp:{g.id}:0")]
        for g, n in groups
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def group_keyboard(group: Group, channels: list[Channel], page: int, lang: str) -> InlineKeyboardMarkup:
    pages = max(1, -(-len(channels) // CHANNELS_PER_PAGE))
    page = min(max(page, 0), pages - 1)
    start = page * CHANNELS_PER_PAGE
    rows = [
        [InlineKeyboardButton(text=f"❌ {i}. {_short(c.title)}", callback_data=f"rmg:{group.id}:{c.id}:{page}")]
        for i, c in enumerate(channels[start : start + CHANNELS_PER_PAGE], start=start + 1)
    ]
    if pages > 1:
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton(text="◀", callback_data=f"grp:{group.id}:{page - 1}"))
        nav.append(InlineKeyboardButton(text=f"{page + 1}/{pages}", callback_data=f"grp:{group.id}:{page}"))
        if page < pages - 1:
            nav.append(InlineKeyboardButton(text="▶", callback_data=f"grp:{group.id}:{page + 1}"))
        rows.append(nav)
    rows.append(
        [
            InlineKeyboardButton(text=t(lang, "btn_group_add"), callback_data=f"gadd:{group.id}"),
            InlineKeyboardButton(text=t(lang, "btn_group_delete"), callback_data=f"gdel:{group.id}"),
        ]
    )
    rows.append([InlineKeyboardButton(text=t(lang, "btn_groups_back"), callback_data="grps")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def delete_confirm_keyboard(group: Group, lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=t(lang, "btn_confirm_delete"), callback_data=f"gdelok:{group.id}"),
                InlineKeyboardButton(text=t(lang, "btn_cancel"), callback_data=f"grp:{group.id}:0"),
            ]
        ]
    )


# ---- digest ----


def digest_menu(lang: str, style: str, groups: list[tuple[Group, int]]) -> InlineKeyboardMarkup:
    """Style, then which group. Group id 0 means every group, each with its own digest."""
    rows = [
        [InlineKeyboardButton(text=t(lang, "btn_digest_style", style=style), callback_data="dg:style")],
        [InlineKeyboardButton(text=t(lang, "btn_all_groups"), callback_data="dgg:0")],
    ]
    buttons = [
        InlineKeyboardButton(text=f"{_short(group_title(g, lang), 28)} ({n})", callback_data=f"dgg:{g.id}")
        for g, n in groups
        if n
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows + grid(buttons, 2))


def digest_period_menu(lang: str, group_id: int, style: str) -> InlineKeyboardMarkup:
    b = lambda key, window: InlineKeyboardButton(  # noqa: E731
        text=t(lang, key), callback_data=f"dgp:{group_id}:{window}"
    )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t(lang, "btn_digest_style", style=style), callback_data="dg:style")],
            [b("btn_unread", "new")],
            [b("btn_24h", "24"), b("btn_48h", "48"), b("btn_7d", "168")],
            [InlineKeyboardButton(text=t(lang, "back"), callback_data="dgm")],
        ]
    )
