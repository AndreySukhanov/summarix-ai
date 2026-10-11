from datetime import timedelta

import pytest
import pytest_asyncio

from bot.texts import TEXTS, t
from database.db import add_channel, init_models, make_sessionmaker
from scripts.tgdigest import Section, search_blocks
from services.reader import ChannelInfo
from services.search import SearchService, find_channels, parse_query, search_posts, split_terms, topic_matcher
from tests.fakes import NOW, FakeReader, fake_llm, make_post

DEFAULTS = {"style": "digest", "language": "ru", "digest_time": "09:00", "timezone": "Europe/Moscow"}
TECH = ChannelInfo(-1001, "Tech News", "technews")
PRIV = ChannelInfo(-1002, "Private notes", None)
XR = ChannelInfo(-1003, "XR media очки", "xrmedia")
SHOP = ChannelInfo(-1004, "Очки shop", "glassshop")
DEAD = ChannelInfo(-1005, "Old очки blog", "oldblog")
OFF = ChannelInfo(-1006, "Очки for cats, all about cats", "catsglasses")


@pytest_asyncio.fixture
async def sessions():
    engine, maker = make_sessionmaker("sqlite+aiosqlite:///:memory:")
    await init_models(engine)
    yield maker
    await engine.dispose()


async def seed(sessions, *channels):
    async with sessions() as db:
        for c in channels:
            await add_channel(db, c.peer_id, c.title, c.username)
        await db.commit()


def test_terms_and_query_parsing():
    assert split_terms("Rokid, умные очки; smart glasses\nRokid") == ["Rokid", "умные очки", "smart glasses"]
    assert parse_query("Rokid, умные очки 14") == ("Rokid, умные очки", 14)
    assert parse_query("Rokid") == ("Rokid", 30)
    assert parse_query("GPT 5000") == ("GPT", 365)  # capped
    assert parse_query("2026") == ("2026", 30)  # a lone number is the query, not the period
    assert parse_query(None) == ("", 30)


def test_topic_matcher_ignores_endings_needs_every_word_and_respects_word_starts():
    on_topic = topic_matcher(["умные очки", "AI очки", "смарт-очки", "Ray-Ban"])
    assert on_topic("Обзор умных очков от Rokid")
    assert on_topic("Новые смарт очки без камеры")
    assert on_topic("Ray Ban Display в продаже")
    assert not on_topic("Умные часы и AI агенты")  # no word for the glasses at all
    assert not on_topic("Точка роста для ИИ")  # «очк» inside «точка» is not a word start
    assert topic_matcher(["Rokid"])("rokid glasses review")


# ---------- posts ----------

async def test_search_merges_terms_per_channel_and_reports_broken_channels():
    reader = FakeReader({
        TECH.peer_id: [
            make_post(TECH, 1, "Rokid показали новые очки"),
            make_post(TECH, 2, "Обзор очков Rokid"),  # matches both terms: listed once
            make_post(TECH, 3, "про погоду"),
            make_post(TECH, 4, "Rokid снова", hours_ago=24 * 40),  # older than the window
        ],
        XR.peer_id: [make_post(XR, 7, "Smart glasses market")],
    })
    reader.failing.add(PRIV.peer_id)

    hits, errors = await search_posts(
        reader, [XR, PRIV, TECH], ["Rokid", "очков", "smart glasses"], since=NOW - timedelta(days=30)
    )

    assert [h.channel.title for h in hits] == ["XR media очки", "Tech News"]
    assert [p.message_id for p in hits[1].posts] == [1, 2]
    assert errors == ["Private notes (channel is private now)"]


# ---------- channels ----------

def channel_posts(channel, start, count, on_topic, days_ago=0.0):
    texts = ["новые очки вышли" if i < on_topic else "что-то другое" for i in range(count)]
    return [make_post(channel, start + i, text, hours_ago=24 * days_ago + i) for i, text in enumerate(texts)]


