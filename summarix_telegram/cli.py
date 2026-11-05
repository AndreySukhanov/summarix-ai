"""Console commands of the installed package (pipx install summarix-telegram).

summarix-bot and summarix-login work in SUMMARIX_HOME when it is set, else in the current folder:
that is where .env, data/ (the database, the Telegram session) and exports/ live. tgdigest and
summarix-mcp find the same folder on their own (see scripts/tgdigest.py `_home`)."""
import asyncio
import os
from pathlib import Path


def _enter_home() -> None:
    home = os.environ.get("SUMMARIX_HOME")
    if home:
        os.chdir(Path(home).expanduser())


def bot() -> None:
    _enter_home()
    from summarix_telegram.bot.main import main

    asyncio.run(main())


def login() -> None:
    _enter_home()
    from summarix_telegram.scripts.login import main

    main()
