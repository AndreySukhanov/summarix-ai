"""
Scheduled maintenance tasks (sync DB stack — Celery has no event loop).
"""
from datetime import datetime, timezone

from config.constants import SubStatus, Tier
from database.connection import get_db
from database.models import Subscription
from tasks.celery_app import celery_app
from utils.logger import get_logger

logger = get_logger("tasks")


@celery_app.task
def expire_subscriptions():
    """Downgrade paid subscriptions past their expiry date."""
    now = datetime.now(timezone.utc)
    with get_db() as db:
        expired = db.query(Subscription).filter(
            Subscription.tier != Tier.FREE,
            Subscription.expires_at.isnot(None),
            Subscription.expires_at < now,
        ).all()
        for sub in expired:
            sub.tier = Tier.FREE
            sub.status = SubStatus.ACTIVE
            sub.expires_at = None
            sub.requests_used = 0
    logger.info(f"Expired {len(expired)} subscriptions")
    return len(expired)


@celery_app.task
def reset_monthly_usage():
    """Reset FREE-tier counters on the 1st (paid tiers reset on renewal)."""
    with get_db() as db:
        updated = db.query(Subscription).filter(
            Subscription.tier == Tier.FREE,
        ).update({Subscription.requests_used: 0})
    logger.info(f"Reset monthly usage for {updated} free subscriptions")
    return updated