async def test_find_keeps_live_on_topic_channels_media_above_shop_and_skips_followed():
    reader = FakeReader({
        XR.peer_id: channel_posts(XR, 100, 30, on_topic=27),  # active media
        SHOP.peer_id: channel_posts(SHOP, 200, 3, on_topic=3, days_ago=20)[:1]
        + channel_posts(SHOP, 210, 5, on_topic=5, days_ago=90),  # one post a month
        DEAD.peer_id: channel_posts(DEAD, 300, 10, on_topic=10, days_ago=200),  # silent for months
        OFF.peer_id: channel_posts(OFF, 400, 20, on_topic=0),  # lively, but never about the topic
        TECH.peer_id: channel_posts(TECH, 500, 20, on_topic=20),
    })
    ghost = ChannelInfo(-1007, "Очки ghost", "gone")  # found, but its history cannot be read
    followed = ChannelInfo(TECH.peer_id, "Tech очки", "technews")
    reader.directory = [(SHOP, 10_000), (XR, 2471), (DEAD, 900), (OFF, 50), (ghost, 5), (followed, 100)]

    found = await find_channels(reader, ["очки"], now=NOW, exclude={TECH.peer_id})

    assert [f.channel.username for f in found] == ["xrmedia", "glassshop"]
    xr = found[0]
    assert (xr.subscribers, xr.posts_month, xr.on_topic, xr.sampled) == (2471, 30, 27, 30)


# ---------- the bot ----------

def search_replies(kwargs):
    content = kwargs["messages"][-1]["content"]
    if "Telegram search matches whole words" in content:
        return "1. очки\n- очков\n• smart glasses"
    if "found by a word in their name" in content:
        return "1, 3"  # the model drops number 2
    return "• Rokid показали очки [1], обзор [2]"


async def test_bot_search_widens_a_phrase_and_links_citations(sessions):
    await seed(sessions, TECH, XR)
    reader = FakeReader({TECH.peer_id: [make_post(TECH, 1, "Rokid и очки"), make_post(TECH, 2, "Обзор очков")]})
    llm, client = fake_llm(search_replies)
    svc = SearchService(sessions, reader, llm, defaults=DEFAULTS)

    [text] = await svc.search("очки", 30, "ru", now=NOW)

    assert {c["query"] for c in reader.calls} == {"очки", "очков", "smart glasses"}
    assert "🔎 <b>«очки»</b> за 30 дн. · каналов: 1 · постов: 2" in text
    assert "Искал по словам: очки, очков, smart glasses" in text
    assert '<a href="https://t.me/technews">Tech News</a>' in text
    assert '<a href="https://t.me/technews/1">1</a>' in text and '<a href="https://t.me/technews/2">2</a>' in text
    assert llm.language == "Russian"


async def test_bot_search_hides_channels_where_the_words_matched_in_another_sense(sessions):
    await seed(sessions, TECH, XR)
    reader = FakeReader({
        TECH.peer_id: [make_post(TECH, 1, "Набрал очки в рейтинге игры")],
        XR.peer_id: [make_post(XR, 5, "Новые очки Rokid")],
    })

    def replies(kwargs):
        content = kwargs["messages"][-1]["content"]
        return "NONE" if "Tech News" in content else "• Rokid показали очки [1]"

    llm, _ = fake_llm(replies)
    [text] = await SearchService(sessions, reader, llm, defaults=DEFAULTS).search("очки, Rokid", 30, "ru", now=NOW)

    assert "каналов: 1 · постов: 1" in text
    assert "XR media очки" in text and "Tech News" not in text

    llm, _ = fake_llm(lambda kw: "NONE")
    [text] = await SearchService(sessions, reader, llm, defaults=DEFAULTS).search("очки, Rokid", 30, "ru", now=NOW)
    assert text.startswith("По «очки, Rokid» за 30 дн. ничего не нашёл")


async def test_bot_search_with_commas_skips_the_model_and_says_when_nothing_found(sessions):
    await seed(sessions, TECH)
    reader = FakeReader({TECH.peer_id: [make_post(TECH, 1, "про погоду")]})
    llm, client = fake_llm(search_replies)
    svc = SearchService(sessions, reader, llm, defaults=DEFAULTS)

    [text] = await svc.search("Rokid, Ray-Ban", 7, "en", now=NOW)

    assert client.requests == []  # explicit terms: no expansion, nothing to retell
    assert text == "Nothing on «Rokid, Ray-Ban» in 7 days. Searched for: Rokid, Ray-Ban"


