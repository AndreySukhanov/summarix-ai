"""
The AI feature handler: any text message → quota check → AI call → reply.

This handler is registered LAST, so commands and other routers win first.
Swap services/ai_service.py to change what the bot actually does.
"""
from aiogram import F, Router
from aiogram.types import Message

from database.connection import get_async_db
from services.ai_service import generate_reply
from services.subscription_service import SubscriptionService
from utils.i18n import _
from utils.logger import get_logger

logger = get_logger("bot.ai")
router = Router()

MAX_MESSAGE_LEN = 4096


@router.message(F.text & ~F.text.startswith("/"))
async def handle_ai_request(message: Message):
    lang = "ru" if (message.from_user.language_code == "ru") else "en"

    async with get_async_db() as db:
        user = await SubscriptionService.get_or_create_user(
            db, telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
        )
        if not await SubscriptionService.check_limit(db, user.id):
            await message.answer(_("limit_reached", lang))
            return
        user_db_id = user.id

    thinking = await message.answer(_("thinking", lang))
    try:
        reply = await generate_reply(message.text)
    except Exception as e:
        logger.error(f"AI call failed: {e}", exc_info=True)
        await thinking.edit_text(_("ai_error", lang))
        return

    # Charge the quota only after a successful generation
    async with get_async_db() as db:
        await SubscriptionService.increment_usage(db, user_db_id)

    for chunk_start in range(0, len(reply), MAX_MESSAGE_LEN):
        chunk = reply[chunk_start:chunk_start + MAX_MESSAGE_LEN]
        if chunk_start == 0:
            await thinking.edit_text(chunk)
        else:
            await message.answer(chunk)
