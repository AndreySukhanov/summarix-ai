"""
One-time login of the owner's Telegram account. Asks for the phone number, the code
Telegram sends, and the 2FA password if you have one. Creates the session file.

    python -m scripts.login
    docker compose run --rm bot python -m scripts.login
"""
import asyncio
import sys
from pathlib import Path

from telethon import TelegramClient

from config.settings import TelegramAccountSettings


def ask_phone() -> str:
    while True:
        phone = input("Phone number of YOUR account, e.g. +79991234567 (not the bot token): ").strip()
        if ":" in phone:
            print("That looks like a bot token. A bot cannot read your channels - enter a phone number.")
            continue
        return phone


async def login() -> None:
    settings = TelegramAccountSettings()
    session = Path(settings.tg_session)
    session.parent.mkdir(parents=True, exist_ok=True)
    client = TelegramClient(str(session), settings.tg_api_id, settings.tg_api_hash)
    await client.start(phone=ask_phone)
    me = await client.get_me()
    if me.bot:
        await client.log_out()  # also deletes the session file
        sys.exit("Logged in as a bot, which cannot read channels. Run again and enter your phone number.")
    print(f"Logged in as {me.first_name} (id {me.id}). Session: {session}.session")
    print("This file is full access to your account: never commit or share it.")
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(login())
