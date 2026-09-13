"""
OwnerOnly drops everyone but the owner. UiLanguage puts the current interface language
into handler data as `lang`, so a change in /settings applies to the very next message.
"""
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from database.db import SessionMaker, get_settings


class OwnerOnly(BaseMiddleware):
    def __init__(self, owner_id: int):
        self.owner_id = owner_id

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = getattr(event, "from_user", None)
        if user is None or user.id != self.owner_id:
            return None
        return await handler(event, data)


class UiLanguage(BaseMiddleware):
    def __init__(self, sessions: SessionMaker, defaults: dict):
        self.sessions = sessions
        self.defaults = defaults

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with self.sessions() as db:
            data["lang"] = (await get_settings(db, self.defaults)).ui_language
        return await handler(event, data)
