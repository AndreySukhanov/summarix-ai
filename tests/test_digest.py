from datetime import timedelta
from types import SimpleNamespace

import pytest_asyncio

from bot.handlers import extract_refs
from bot.middlewares import OwnerOnly
from database.db import add_channel, init_models, last_run, list_channels, make_sessionmaker
from services.digest import DigestService
from services.reader import ChannelInfo
from tests.fakes import NOW, FakeReader, fake_llm, make_post

TECH = ChannelInfo(-1001, "Tech <News>", "technews")
PRIV = ChannelInfo(-1002, "Private notes", None)


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


def service(sessions, reader, llm, **kw):
    return DigestService(sessions, reader, llm, ui_language="en", **kw)


async def test_no_channels_message(sessions):
    llm, _ = fake_llm()
    result = await service(sessions, FakeReader(), llm).build(now=NOW)
    assert "No channels yet" in result.messages[0]


async def test_digest_marks_read_only_after_commit(sessions):
    await seed(sessions, TECH)
    reader = FakeReader({TECH.peer_id: [make_post(TECH, 10, "one"), make_post(TECH, 11, "two")]})
    llm, _ = fake_llm()
    svc = service(sessions, reader, llm)

    first = await svc.build(now=NOW)
    assert first.posts == 2 and first.read_marks == {TECH.peer_id: 11}
    assert '<a href="https://t.me/technews/10">1</a>' in first.messages[0]
    assert "Tech &lt;News&gt;" in first.messages[0]

    again = await svc.build(now=NOW)  # nothing committed yet: same posts again
    assert again.posts == 2

    await svc.commit(first, "manual")
    after = await svc.build(now=NOW)
    assert after.posts == 0 and "No new posts." in after.messages[0]
    async with sessions() as db:
        assert (await list_channels(db))[0].last_message_id == 11
        run = await last_run(db)
        assert run.posts == 2 and run.input_tokens > 0


async def test_new_channel_looks_back_only_lookback_hours(sessions):
    await seed(sessions, TECH)
    reader = FakeReader({TECH.peer_id: [make_post(TECH, 1, "old", hours_ago=30), make_post(TECH, 2, "fresh")]})
    llm, _ = fake_llm()
    result = await service(sessions, reader, llm, lookback_hours=24).build(now=NOW)
    assert result.posts == 1
    assert reader.calls[0]["since"] == NOW - timedelta(hours=24)


async def test_recap_window_ignores_read_marks_and_marks_nothing(sessions):
    await seed(sessions, TECH)
    reader = FakeReader({TECH.peer_id: [make_post(TECH, 5, "a", hours_ago=40), make_post(TECH, 6, "b")]})
    llm, _ = fake_llm()
    svc = service(sessions, reader, llm)
    await svc.commit(await svc.build(now=NOW), "schedule")

    recap = await svc.build(window_hours=48, now=NOW)
    assert recap.posts == 2 and recap.read_marks == {}
    assert reader.calls[-1]["after_id"] == 0
    assert "Last 48 h" in recap.messages[0]


async def test_image_captions_are_capped_per_run(sessions):
    await seed(sessions, TECH)
    reader = FakeReader({TECH.peer_id: [make_post(TECH, 1, "", images=2), make_post(TECH, 2, "chart", images=2)]})
    llm, client = fake_llm()
    result = await service(sessions, reader, llm, max_images_per_run=3).build(now=NOW)

    assert result.images == 3
    image_calls = [r for r in client.requests if isinstance(r["messages"][-1]["content"], list)]
    assert len(image_calls) == 3
    assert image_calls[0]["messages"][-1]["content"][1]["image_url"]["detail"] == "low"
    summary_prompt = next(r for r in client.requests if r["messages"][0]["role"] == "system")
    assert "(image: A chart with revenue up 20%)" in summary_prompt["messages"][1]["content"]


async def test_images_disabled_means_no_downloads(sessions):
    await seed(sessions, TECH)
    reader = FakeReader({TECH.peer_id: [make_post(TECH, 1, "x", images=1)]})
    llm, client = fake_llm()
    await service(sessions, reader, llm, describe_images=False).build(now=NOW)
    assert reader.calls[0]["with_images"] is False
    assert all(not isinstance(r["messages"][-1]["content"], list) for r in client.requests)


async def test_broken_channel_is_reported_and_others_still_arrive(sessions):
    await seed(sessions, TECH, PRIV)
    reader = FakeReader({TECH.peer_id: [make_post(TECH, 1, "x")]})
    reader.failing.add(PRIV.peer_id)
    llm, _ = fake_llm()
    result = await service(sessions, reader, llm).build(now=NOW)
    assert result.channels_with_news == 1
    assert PRIV.peer_id not in result.read_marks
    assert "Could not read: Private notes (channel is private now)" in result.messages[-1]


async def test_highlights_only_with_two_or_more_channels(sessions):
    await seed(sessions, TECH, PRIV)
    reader = FakeReader({TECH.peer_id: [make_post(TECH, 1, "x")], PRIV.peer_id: [make_post(PRIV, 3, "y")]})
    llm, _ = fake_llm()
    text = "\n".join((await service(sessions, reader, llm).build(now=NOW)).messages)
    assert "<b>Highlights</b>" in text and "• Big news (Tech)" in text
    assert '<a href="https://t.me/c/2/3">1</a>' in text  # private channel link


def test_plain_message_links_are_found():
    text = "вот папка https://t.me/addlist/AbC_1 и ещё @durov_news, спасибо"
    assert extract_refs(text) == ["https://t.me/addlist/AbC_1", "@durov_news"]
    assert extract_refs("просто текст") == []


async def test_owner_only_middleware_drops_strangers():
    seen = []

    async def handler(event, data):
        seen.append(event)
        return "ok"

    mw = OwnerOnly(owner_id=42)
    assert await mw(handler, SimpleNamespace(from_user=SimpleNamespace(id=7)), {}) is None
    assert await mw(handler, SimpleNamespace(from_user=None), {}) is None
    assert await mw(handler, SimpleNamespace(from_user=SimpleNamespace(id=42)), {}) == "ok"
    assert len(seen) == 1
