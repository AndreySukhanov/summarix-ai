"""
Users, subscriptions and usage quotas. All methods are async coroutines.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.constants import SUBSCRIPTION_DAYS, SubStatus, Tier, TIER_LIMITS
from database.models import Subscription, User


class SubscriptionService:

    @staticmethod
    async def get_or_create_user(
        db: AsyncSession, telegram_id: int,
        username: str = None, first_name: str = None, language: str = "en",
    ) -> User:
        user = (await db.execute(
            select(User).where(User.telegram_id == telegram_id)
        )).scalars().first()

        if user is None:
            user = User(
                telegram_id=telegram_id, username=username,
                first_name=first_name, language=language,
            )
            db.add(user)
            await db.flush()
            db.add(Subscription(user_id=user.id, tier=Tier.FREE, status=SubStatus.ACTIVE))
            await db.flush()
        else:
            user.last_active = datetime.now(timezone.utc)

        return user

    @staticmethod
    async def get_subscription(db: AsyncSession, user_id: int) -> Subscription | None:
        return (await db.execute(
            select(Subscription).where(Subscription.user_id == user_id)
        )).scalars().first()

    @staticmethod
    async def check_limit(db: AsyncSession, user_id: int) -> bool:
        """True if the user may make another AI request this month."""
        sub = await SubscriptionService.get_subscription(db, user_id)
        if sub is None:
            return False
        limit = TIER_LIMITS[sub.tier]["requests"] + (sub.bonus_requests or 0)
        return sub.requests_used < limit

    @staticmethod
    async def remaining(db: AsyncSession, user_id: int) -> int:
        sub = await SubscriptionService.get_subscription(db, user_id)
        if sub is None:
            return 0
        limit = TIER_LIMITS[sub.tier]["requests"] + (sub.bonus_requests or 0)
        return max(0, limit - sub.requests_used)

    @staticmethod
    async def increment_usage(db: AsyncSession, user_id: int):
        sub = await SubscriptionService.get_subscription(db, user_id)
        if sub is not None:
            sub.requests_used += 1

    @staticmethod
    async def upgrade(db: AsyncSession, user_id: int, tier: Tier) -> Subscription:
        """Activate a paid tier for SUBSCRIPTION_DAYS (called after payment)."""
        sub = await SubscriptionService.get_subscription(db, user_id)
        sub.tier = tier
        sub.status = SubStatus.ACTIVE
        sub.requests_used = 0
        sub.started_at = datetime.now(timezone.utc)
        sub.expires_at = datetime.now(timezone.utc) + timedelta(days=SUBSCRIPTION_DAYS)
        return sub
