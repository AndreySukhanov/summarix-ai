"""
/invite — personal referral link, stats and a share button.
"""
from urllib.parse import quote

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from config.constants import (
    REFERRAL_DEEP_LINK_PREFIX, REFERRAL_REFERRED_BONUS, REFERRAL_REFERRER_BONUS,
)
from database.connection import get_async_db
from services.referral_service import ReferralService
from services.subscription_service import SubscriptionService
from utils.i18n import _

router = Router()

_bot_username: str | None = None


async def _get_bot_username(bot) -> str:
    global _bot_username
    if _bot_username is None:
        _bot_username = (await bot.get_me()).username
    return _bot_username


@router.message(Command("invite"))
@router.callback_query(F.data == "referral")
async def show_referral(event: Message | CallbackQuery):
    tg = event.from_user
    lang = "ru" if tg.language_code == "ru" else "en"
    bot = event.bot

    async with get_async_db() as db:
        user = await SubscriptionService.get_or_create_user(db, telegram_id=tg.id)
        code = await ReferralService.get_or_create_code(db, user.id)
        stats = await ReferralService.get_stats(db, user.id)
        code_str = code.code

    username = await _get_bot_username(bot)
    link = f"https://t.me/{username}?start={REFERRAL_DEEP_LINK_PREFIX}{code_str}"
    share_url = f"https://t.me/share/url?url={quote(link)}"

    text = _("referral_message", lang,
             link=link,
             referred=REFERRAL_REFERRED_BONUS,
             referrer=REFERRAL_REFERRER_BONUS,
             invited=stats["invited"],
             earned=stats["bonus_earned"])
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Share", url=share_url)],
    ])

    target = event.message if isinstance(event, CallbackQuery) else event
    await target.answer(text, reply_markup=keyboard, parse_mode="HTML",
                        disable_web_page_preview=True)
    if isinstance(event, CallbackQuery):
        await event.answer()
