import pytest

from config.constants import Tier, TIER_LIMITS
from services.subscription_service import SubscriptionService
from tests.conftest import create_subscription, create_user

pytestmark = pytest.mark.asyncio


async def test_get_or_create_user_creates_subscription(db_session):
    user = await SubscriptionService.get_or_create_user(db_session, telegram_id=42)
    sub = await SubscriptionService.get_subscription(db_session, user.id)
    assert sub is not None
    assert sub.tier == Tier.FREE


async def test_get_or_create_user_is_idempotent(db_session):
    u1 = await SubscriptionService.get_or_create_user(db_session, telegram_id=42)
    u2 = await SubscriptionService.get_or_create_user(db_session, telegram_id=42)
    assert u1.id == u2.id


async def test_limit_enforced(db_session):
    user = await create_user(db_session)
    sub = await create_subscription(db_session, user)

    free_limit = TIER_LIMITS[Tier.FREE]["requests"]
    sub.requests_used = free_limit - 1
    assert await SubscriptionService.check_limit(db_session, user.id) is True

    await SubscriptionService.increment_usage(db_session, user.id)
    assert await SubscriptionService.check_limit(db_session, user.id) is False
    assert await SubscriptionService.remaining(db_session, user.id) == 0


async def test_bonus_requests_extend_limit(db_session):
    user = await create_user(db_session)
    sub = await create_subscription(db_session, user)
    sub.requests_used = TIER_LIMITS[Tier.FREE]["requests"]

    assert await SubscriptionService.check_limit(db_session, user.id) is False
    sub.bonus_requests = 5
    assert await SubscriptionService.check_limit(db_session, user.id) is True
    assert await SubscriptionService.remaining(db_session, user.id) == 5


async def test_upgrade_resets_usage_and_sets_expiry(db_session):
    user = await create_user(db_session)
    sub = await create_subscription(db_session, user)
    sub.requests_used = 10

    upgraded = await SubscriptionService.upgrade(db_session, user.id, Tier.PRO)
    assert upgraded.tier == Tier.PRO
    assert upgraded.requests_used == 0
    assert upgraded.expires_at is not None
