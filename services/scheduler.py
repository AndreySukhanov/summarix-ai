"""
Daily digest without Celery or Redis: one asyncio task that sleeps until the next run.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Awaitable, Callable
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)


def next_run_at(now: datetime, hhmm: str, tz_name: str) -> datetime:
    """The next moment the local clock in tz_name shows hhmm, returned in UTC."""
    tz = ZoneInfo(tz_name)
    hour, minute = (int(x) for x in hhmm.split(":"))
    local_now = now.astimezone(tz)
    candidate = local_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= local_now:
        candidate = (local_now + timedelta(days=1)).replace(hour=hour, minute=minute, second=0, microsecond=0)
    return candidate.astimezone(timezone.utc)


async def run_daily(job: Callable[[], Awaitable[None]], hhmm: str, tz_name: str) -> None:
    while True:
        target = next_run_at(datetime.now(timezone.utc), hhmm, tz_name)
        delay = (target - datetime.now(timezone.utc)).total_seconds()
        logger.info("next digest at %s (in %.0f min)", target.isoformat(), delay / 60)
        await asyncio.sleep(max(delay, 0))
        try:
            await job()
        except Exception:
            logger.exception("scheduled digest failed")
