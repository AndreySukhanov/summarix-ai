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


def test_every_style_has_both_prompt_variants_and_titles():
    assert len(STYLES) == 13
    for key, style in STYLES.items():
        assert style["prompt_ru"] and style["prompt_en"] and style["title_ru"] and style["title_en"], key


def test_style_prompt_language_variant_and_custom_override():
    assert style_prompt("rick", "ru").startswith("Пиши как циничный гений")
    assert style_prompt("rick", "es").startswith("Write as a cynical genius")
    assert style_prompt("rick", "ru", custom_prompt="  только цифры  ") == "только цифры"
    assert style_prompt("unknown", "en") == STYLES["digest"]["prompt_en"]


async def test_digest_uses_style_language_and_custom_prompt_from_settings(sessions):
    async with sessions() as db:
        await add_channel(db, TECH.peer_id, TECH.title, TECH.username)
        await db.commit()
        await update_settings(db, DEFAULTS, style="tldr", language="en")
    reader = FakeReader({TECH.peer_id: [make_post(TECH, 1, "news")]})
    llm, client = fake_llm()
    svc = DigestService(sessions, reader, llm, defaults=DEFAULTS)

    await svc.build(now=NOW)
    system = client.requests[-1]["messages"][0]["content"]
    assert "Write in English." in system
    assert "TL;DR" in system
    assert "cite its source posts by number" in system  # hard rules survive any style

    async with sessions() as db:
        await update_settings(db, DEFAULTS, custom_prompt="Only numbers, like a trader.")
    await svc.build(now=NOW)
    system = client.requests[-1]["messages"][0]["content"]
    assert "Only numbers, like a trader." in system and "TL;DR" not in system


@pytest.mark.parametrize("raw, expected", [("08:30", "08:30"), ("8:05", "08:05"), ("23.59", "23:59"), ("24:00", None), ("abc", None)])
def test_parse_time(raw, expected):
    assert parse_time(raw) == expected


def test_timezones():
    assert all(valid_timezone(name) for name in TIMEZONE_PRESETS)
    assert valid_timezone("Europe/Astrakhan")
    assert not valid_timezone("Mars/Olympus")
    assert utc_offset("UTC") == "UTC+0"
    assert set(LANGUAGES) == {"ru", "en", "es", "fr", "kk"}
