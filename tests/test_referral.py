import pytest
from sqlalchemy import select

from config.constants import REFERRAL_REFERRED_BONUS, REFERRAL_REFERRER_BONUS
from database.models import Referral
from services.referral_service import ReferralService
from tests.conftest import create_subscription, create_user

pytestmark = pytest.mark.asyncio


async def test_code_is_idempotent(db_session):
    user = await create_user(db_session, telegram_id=1)
    await create_subscription(db_session, user)

    c1 = await ReferralService.get_or_create_code(db_session, user.id)
    c2 = await ReferralService.get_or_create_code(db_session, user.id)
    assert c1.code == c2.code
    assert len(c1.code) == 8


async def test_apply_grants_both_bonuses(db_session):
    referrer = await create_user(db_session, telegram_id=1)
    referrer_sub = await create_subscription(db_session, referrer)
    friend = await create_user(db_session, telegram_id=2)
    friend_sub = await create_subscription(db_session, friend)

    code = await ReferralService.get_or_create_code(db_session, referrer.id)
    result = await ReferralService.apply_code(db_session, code.code, friend)

    assert result == referrer.telegram_id
    assert referrer_sub.bonus_requests == REFERRAL_REFERRER_BONUS
    assert friend_sub.bonus_requests == REFERRAL_REFERRED_BONUS
    assert (await db_session.execute(select(Referral))).scalars().one() is not None


async def test_self_referral_rejected(db_session):
    user = await create_user(db_session, telegram_id=1)
    sub = await create_subscription(db_session, user)

    code = await ReferralService.get_or_create_code(db_session, user.id)
    assert await ReferralService.apply_code(db_session, code.code, user) is None
    assert (sub.bonus_requests or 0) == 0


async def test_only_once_per_referred_user(db_session):
    r1 = await create_user(db_session, telegram_id=1)
    await create_subscription(db_session, r1)
    r2 = await create_user(db_session, telegram_id=2)
    r2_sub = await create_subscription(db_session, r2)
    friend = await create_user(db_session, telegram_id=3)
    await create_subscription(db_session, friend)

    code1 = await ReferralService.get_or_create_code(db_session, r1.id)
    code2 = await ReferralService.get_or_create_code(db_session, r2.id)

    assert await ReferralService.apply_code(db_session, code1.code, friend) is not None
    assert await ReferralService.apply_code(db_session, code2.code, friend) is None
    assert (r2_sub.bonus_requests or 0) == 0


async def test_unknown_code_returns_none(db_session):
    friend = await create_user(db_session, telegram_id=1)
    await create_subscription(db_session, friend)
    assert await ReferralService.apply_code(db_session, "NOPE1234", friend) is None


async def test_stats(db_session):
    referrer = await create_user(db_session, telegram_id=1)
    await create_subscription(db_session, referrer)
    code = await ReferralService.get_or_create_code(db_session, referrer.id)

    for tid in (2, 3):
        friend = await create_user(db_session, telegram_id=tid)
        await create_subscription(db_session, friend)
        await ReferralService.apply_code(db_session, code.code, friend)

    stats = await ReferralService.get_stats(db_session, referrer.id)
    assert stats == {"invited": 2, "bonus_earned": 2 * REFERRAL_REFERRER_BONUS}
