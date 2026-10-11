"""
Daily digest without Celery or Redis: one asyncio task that sleeps until the next run.
Time and timezone are read from the settings each round; `wake` interrupts the sleep
when the owner changes them, so a new time applies immediately.
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


async def run_daily(
    job: Callable[[], Awaitable[None]],
    schedule: Callable[[], Awaitable[tuple[str, str]]],
    wake: asyncio.Event,
    retry_s: float = 60,
) -> None:
    while True:
        wake.clear()  # before reading: a change made while the settings are read stays set
        try:
            hhmm, tz_name = await schedule()
            target = next_run_at(datetime.now(timezone.utc), hhmm, tz_name)
        except Exception:  # a busy database once must not end the daily digest for good
            logger.exception("could not read the schedule, retrying")
            try:
                await asyncio.wait_for(wake.wait(), timeout=retry_s)
            except asyncio.TimeoutError:
                pass
            continue
        delay = max((target - datetime.now(timezone.utc)).total_seconds(), 0)
        logger.info("next digest at %s (in %.0f min)", target.isoformat(), delay / 60)
        try:
            await asyncio.wait_for(wake.wait(), timeout=delay)
            continue  # schedule changed: recompute
        except asyncio.TimeoutError:
            pass
        try:
            await job()
        except Exception:
            logger.exception("scheduled digest failed")
