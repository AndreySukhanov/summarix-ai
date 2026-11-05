"""The MCP server, offline: a fake Telegram reader, a temporary data folder, no network."""
from datetime import datetime, timedelta, timezone

import pytest

from scripts import mcp_server as srv
from scripts import tgdigest as td
from services.reader import ChannelInfo, Post, post_link
from tests.fakes import FakeReader

TECH = ChannelInfo(-1001, "Tech News", "technews")
MEMES = ChannelInfo(-1003, "Memes", "memes")


def recent_post(channel: ChannelInfo, message_id: int, text: str, hours_ago: float = 1) -> Post:
    return Post(message_id, datetime.now(timezone.utc) - timedelta(hours=hours_ago), text, post_link(channel, message_id))


class FakeClient:
    def __init__(self):
        self.disconnected = 0

    async def disconnect(self):
        self.disconnected += 1


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Data in a temp folder, a logged-in fake client and a fake reader with two channels."""
    data = tmp_path / "tgdigest"
    monkeypatch.setattr(td, "DATA", data)
    monkeypatch.setattr(td, "LIST_FILE", data / "channels.json")
    monkeypatch.setattr(td, "IMAGES_DIR", data / "img")
    monkeypatch.setattr(td, "BOT_DB", tmp_path / "summarix.db")
    client = FakeClient()
    reader = FakeReader(
        posts={
            TECH.peer_id: [recent_post(TECH, 10, "A cheaper vision model shipped"), recent_post(TECH, 11, "Agent framework release")],
            MEMES.peer_id: [recent_post(MEMES, 5, "Monday mood")],
        },
        known={"technews": TECH, "memes": MEMES},
    )

    async def connect():
        return client

    monkeypatch.setattr(td, "connect", connect)
    monkeypatch.setattr(srv, "TelethonReader", lambda _client: reader)
    return client, reader


async def test_server_is_named_and_exposes_the_tools():
    assert srv.mcp.name == "summarix-telegram"
    names = {tool.name for tool in await srv.mcp.list_tools()}
    assert names == {
        "list_channels", "add_channels", "remove_channels", "list_styles",
        "fetch_posts", "search_posts", "find_channels", "read_part",
    }


async def test_no_session_tells_the_user_to_log_in_in_their_own_terminal(env, monkeypatch):
    async def no_session():
        return None

    monkeypatch.setattr(td, "connect", no_session)
    td.ChannelList([td.Entry(TECH.peer_id, TECH.title, TECH.username)]).save(td.LIST_FILE)
    for result in (await srv.fetch_posts(), await srv.find_channels(["ai"])):
        assert "own terminal" in result and "tgdigest.py login" in result


async def test_empty_list_asks_to_add_channels(env):
    assert "add channels" in await srv.fetch_posts()
    assert "list is empty" in (await srv.list_channels()).lower()


async def test_add_list_remove_channels(env):
    client, _ = env
    out = await srv.add_channels(["@technews", "t.me/memes", "not a link at all"])
    assert "added: Tech News" in out and "added: Memes" in out and "skipped" in out
    assert client.disconnected == 1
    assert (await srv.list_channels()).splitlines()[:2] == ["1. Tech News @technews", "2. Memes @memes"]
    assert "removed: Memes" in await srv.remove_channels(["2"])
    assert "Memes" not in await srv.list_channels()


async def test_fetch_posts_returns_marked_untrusted_posts_with_links_and_saves_the_part(env):
    await srv.add_channels(["@technews", "@memes"])
    out = await srv.fetch_posts(hours=24, style="tldr")
    assert out.startswith(srv.UNTRUSTED)
    assert "### [1]" in out and "https://t.me/technews/10" in out and "Monday mood" in out
    assert "STYLE:" in out and "Part 1 of 1" in out and "read_part" not in out
    assert (td.DATA / "mcp_posts_part1.md").exists()
    assert "Monday mood" in await srv.read_part("posts", 1)
    assert await srv.read_part("posts", 2) == "There are 1 parts."


async def test_big_issue_comes_in_parts_without_collecting_again(env, monkeypatch):
    monkeypatch.setattr(srv, "PART_CHARS", 10)  # every channel becomes its own part
    _, reader = env
    await srv.add_channels(["@technews", "@memes"])
    first = await srv.fetch_posts()
    assert "Part 1 of 2" in first and "read_part(kind='posts', part=2)" in first
    calls = len(reader.calls)
    second = await srv.read_part("posts", 2)
    assert "Part 2 of 2" in second and "Monday mood" in second
    assert len(reader.calls) == calls  # read_part never touches Telegram


async def test_quiet_window_and_bad_style(env):
    await srv.add_channels(["@technews"])
    assert "No posts in the last" in await srv.fetch_posts(hours=0)  # clamped to 1 h, posts are 1 h old
    assert "Unknown style" in await srv.fetch_posts(style="poem")


async def test_search_posts_finds_by_word_and_reads_nothing_else(env):
    await srv.add_channels(["@technews", "@memes"])
    out = await srv.search_posts(["vision"])
    assert out.startswith(srv.UNTRUSTED)
    assert "A cheaper vision model shipped" in out and "Monday mood" not in out
    assert "No posts with «quantum»" in await srv.search_posts(["quantum"])
    assert "at least one" in await srv.search_posts(["  "])


async def test_read_part_before_any_collection(env):
    assert "run fetch_posts first" in await srv.read_part("posts", 1)
    assert "kind is" in await srv.read_part("everything", 1)


async def test_stdout_stays_clean_for_the_protocol(env, capsys):
    """stdio is the protocol channel: a library that prints must not corrupt it."""
    _, reader = env
    original = reader.fetch_posts

    async def noisy_fetch(*args, **kwargs):
        print("library chatter")
        return await original(*args, **kwargs)

    reader.fetch_posts = noisy_fetch
    await srv.add_channels(["@technews"])
    await srv.fetch_posts()
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "library chatter" in captured.err


async def test_styles_are_listed_with_keys(env):
    out = await srv.list_styles()
    assert out.splitlines()[0].startswith("digest:") and len(out.splitlines()) == 13
