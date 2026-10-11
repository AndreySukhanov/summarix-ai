"""
Wiring: settings -> SQLite -> Telethon (owner's account) -> model -> bot + daily scheduler.
"""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from openai import AsyncOpenAI
from telethon import TelegramClient

from aiogram.types import BotCommand

from bot.handlers import build_router, send_digest
from bot.middlewares import OwnerOnly, UiLanguage
from bot.settings_menu import build_settings_router
from bot.texts import UI_LANGUAGES, t
from config.settings import Settings
from database.db import get_settings, init_models, make_sessionmaker
from services.digest import DigestService
from services.llm import LLM
from services.reader import TelethonReader
from services.scheduler import run_daily
from services.search import SearchService
from services.styles import DEFAULT_STYLE

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
    if (await client.get_me()).bot:
        raise SystemExit("The session belongs to a bot, which cannot read channels. Delete it and log in with your phone.")

    llm = LLM(
        AsyncOpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url),
        settings.llm_model,
        vision_model=settings.vision_model,
    )
    reader = TelethonReader(client)
    defaults = {
        "style": DEFAULT_STYLE,
        "language": settings.digest_language,
        "ui_language": settings.ui_language,
        "digest_time": settings.digest_time,
        "timezone": settings.timezone,
    }
    service = DigestService(
        sessions,
        reader,
        llm,
        lookback_hours=settings.lookback_hours,
        max_posts_per_channel=settings.max_posts_per_channel,
        describe_images=settings.describe_images,
        max_images_per_run=settings.max_images_per_run,
        defaults=defaults,
    )

    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher()
    for observer in (dp.message, dp.callback_query):
        observer.outer_middleware(OwnerOnly(settings.owner_id))
        observer.outer_middleware(UiLanguage(sessions, defaults))
    wake = asyncio.Event()
    # settings first: the main router ends with a catch-all for plain text
    dp.include_router(build_settings_router(sessions=sessions, defaults=defaults, wake=wake))
    # its own LLM wrapper: a search must not reset the token count of a digest running at the same time
    search_llm = LLM(llm.client, settings.llm_model, vision_model=settings.vision_model)
    searcher = SearchService(sessions, reader, search_llm, defaults=defaults)
    dp.include_router(
        build_router(
            sessions=sessions,
            reader=reader,
            service=service,
            searcher=searcher,
            defaults=defaults,
            model=settings.llm_model,
        )
    )
    await set_commands(bot)

    async def scheduled() -> None:
        await send_digest(bot, settings.owner_id, service, window_hours=None, trigger="schedule")

    async def schedule() -> tuple[str, str]:
        async with sessions() as db:
            prefs = await get_settings(db, defaults)
        return prefs.digest_time, prefs.timezone

    scheduler = asyncio.create_task(run_daily(scheduled, schedule, wake))
    logger.info("bot started")
    try:
        await dp.start_polling(bot)
    finally:
        scheduler.cancel()
        await client.disconnect()
        await engine.dispose()


async def set_commands(bot: Bot) -> None:
    """The "/" menu in Telegram, in each interface language."""
    names = ["start", "digest", "search", "find", "channels", "add", "settings", "status", "help"]
    for lang in UI_LANGUAGES:
        commands = [BotCommand(command=name, description=t(lang, f"cmd_{name}")) for name in names]
        await bot.set_my_commands(commands, language_code=None if lang == "en" else lang)


if __name__ == "__main__":
    asyncio.run(main())
