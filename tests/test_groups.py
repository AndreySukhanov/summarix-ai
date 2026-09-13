from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio

from bot.handlers import send_digest
from database.db import (
    add_channel,
    add_to_group,
    delete_group,
    folder_group,
    group_channels,
    init_models,
    list_channels,
    list_groups,
    make_sessionmaker,
    manual_group,
    remove_from_group,
)
from services.digest import DigestService
from services.reader import ChannelInfo  # noqa: E402
from services.reader import Post, post_link
from tests.fakes import FakeReader, fake_llm


def make_post(channel, message_id, text):
    """send_digest uses the real clock, so posts are dated relative to it."""
    date = datetime.now(timezone.utc) - timedelta(hours=1)
    return Post(message_id, date, text, post_link(channel, message_id))


@pytest.fixture(autouse=True)
def no_real_digest_file(tmp_path, monkeypatch):
    monkeypatch.setattr("bot.handlers.LAST_DIGEST_PATH", tmp_path / "last_digest.txt")

AI = ChannelInfo(-1001, "AI news", "ainews")
GAMES = ChannelInfo(-1002, "Games", "games")
BOTH = ChannelInfo(-1003, "Tech and games", "techgames")


@pytest_asyncio.fixture
async def sessions():
    engine, maker = make_sessionmaker("sqlite+aiosqlite:///:memory:")
    await init_models(engine)
    yield maker
    await engine.dispose()


async def test_channels_from_before_groups_move_to_my_channels(tmp_path):
    engine, maker = make_sessionmaker(f"sqlite+aiosqlite:///{tmp_path / 'old.db'}")
    await init_models(engine)
    async with maker() as db:  # the old bot stored channels without any group
        for c in (AI, GAMES):
            await add_channel(db, c.peer_id, c.title, c.username)
        await db.commit()
    await init_models(engine)  # next start
    async with maker() as db:
        groups = await list_groups(db)
        assert [(g.kind, n) for g, n in groups] == [("manual", 2)]
    await engine.dispose()


async def test_folder_group_is_reused_and_channels_can_be_in_several_groups(sessions):
    async with sessions() as db:
        folder = await folder_group(db, "slug1", "Tech folder")
        again = await folder_group(db, "slug1", "Tech folder renamed")
        assert folder.id == again.id and again.title == "Tech folder renamed"
        mine = await manual_group(db)
        _, new1 = await add_to_group(db, folder, BOTH.peer_id, BOTH.title, BOTH.username)
        _, new2 = await add_to_group(db, mine, BOTH.peer_id, BOTH.title, BOTH.username)
        _, dup = await add_to_group(db, mine, BOTH.peer_id, BOTH.title, BOTH.username)
        await db.commit()
        assert (new1, new2, dup) == (True, True, False)
        assert len(await list_channels(db)) == 1  # one channel, two memberships
        assert {g.kind: n for g, n in await list_groups(db)} == {"manual": 1, "folder": 1}


async def test_removing_last_membership_removes_the_channel(sessions):
    async with sessions() as db:
        folder = await folder_group(db, "s", "F")
        mine = await manual_group(db)
        both, _ = await add_to_group(db, folder, BOTH.peer_id, BOTH.title, BOTH.username)
        await add_to_group(db, mine, BOTH.peer_id, BOTH.title, BOTH.username)
        only, _ = await add_to_group(db, folder, AI.peer_id, AI.title, AI.username)
        await db.commit()

        await delete_group(db, folder.id)
        await db.commit()
        titles = {c.title for c in await list_channels(db)}
        assert titles == {"Tech and games"}  # AI news was only in the deleted folder

        await remove_from_group(db, mine.id, both.id)
        await db.commit()
        assert await list_channels(db) == []


class FakeBot:
    def __init__(self):
        self.sent: list[str] = []

    async def send_message(self, chat_id, text, **kwargs):
        self.sent.append(text)


async def seed_groups(sessions):
    async with sessions() as db:
        ai = await folder_group(db, "ai", "AI")
        games = await folder_group(db, "games", "Games")
        await add_to_group(db, ai, AI.peer_id, AI.title, AI.username)
        await add_to_group(db, games, GAMES.peer_id, GAMES.title, GAMES.username)
        await db.commit()
        return ai.id, games.id


async def test_each_group_gets_its_own_digest(sessions):
    ai_id, games_id = await seed_groups(sessions)
    reader = FakeReader({AI.peer_id: [make_post(AI, 1, "model")], GAMES.peer_id: [make_post(GAMES, 5, "patch")]})
    llm, _ = fake_llm()
    svc = DigestService(sessions, reader, llm, ui_language="en")
    bot = FakeBot()

    await send_digest(bot, 1, svc, window_hours=None, trigger="manual")
    assert len(bot.sent) == 2
    assert "📁 AI" in bot.sent[0] and "Games" not in bot.sent[0]
    assert "📁 Games" in bot.sent[1] and "AI news" not in bot.sent[1]
    async with sessions() as db:
        assert {c.title: c.last_message_id for c in await list_channels(db)} == {"AI news": 1, "Games": 5}


async def test_quiet_groups_stay_silent_and_single_group_digest(sessions):
    ai_id, games_id = await seed_groups(sessions)
    reader = FakeReader({AI.peer_id: [make_post(AI, 1, "model")]})  # games has nothing new
    llm, _ = fake_llm()
    svc = DigestService(sessions, reader, llm, ui_language="en")

    bot = FakeBot()
    await send_digest(bot, 1, svc, window_hours=24, trigger="manual")
    assert len(bot.sent) == 1 and "📁 AI" in bot.sent[0]

    bot = FakeBot()
    await send_digest(bot, 1, svc, window_hours=24, trigger="manual", group_id=games_id)
    assert len(bot.sent) == 1 and "No new posts." in bot.sent[0] and "📁 Games" in bot.sent[0]

    reader.posts = {}
    bot = FakeBot()
    await send_digest(bot, 1, svc, window_hours=24, trigger="manual")
    assert len(bot.sent) == 1 and "No new posts." in bot.sent[0]


async def test_group_channels_listing(sessions):
    ai_id, _ = await seed_groups(sessions)
    async with sessions() as db:
        assert [c.title for c in await group_channels(db, ai_id)] == ["AI news"]
