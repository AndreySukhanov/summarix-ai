"""
Middlewares: ban check (DB-backed, cached) and a simple per-user rate limit.
"""
import time
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from sqlalchemy import select

from database.connection import get_async_db
from database.models import User
from utils.i18n import _

_BAN_CACHE: dict[int, tuple[bool, float]] = {}
_BAN_CACHE_TTL = 60  # seconds

_LAST_SEEN: dict[int, float] = {}
RATE_LIMIT_SECONDS = 1.0


def _event_user_id(event: TelegramObject) -> int | None:
    if isinstance(event, (Message, CallbackQuery)) and event.from_user:
        return event.from_user.id
    return None


class BanCheckMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user_id = _event_user_id(event)
        if user_id is None:
            return await handler(event, data)

        cached = _BAN_CACHE.get(user_id)
        if cached and time.monotonic() - cached[1] < _BAN_CACHE_TTL:
            banned = cached[0]
        else:
            banned = False
            try:
                async with get_async_db() as db:
                    user = (await db.execute(
                        select(User).where(User.telegram_id == user_id)
                    )).scalars().first()
                    banned = bool(user and user.is_banned)
            except Exception:
                pass  # DB down — let traffic through rather than lock everyone out
            _BAN_CACHE[user_id] = (banned, time.monotonic())

        if banned:
            if isinstance(event, Message):
                await event.answer(_("banned"))
            elif isinstance(event, CallbackQuery):
                await event.answer(_("banned"), show_alert=True)
            return None

        return await handler(event, data)


class RateLimitMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user_id = _event_user_id(event)
        if user_id is None or not isinstance(event, Message):
            return await handler(event, data)

        now = time.monotonic()
        last = _LAST_SEEN.get(user_id, 0.0)
        _LAST_SEEN[user_id] = now
        if now - last < RATE_LIMIT_SECONDS:
            await event.answer(_("rate_limited"))
            return None

        return await handler(event, data)
