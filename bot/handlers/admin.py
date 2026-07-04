"""
Admin commands (gated by ADMIN_ID from .env):
/stats — funnel: registrations → activation → paying
/ban <telegram_id>, /unban <telegram_id>
"""
from datetime import datetime, timedelta, timezone

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import func, select

from config.constants import SubStatus, Tier
from config.settings import settings
from database.connection import get_async_db
from database.models import Referral, Subscription, User
from utils.logger import get_logger

logger = get_logger("bot.admin")
router = Router()


def is_admin(user_id: int) -> bool:
    return user_id == settings.admin_id


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    if not is_admin(message.from_user.id):
        return

    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)

    async with get_async_db() as db:
        async def count_users(*where):
            return (await db.execute(
                select(func.count()).select_from(User).where(*where)
            )).scalar() or 0

        total = await count_users()
        new_week = await count_users(User.created_at >= week_ago)
        active_week = await count_users(User.last_active >= week_ago)
        paying = (await db.execute(
            select(func.count()).select_from(Subscription).where(
                Subscription.tier != Tier.FREE,
                Subscription.status == SubStatus.ACTIVE,
            )
        )).scalar() or 0
        activated = (await db.execute(
            select(func.count()).select_from(Subscription).where(
                Subscription.requests_used > 0
            )
        )).scalar() or 0
        referrals = (await db.execute(
            select(func.count()).select_from(Referral)
        )).scalar() or 0

    def pct(part, whole):
        return f"{part / whole * 100:.0f}%" if whole else "—"

    await message.answer(
        "📊 <b>Funnel</b>\n\n"
        f"Users: {total} (+{new_week} last 7d)\n"
        f"Activated (≥1 request): {activated} ({pct(activated, total)})\n"
        f"Active last 7d: {active_week} ({pct(active_week, total)})\n"
        f"Referrals: {referrals}\n"
        f"Paying: {paying} ({pct(paying, total)} conversion)",
        parse_mode="HTML",
    )


async def _set_ban(message: Message, banned: bool):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer(f"Usage: /{'ban' if banned else 'unban'} <telegram_id>")
        return

    telegram_id = int(parts[1])
    async with get_async_db() as db:
        user = (await db.execute(
            select(User).where(User.telegram_id == telegram_id)
        )).scalars().first()
        if user is None:
            await message.answer("User not found")
            return
        user.is_banned = banned

    logger.info(f"Admin {'banned' if banned else 'unbanned'} {telegram_id}")
    await message.answer(f"{'🚫 Banned' if banned else '✅ Unbanned'}: {telegram_id}")


@router.message(Command("ban"))
async def cmd_ban(message: Message):
    await _set_ban(message, True)


@router.message(Command("unban"))
async def cmd_unban(message: Message):
    await _set_ban(message, False)
