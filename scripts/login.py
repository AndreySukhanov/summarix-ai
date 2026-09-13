"""
One-time login of the owner's Telegram account. Asks for the phone number, the code
Telegram sends, and the 2FA password if you have one. Creates the session file.

    python -m scripts.login
    docker compose run --rm bot python -m scripts.login
"""
import asyncio
from pathlib import Path

from telethon import TelegramClient

from config.settings import TelegramAccountSettings


async def login() -> None:
    settings = TelegramAccountSettings()
    Path(settings.tg_session).parent.mkdir(parents=True, exist_ok=True)
    client = TelegramClient(settings.tg_session, settings.tg_api_id, settings.tg_api_hash)
    await client.start()  # interactive prompts
    me = await client.get_me()
    print(f"Logged in as {me.first_name} (id {me.id}). Session: {settings.tg_session}.session")
    print("This file is full access to your account: never commit or share it.")
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(login())
