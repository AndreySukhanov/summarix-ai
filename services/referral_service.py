"""
Referral program: "invite a friend — both get bonus requests".

Guards: self-referral, one referral per referred user (ever),
exhausted/inactive codes, banned referrers.
"""
import secrets
import string

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from config.constants import (
    REFERRAL_MAX_USES, REFERRAL_REFERRED_BONUS, REFERRAL_REFERRER_BONUS,
)
from database.models import Referral, ReferralCode, Subscription, User
from utils.logger import get_logger

logger = get_logger("services.referral")

_ALPHABET = string.ascii_uppercase + string.digits


class ReferralService:

    @staticmethod
    async def get_or_create_code(db: AsyncSession, user_id: int) -> ReferralCode:
        code = (await db.execute(
            select(ReferralCode).where(ReferralCode.user_id == user_id)
        )).scalars().first()
        if code is not None:
            return code

        for _ in range(5):  # retry on the (unlikely) unique collision
            candidate = "".join(secrets.choice(_ALPHABET) for _ in range(8))
            code = ReferralCode(
                user_id=user_id, code=candidate, max_uses=REFERRAL_MAX_USES
            )
            db.add(code)
            try:
                await db.flush()
                return code
            except IntegrityError:
                await db.rollback()
        raise RuntimeError("Could not generate a unique referral code")

    @staticmethod
    async def get_stats(db: AsyncSession, user_id: int) -> dict:
        invited = (await db.execute(
            select(func.count()).select_from(Referral).where(
                Referral.referrer_id == user_id
            )
        )).scalar() or 0
        return {"invited": invited, "bonus_earned": invited * REFERRAL_REFERRER_BONUS}

    @staticmethod
    async def apply_code(db: AsyncSession, code_str: str, referred_user: User) -> int | None:
        """
        Apply a referral code for a NEW user. Grants bonuses to both sides.
        Returns the referrer's telegram_id (to notify them) or None if rejected.
        """
        code = (await db.execute(
            select(ReferralCode).where(
                ReferralCode.code == code_str, ReferralCode.is_active.is_(True)
            )
        )).scalars().first()
        if code is None:
            return None
        if code.user_id == referred_user.id:
            return None  # self-referral
        if code.max_uses and code.uses_count >= code.max_uses:
            return None

        already = (await db.execute(
            select(Referral).where(Referral.referred_id == referred_user.id)
        )).scalars().first()
        if already is not None:
            return None

        referrer = (await db.execute(
            select(User).where(User.id == code.user_id)
        )).scalars().first()
        if referrer is None or referrer.is_banned:
            return None

        db.add(Referral(
            referrer_id=referrer.id, referred_id=referred_user.id, code_id=code.id
        ))
        code.uses_count += 1

        for user_id, bonus in (
            (referrer.id, REFERRAL_REFERRER_BONUS),
            (referred_user.id, REFERRAL_REFERRED_BONUS),
        ):
            sub = (await db.execute(
                select(Subscription).where(Subscription.user_id == user_id)
            )).scalars().first()
            if sub is not None:
                sub.bonus_requests = (sub.bonus_requests or 0) + bonus

        await db.flush()
        logger.info(f"Referral applied: {referrer.id} -> {referred_user.id}")
        return referrer.telegram_id
