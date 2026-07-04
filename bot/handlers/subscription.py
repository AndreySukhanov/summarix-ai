"""
Subscription status + payment via Telegram Stars (XTR).

Stars require ZERO payment-provider setup: no tokens, no webhooks,
no PSP account. send_invoice with currency="XTR" just works.
"""
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, LabeledPrice, Message, PreCheckoutQuery

from bot.keyboards import subscription_menu
from config.constants import Tier, TIER_LIMITS, TIER_PRICES_STARS
from database.connection import get_async_db
from database.models import Payment
from services.subscription_service import SubscriptionService
from utils.i18n import _
from utils.logger import get_logger

logger = get_logger("bot.subscription")
router = Router()


@router.message(Command("subscription"))
@router.callback_query(F.data == "subscription")
async def show_subscription(event: Message | CallbackQuery):
    tg = event.from_user
    lang = "ru" if tg.language_code == "ru" else "en"

    async with get_async_db() as db:
        user = await SubscriptionService.get_or_create_user(db, telegram_id=tg.id)
        sub = await SubscriptionService.get_subscription(db, user.id)
        limit = TIER_LIMITS[sub.tier]["requests"] + (sub.bonus_requests or 0)
        text = _("sub_status", lang, tier=sub.tier.value.upper(),
                 used=sub.requests_used, limit=limit)

    markup = subscription_menu(lang) if sub.tier == Tier.FREE else None
    if isinstance(event, CallbackQuery):
        await event.message.answer(text, reply_markup=markup, parse_mode="HTML")
        await event.answer()
    else:
        await event.answer(text, reply_markup=markup, parse_mode="HTML")


@router.callback_query(F.data == "buy_pro")
async def buy_pro(callback: CallbackQuery):
    lang = "ru" if callback.from_user.language_code == "ru" else "en"
    limit = TIER_LIMITS[Tier.PRO]["requests"]

    await callback.message.answer_invoice(
        title=_("sub_invoice_title", lang),
        description=_("sub_invoice_desc", lang, limit=limit),
        payload=f"sub:{Tier.PRO.value}",
        currency="XTR",
        prices=[LabeledPrice(label="PRO", amount=TIER_PRICES_STARS[Tier.PRO])],
    )
    await callback.answer()


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery):
    await query.answer(ok=True)


@router.message(F.successful_payment)
async def payment_success(message: Message):
    lang = "ru" if message.from_user.language_code == "ru" else "en"
    payment = message.successful_payment
    tier = Tier(payment.invoice_payload.split(":", 1)[1])

    async with get_async_db() as db:
        user = await SubscriptionService.get_or_create_user(
            db, telegram_id=message.from_user.id
        )
        sub = await SubscriptionService.upgrade(db, user.id, tier)
        db.add(Payment(
            user_id=user.id, tier=tier,
            amount_stars=payment.total_amount,
            telegram_charge_id=payment.telegram_payment_charge_id,
        ))
        until = sub.expires_at.strftime("%Y-%m-%d")

    logger.info(f"Payment: user {message.from_user.id} -> {tier.value}")
    await message.answer(_("sub_activated", lang, until=until))
