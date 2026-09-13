import re

import pytest
import pytest_asyncio

from bot.settings_menu import parse_time, utc_offset, valid_timezone
from database.db import add_channel, get_settings, init_models, make_sessionmaker, update_settings
from services.digest import DigestService
from services.reader import ChannelInfo
from services.styles import LANGUAGES, STYLES, TIMEZONE_PRESETS, style_prompt
from tests.fakes import NOW, FakeReader, fake_llm, make_post

DEFAULTS = {"style": "digest", "language": "ru", "digest_time": "09:00", "timezone": "Europe/Moscow"}
TECH = ChannelInfo(-1001, "Tech", "technews")


@pytest_asyncio.fixture
async def sessions():
    engine, maker = make_sessionmaker("sqlite+aiosqlite:///:memory:")
    await init_models(engine)
    yield maker
    await engine.dispose()


async def test_settings_row_is_seeded_once_then_updated(sessions):
    async with sessions() as db:
        first = await get_settings(db, DEFAULTS)
        assert (first.style, first.language, first.digest_time) == ("digest", "ru", "09:00")
        await update_settings(db, DEFAULTS, style="rick", digest_time="07:15")
    async with sessions() as db:
        again = await get_settings(db, {**DEFAULTS, "style": "tldr"})  # defaults no longer apply
        assert (again.style, again.digest_time) == ("rick", "07:15")


def test_style_prompt_follows_digest_language_and_custom_override():
    assert len(STYLES) == 13
    assert style_prompt("rick", "ru").startswith("Голос: гениальный учёный")
    assert style_prompt("rick", "es").startswith("Escribe como un científico genio")
    assert style_prompt("rick", "xx").startswith("You are a burned-out genius")  # unknown language -> English
    assert "я гений" not in style_prompt("rick", "ru").split("словам")[0]  # no instruction to brag
    assert style_prompt("rick", "ru", custom_prompt="  только цифры  ") == "только цифры"
    assert style_prompt("unknown", "en") == STYLES["digest"]["prompt"]["en"]


async def test_digest_uses_style_language_and_custom_prompt_from_settings(sessions):
    async with sessions() as db:
        await add_channel(db, TECH.peer_id, TECH.title, TECH.username)
        await db.commit()
        await update_settings(db, DEFAULTS, style="tldr", language="en")
    reader = FakeReader({TECH.peer_id: [make_post(TECH, 1, "news")]})
    llm, client = fake_llm()
    svc = DigestService(sessions, reader, llm, defaults=DEFAULTS)

    await svc.build(now=NOW)
    summary_request = next(r for r in client.requests if "Posts from the Telegram channel" in r["messages"][-1]["content"])
    user = summary_request["messages"][-1]["content"]
    assert "Write in English only." in user
    assert "put the source post number in square brackets" in user  # hard rules survive any style
    assert "130 words" in user
    assert "emoji" in user and "burps" in user
    assert user.index("news") < user.index("STYLE") < user.index("TL;DR")  # posts first, style last
    assert user.rstrip().endswith(STYLES["tldr"]["prompt"]["en"])

    async with sessions() as db:
        await update_settings(db, DEFAULTS, custom_prompt="Only numbers, like a trader.")
    await svc.build(now=NOW)
    user = client.requests[-1]["messages"][-1]["content"]
    assert user.rstrip().endswith("Only numbers, like a trader.") and "TL;DR" not in user


@pytest.mark.parametrize("raw, expected", [("08:30", "08:30"), ("8:05", "08:05"), ("23.59", "23:59"), ("24:00", None), ("abc", None)])
def test_parse_time(raw, expected):
    assert parse_time(raw) == expected


def test_interface_texts_complete_in_all_languages():
    from bot.keyboards import button_texts
    from bot.texts import TEXTS, UI_LANGUAGES

    assert UI_LANGUAGES == ("ru", "en", "es", "fr", "kk")
    reference = set(TEXTS["en"])
    for lang, table in TEXTS.items():
        assert set(table) == reference, (lang, reference ^ set(table))
        for key, text in table.items():
            if "{" in TEXTS["en"][key]:
                assert set(re.findall(r"{(\w+)}", text)) == set(re.findall(r"{(\w+)}", TEXTS["en"][key])), (lang, key)
    assert len(button_texts("menu_settings")) == 5


def test_every_style_is_translated():
    for key, style in STYLES.items():
        for lang in ("ru", "en", "es", "fr", "kk"):
            assert style["title"][lang] and style["prompt"][lang], (key, lang)


async def test_old_database_gets_ui_language_column(tmp_path):
    url = f"sqlite+aiosqlite:///{tmp_path / 'old.db'}"
    engine, maker = make_sessionmaker(url)
    async with engine.begin() as conn:  # the settings table as the first release created it
        await conn.exec_driver_sql(
            "CREATE TABLE settings (id INTEGER PRIMARY KEY, style VARCHAR(32), language VARCHAR(8), "
            "digest_time VARCHAR(5), timezone VARCHAR(64), custom_prompt TEXT)"
        )
        await conn.exec_driver_sql("INSERT INTO settings VALUES (1, 'rick', 'en', '08:00', 'UTC', NULL)")
    await init_models(engine)
    async with maker() as db:
        row = await get_settings(db, DEFAULTS)
        assert (row.style, row.ui_language) == ("rick", "ru")
    await engine.dispose()


def test_timezones():
    assert all(valid_timezone(name) for name in TIMEZONE_PRESETS)
    assert valid_timezone("Europe/Astrakhan")
    assert not valid_timezone("Mars/Olympus")
    assert utc_offset("UTC") == "UTC+0"
    assert set(LANGUAGES) == {"ru", "en", "es", "fr", "kk"}


def test_disclaimers_are_stripped_and_names_are_not_in_prompts():
    from services.llm import strip_disclaimer

    text = "Не могу копировать голос, но вот:\n\nСам пересказ [1]"
    assert strip_disclaimer(text) == "Сам пересказ [1]"
    assert strip_disclaimer("I can't do that.") == "I can't do that."  # nothing else left: keep as is
    assert strip_disclaimer("Normal text") == "Normal text"
    for lang in ("ru", "en"):
        prompt = STYLES["rick"]["prompt"][lang].lower()
        assert "burp" not in prompt and "буэ" not in prompt and "sanchez" not in prompt
