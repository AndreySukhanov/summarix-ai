"""
/start: register the user, apply referral deep-link (new users only), show menu.
Deep-link format: https://t.me/<bot>?start=ref_<code>
"""
from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from sqlalchemy import select

from bot.keyboards import main_menu
from config.constants import (
    REFERRAL_DEEP_LINK_PREFIX, REFERRAL_REFERRED_BONUS, REFERRAL_REFERRER_BONUS,
    Tier, TIER_LIMITS,
)
from database.connection import get_async_db
from database.models import User
from services.referral_service import ReferralService
from services.subscription_service import SubscriptionService
from utils.i18n import _
from utils.logger import get_logger

logger = get_logger("bot.start")
router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message, command: CommandObject = None):
    tg = message.from_user
    lang = "ru" if tg.language_code == "ru" else "en"
    deep_link_arg = (command.args or "").strip() if command else ""

    referrer_telegram_id = None
    async with get_async_db() as db:
        is_new = (await db.execute(
            select(User.id).where(User.telegram_id == tg.id)
        )).scalars().first() is None

        user = await SubscriptionService.get_or_create_user(
            db, telegram_id=tg.id, username=tg.username,
            first_name=tg.first_name, language=lang,
        )

        if is_new and deep_link_arg.startswith(REFERRAL_DEEP_LINK_PREFIX):
            code = deep_link_arg[len(REFERRAL_DEEP_LINK_PREFIX):]
            referrer_telegram_id = await ReferralService.apply_code(db, code, user)

    await message.answer(
        _("start", lang, name=tg.first_name or "friend",
          free_limit=TIER_LIMITS[Tier.FREE]["requests"]),
        reply_markup=main_menu(lang),
    )

    if referrer_telegram_id:
        await message.answer(_("referral_welcome", lang, bonus=REFERRAL_REFERRED_BONUS))
        try:
            await message.bot.send_message(
                referrer_telegram_id,
                _("referral_reward", lang, bonus=REFERRAL_REFERRER_BONUS),
            )
        except Exception:
            pass  # referrer blocked the bot — their problem, not ours
