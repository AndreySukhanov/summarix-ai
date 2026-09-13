"""
Wiring: settings -> SQLite -> Telethon (owner's account) -> model -> bot + daily scheduler.
"""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from openai import AsyncOpenAI
from telethon import TelegramClient

from bot.handlers import OwnerOnly, build_router, send_digest
from config.settings import Settings
from database.db import init_models, make_sessionmaker
from services.digest import DigestService
from services.llm import LLM
from services.reader import TelethonReader
from services.scheduler import run_daily

logger = logging.getLogger("summarix")


async def main() -> None:
    settings = Settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    engine, sessions = make_sessionmaker(settings.database_url)
    await init_models(engine)

    client = TelegramClient(settings.tg_session, settings.tg_api_id, settings.tg_api_hash)
    await client.connect()
    if not await client.is_user_authorized():
        raise SystemExit("Telegram account is not logged in. Run once: python -m scripts.login")

    llm = LLM(
        AsyncOpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url),
        settings.llm_model,
        vision_model=settings.vision_model,
        language=settings.digest_language,
    )
    reader = TelethonReader(client)
    service = DigestService(
        sessions,
        reader,
        llm,
        lookback_hours=settings.lookback_hours,
        max_posts_per_channel=settings.max_posts_per_channel,
        describe_images=settings.describe_images,
        max_images_per_run=settings.max_images_per_run,
        ui_language=settings.ui_language,
        timezone_name=settings.timezone,
    )

    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher()
    dp.message.outer_middleware(OwnerOnly(settings.owner_id))
    dp.callback_query.outer_middleware(OwnerOnly(settings.owner_id))
    dp.include_router(
        build_router(
            sessions=sessions,
            reader=reader,
            service=service,
            lang=settings.ui_language,
            digest_time=settings.digest_time,
            timezone_name=settings.timezone,
            model=settings.llm_model,
        )
    )

    async def scheduled() -> None:
        await send_digest(bot, settings.owner_id, service, window_hours=None, trigger="schedule")

    scheduler = asyncio.create_task(run_daily(scheduled, settings.digest_time, settings.timezone))
    logger.info("bot started; digest daily at %s %s", settings.digest_time, settings.timezone)
    try:
        await dp.start_polling(bot)
    finally:
        scheduler.cancel()
        await client.disconnect()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
