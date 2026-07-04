"""
Bot entry point: init DB, pick FSM storage (Redis with ping-verified
fallback to memory), register middlewares and routers, start polling.

Router order matters in aiogram — first match wins. The AI handler
catches all plain text, so it goes last.
"""
import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from bot.handlers import admin, ai, referral, start, subscription
from bot.middlewares import BanCheckMiddleware, RateLimitMiddleware
from config.settings import settings
from database.connection import init_db
from utils.logger import get_logger

logger = get_logger("bot")


async def _make_storage():
    """Redis-backed FSM storage if Redis is reachable, else in-memory."""
    try:
        from aiogram.fsm.storage.redis import RedisStorage
        from redis.asyncio import Redis

        redis = Redis.from_url(settings.redis_url)
        await redis.ping()
        logger.info("FSM storage: Redis")
        return RedisStorage(redis=redis)
    except Exception as e:
        logger.warning(f"Redis unavailable ({e}), FSM storage: memory")
        return MemoryStorage()


async def main():
    logger.info("Starting bot...")

    try:
        init_db()
        logger.info("Database ready")
    except Exception as e:
        logger.warning(f"Database unavailable: {e} — starting anyway")

    bot = Bot(token=settings.bot_token, default=DefaultBotProperties())
    dp = Dispatcher(storage=await _make_storage())

    dp.message.middleware(BanCheckMiddleware())
    dp.callback_query.middleware(BanCheckMiddleware())
    dp.message.middleware(RateLimitMiddleware())

    dp.include_router(admin.router)
    dp.include_router(start.router)
    dp.include_router(subscription.router)
    dp.include_router(referral.router)
    dp.include_router(ai.router)  # catch-all for text — keep last

    logger.info("Bot started, polling...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