async def test_bot_find_lists_channels_with_stats_drops_what_the_model_rejects_and_skips_followed(sessions):
    await seed(sessions, TECH)
    reader = FakeReader({
        XR.peer_id: channel_posts(XR, 100, 30, on_topic=27),
        SHOP.peer_id: channel_posts(SHOP, 200, 10, on_topic=10),
        OFF.peer_id: channel_posts(OFF, 400, 20, on_topic=5),
        TECH.peer_id: channel_posts(TECH, 500, 20, on_topic=20),
    })
    reader.directory = [(XR, 2471), (SHOP, 50), (OFF, 10), (ChannelInfo(TECH.peer_id, "Tech очки", "technews"), 100)]
    llm, client = fake_llm(search_replies)
    svc = SearchService(sessions, reader, llm, defaults=DEFAULTS)

    text, found = await svc.find("очки", "ru", now=NOW)

    pick_prompt = client.requests[-1]["messages"][-1]["content"]
    assert "1. XR media очки - новые очки вышли" in pick_prompt  # title plus a recent on-topic post
    assert [f.channel.username for f in found] == ["xrmedia", "catsglasses"]  # the shop (2) dropped
    assert '1. <a href="https://t.me/xrmedia">XR media очки</a>' in text
    assert "👥 2 471 · постов за месяц: 30 · по теме 27 из 30" in text


async def test_pick_channels_falls_back_to_all_when_the_model_fails():
    def broken(kw):
        raise RuntimeError("API down")

    llm, _ = fake_llm(broken)
    assert await llm.pick_channels("очки", [("A", "a"), ("B", "b")]) == {0, 1}
    llm, _ = fake_llm(lambda kw: "none")
    assert await llm.pick_channels("очки", [("A", "a")]) == set()
    assert await llm.pick_channels("очки", []) == set()


@pytest.mark.parametrize("lang", list(TEXTS))
def test_search_texts_exist_in_every_language_and_help_mentions_the_commands(lang):
    t(lang, "search_title", query="q", days=1, channels=1, posts=1)
    t(lang, "search_nothing", query="q", days=1, terms="q")
    t(lang, "find_stats", subscribers="1", month=1, on_topic=1, sampled=1)
    for key in ("search_prompt", "searching", "find_prompt", "finding", "find_hint", "cmd_search", "cmd_find"):
        assert t(lang, key)
    help_text = t(lang, "help", time="09:00", tz="UTC")
    assert "/search" in help_text and "/find" in help_text
    assert "09:00" in help_text.split("\n\n")[-1]  # the schedule line still closes the help


# ---------- the model's search helpers ----------

async def test_search_terms_cleans_list_marks_but_keeps_numbers_inside_terms():
    llm, _ = fake_llm(lambda kw: "1. очки\n2) Rokid Max 2\n- очки\n\n«смарт-очки»")
    assert await llm.search_terms("очки") == ["очки", "Rokid Max 2", "смарт-очки"]

    def broken(kw):
        raise RuntimeError("API down")

    llm, _ = fake_llm(broken)
    assert await llm.search_terms("очки") == ["очки"]


# ---------- the skill's file ----------

def test_skill_search_file_header_names_terms_and_period():
    header, blocks = search_blocks(
        [Section(TECH, [make_post(TECH, 1, "Rokid и очки")])],
        ["Memes (gone)"],
        terms=["очки", "Rokid"],
        days=30,
        now=NOW,
        total_channels=54,
    )
    assert "# tgdigest · поиск за 30 дн." in header
    assert "Слова поиска: «очки», «Rokid»" in header
    assert "Каналов в списке: 54; с находками: 1; постов: 1" in header
    assert "Не прочитались: Memes (gone)" in header
    assert blocks[0].startswith("## 1. Tech News · https://t.me/technews")
