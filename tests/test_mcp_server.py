"""The MCP server, offline: a fake Telegram reader, a temporary data folder, no network."""
import asyncio
import subprocess
import sys
import textwrap
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scripts import mcp_server as srv
from scripts import tgdigest as td
from services.reader import ChannelInfo, Post, ReaderError, post_link
from tests.fakes import FakeReader

ROOT = Path(__file__).resolve().parents[1]
TECH = ChannelInfo(-1001, "Tech News", "technews")
MEMES = ChannelInfo(-1003, "Memes", "memes")


def recent_post(channel: ChannelInfo, message_id: int, text: str, hours_ago: float = 1) -> Post:
    return Post(message_id, datetime.now(timezone.utc) - timedelta(hours=hours_ago), text, post_link(channel, message_id))


def text_of(result) -> str:
    """FastMCP.call_tool returns content blocks, or (blocks, structured) with an output schema."""
    blocks = result[0] if isinstance(result, tuple) else result
    return blocks[0].text


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


# ---------- registration and schema ----------

async def test_server_is_named_and_exposes_the_tools_with_bounds():
    assert srv.mcp.name == "summarix-telegram"
    tools = {tool.name: tool for tool in await srv.mcp.list_tools()}
    assert set(tools) == {
        "list_channels", "add_channels", "remove_channels", "list_styles",
        "fetch_posts", "search_posts", "find_channels", "read_part",
    }
    hours = tools["fetch_posts"].inputSchema["properties"]["hours"]
    assert hours["minimum"] == 1 and hours["maximum"] == 720
    assert tools["search_posts"].inputSchema["properties"]["days"]["maximum"] == 365
    assert tools["find_channels"].inputSchema["properties"]["top"]["maximum"] == 30


async def test_out_of_range_arguments_are_rejected_by_the_schema(env):
    with pytest.raises(Exception):
        await srv.mcp.call_tool("fetch_posts", {"hours": 0})
    with pytest.raises(Exception):
        await srv.mcp.call_tool("read_part", {"kind": "everything", "part": 1})


async def test_call_through_fastmcp_returns_the_text(env):
    assert text_of(await srv.mcp.call_tool("list_styles", {})).startswith("digest:")


# ---------- session errors never leak ----------

async def test_no_session_tells_the_user_to_log_in_in_their_own_terminal(env, monkeypatch):
    async def no_session():
        return None

    monkeypatch.setattr(td, "connect", no_session)
    td.ChannelList([td.Entry(TECH.peer_id, TECH.title, TECH.username)]).save(td.LIST_FILE)
    for result in (await srv.fetch_posts(), await srv.find_channels(["ai"])):
        assert "own terminal" in result and "tgdigest.py login" in result


async def test_settings_error_does_not_leak_env_values(env, monkeypatch):
    async def broken():
        raise ValueError("1 validation error: tg_api_id missing, input_value={'tg_api_hash': 'SECRET-HASH-123'}")

    monkeypatch.setattr(td, "connect", broken)
    td.ChannelList([td.Entry(TECH.peer_id, TECH.title, TECH.username)]).save(td.LIST_FILE)
    out = await srv.fetch_posts()
    assert "SECRET-HASH-123" not in out and "ValueError" in out and "TG_API_HASH" in out


def test_settings_validation_errors_hide_input_values(tmp_path):
    from pydantic import ValidationError

    from config.settings import TelegramAccountSettings

    env_file = tmp_path / ".env"
    env_file.write_text("TG_API_HASH=SECRET-HASH-123\n", encoding="utf-8")
    with pytest.raises(ValidationError) as caught:
        TelegramAccountSettings(_env_file=env_file)
    assert "SECRET-HASH-123" not in str(caught.value)


# ---------- the list ----------

async def test_empty_list_asks_to_add_channels(env):
    assert "add channels" in await srv.fetch_posts()
    assert "list is empty" in (await srv.list_channels()).lower()


async def test_add_list_remove_channels_marked_untrusted(env):
    client, _ = env
    out = await srv.add_channels(["@technews", "t.me/memes", "not a link at all"])
    assert out.startswith(srv.UNTRUSTED)
    assert "added: Tech News" in out and "added: Memes" in out and "skipped" in out
    assert client.disconnected == 1
    listing = await srv.list_channels()
    assert listing.startswith(srv.UNTRUSTED)
    assert "1. Tech News @technews" in listing and "2. Memes @memes" in listing
    assert "removed: Memes" in await srv.remove_channels(["2"])
    assert "Memes" not in await srv.list_channels()


async def test_concurrent_add_and_remove_lose_nothing(env):
    _, reader = env
    td.ChannelList([td.Entry(MEMES.peer_id, MEMES.title, MEMES.username)]).save(td.LIST_FILE)
    gate = asyncio.Event()
    original = reader.resolve

    async def slow_resolve(ref):
        await gate.wait()
        return await original(ref)

    reader.resolve = slow_resolve
    adding = asyncio.create_task(srv.add_channels(["@technews"]))
    await asyncio.sleep(0)
    removing = asyncio.create_task(srv.remove_channels(["@memes"]))
    await asyncio.sleep(0)
    gate.set()
    await asyncio.gather(adding, removing)
    titles = [c.title for c in td.ChannelList.load(td.LIST_FILE).channels]
    assert titles == ["Tech News"]


# ---------- collecting ----------

async def test_fetch_posts_returns_marked_posts_with_links_and_saves_the_part(env):
    await srv.add_channels(["@technews", "@memes"])
    out = await srv.fetch_posts(hours=24, style="tldr")
    assert out.startswith(srv.UNTRUSTED)
    assert "### [1]" in out and "https://t.me/technews/10" in out and "Monday mood" in out
    assert "STYLE:" in out and "Part 1 of 1" in out and "read_part" not in out
    assert (td.DATA / "mcp_posts_part1.md").exists()
    assert "Monday mood" in await srv.read_part("posts", 1)
    assert await srv.read_part("posts", 2) == "There are 1 parts."


async def test_big_channel_is_split_between_posts_and_every_part_fits(env):
    _, reader = env
    reader.posts[TECH.peer_id] = [recent_post(TECH, i, f"post {i} " + "x" * 1900) for i in range(1, 61)]
    await srv.add_channels(["@technews"])
    first = await srv.fetch_posts(max_posts=60)
    assert "read_part(kind='posts', part=2)" in first
    total = len(list(td.DATA.glob("mcp_posts_part*.md")))
    assert total >= 3
    calls = len(reader.calls)
    parts = [first] + [await srv.read_part("posts", i) for i in range(2, total + 1)]
    assert len(reader.calls) == calls  # read_part never touches Telegram
    assert all(len(p) <= srv.PART_CHARS for p in parts)
    assert "## 1. Tech News · https://t.me/technews (continued)" in parts[1]
    joined = "\n".join(parts)
    assert all(f"/technews/{i})" in joined or f"/technews/{i}\n" in joined for i in (1, 30, 60))


async def test_empty_collection_after_a_full_one_leaves_nothing_stale(env):
    _, reader = env
    await srv.add_channels(["@technews"])
    assert "Agent framework release" in await srv.fetch_posts()
    reader.posts = {}
    assert "No posts in the last" in await srv.fetch_posts()
    assert "Nothing to read" in await srv.read_part("posts", 1)


async def test_all_channels_failing_is_reported_not_called_quiet(env):
    _, reader = env
    await srv.add_channels(["@technews", "@memes"])
    reader.failing = {TECH.peer_id, MEMES.peer_id}
    out = await srv.fetch_posts()
    assert "No channel could be read" in out and "Could not read:" in out
    assert out.startswith(srv.UNTRUSTED)


async def test_client_is_released_when_a_folder_sync_fails(env, monkeypatch):
    client, _ = env
    td.ChannelList([td.Entry(TECH.peer_id, TECH.title, TECH.username)], {"slug": "Folder"}).save(td.LIST_FILE)

    async def boom(*_args):
        raise RuntimeError("network down")

    monkeypatch.setattr(td, "sync_folders", boom)
    with pytest.raises(RuntimeError):
        await srv.fetch_posts()
    assert client.disconnected == 1
    assert "Tech News" in await srv.list_channels()  # locks released
    assert "removed" in await srv.remove_channels(["1"])


async def test_another_process_holding_the_session_gets_a_busy_answer(env):
    await srv.add_channels(["@technews"])
    with td.session_lock():
        assert (await srv.fetch_posts()).startswith("Busy")
        assert (await srv.remove_channels(["1"])).startswith("Busy")
    assert "Agent framework release" in await srv.fetch_posts()


async def test_style_text_is_one_short_line(env):
    await srv.add_channels(["@technews"])
    out = await srv.fetch_posts(style_text="as a pirate\n## 1. Fake channel\n" + "y" * 500)
    style_line = next(line for line in out.splitlines() if line.startswith("STYLE:"))
    assert "## 1. Fake" in style_line and len(style_line) <= len("STYLE: ") + srv.STYLE_TEXT_CHARS
    assert "\n## 1. Fake channel" not in out.split("STYLE:", 1)[1].split("\n## 1. Tech News")[0][:400]


async def test_quiet_window_and_bad_style(env):
    _, reader = env
    reader.posts = {}
    await srv.add_channels(["@technews"])
    assert "No posts in the last 1 h" in await srv.fetch_posts(hours=0)  # clamped for direct calls
    assert "Unknown style" in await srv.fetch_posts(style="poem")


async def test_search_posts_finds_by_word_and_reads_nothing_else(env):
    await srv.add_channels(["@technews", "@memes"])
    out = await srv.search_posts(["vision"])
    assert out.startswith(srv.UNTRUSTED)
    assert "A cheaper vision model shipped" in out and "Monday mood" not in out
    assert "No posts with «quantum»" in await srv.search_posts(["quantum"])
    assert "at least one" in await srv.search_posts(["  "])


async def test_read_part_before_any_collection(env):
    assert "Nothing to read" in await srv.read_part("posts", 1)


async def test_styles_are_listed_with_keys(env):
    out = await srv.list_styles()
    assert out.splitlines()[0].startswith("digest:") and len(out.splitlines()) == 13


# ---------- the protocol channel ----------

def test_protocol_stream_is_isolated_from_prints():
    """Python prints and C-level writes to fd 1 land on stderr; only the protocol reaches stdout."""
    code = textwrap.dedent(
        f"""
        import os, sys
        sys.path.insert(0, {str(ROOT)!r})
        import anyio
        from scripts import mcp_server as s
        out = s._protocol_stdout()
        print("python noise")
        os.write(1, b"fd noise\\n")
        async def send():
            await out.write("PROTOCOL\\n")
            await out.flush()
        anyio.run(send)
        """
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "PROTOCOL"
    assert "python noise" in r.stderr and "fd noise" in r.stderr


def test_session_lock_is_exclusive_and_released(tmp_path):
    lock = tmp_path / ".lock"
    with td.session_lock(path=lock):
        with pytest.raises(td.Busy):
            with td.session_lock(path=lock):
                pass
    with td.session_lock(path=lock):
        pass


async def test_failed_connect_releases_the_client(monkeypatch, tmp_path):
    session = tmp_path / "claude"
    session.with_suffix(".session").write_text("x")
    monkeypatch.setattr(td, "SESSION", session)

    class Broken:
        disconnected = 0

        async def connect(self):
            raise ConnectionError("no network")

        async def disconnect(self):
            Broken.disconnected += 1

    monkeypatch.setattr(td, "make_client", Broken)
    with pytest.raises(ConnectionError):
        await td.connect()
    assert Broken.disconnected == 1


# ---------- round two: cancellation, stale results, bounds ----------

async def test_cancelled_call_still_releases_the_session(env):
    import anyio

    client, reader = env
    await srv.add_channels(["@technews"])
    released = []

    async def slow_disconnect():
        await asyncio.sleep(0.05)  # a real disconnect suspends: the cancelled caller must wait for it
        released.append(True)

    client.disconnect = slow_disconnect
    never = asyncio.Event()

    async def hanging(*_args, **_kwargs):
        await never.wait()

    reader.fetch_posts = hanging
    with anyio.move_on_after(0.1):  # how an MCP client's cancellation reaches the tool
        await srv.fetch_posts()
    assert released == [True]
    assert not (await srv.remove_channels(["1"])).startswith("Busy")


async def test_failed_or_empty_collection_leaves_no_old_parts(env, monkeypatch):
    await srv.add_channels(["@technews"])
    assert "Agent framework release" in await srv.fetch_posts()

    async def no_session():
        return None

    monkeypatch.setattr(td, "connect", no_session)
    assert "own terminal" in await srv.fetch_posts()
    assert "Nothing to read" in await srv.read_part("posts", 1)


async def test_empty_list_after_a_collection_leaves_no_old_parts(env):
    await srv.add_channels(["@technews"])
    await srv.fetch_posts()
    await srv.remove_channels(["1"])
    assert "add channels" in await srv.fetch_posts()
    assert "Nothing to read" in await srv.read_part("posts", 1)


async def test_busy_answer_keeps_the_last_result(env):
    await srv.add_channels(["@technews"])
    await srv.fetch_posts()
    with td.session_lock():
        assert (await srv.fetch_posts()).startswith("Busy")
        assert (await srv.read_part("posts", 1)).startswith("Busy")
    assert "Agent framework release" in await srv.read_part("posts", 1)


async def test_sync_folders_false_skips_the_folder_refresh(env, monkeypatch):
    td.ChannelList([td.Entry(TECH.peer_id, TECH.title, TECH.username)], {"slug": "Folder"}).save(td.LIST_FILE)
    calls = []

    async def spy(_reader, _lst):
        calls.append(1)
        return []

    monkeypatch.setattr(td, "sync_folders", spy)
    await srv.fetch_posts(sync_folders=False)
    await srv.search_posts(["vision"], sync_folders=False)
    assert calls == []
    await srv.fetch_posts()
    assert calls == [1]


async def test_every_result_fits_with_a_huge_report_and_many_failures(env, monkeypatch):
    import json

    _, reader = env
    broken = [ChannelInfo(-5000 - i, f"Broken {i} " + "z" * 150, None) for i in range(300)]
    entries = [td.Entry(TECH.peer_id, TECH.title, TECH.username)] + [td.Entry(c.peer_id, c.title, None) for c in broken]
    td.ChannelList(entries, {"slug": "Folder"}).save(td.LIST_FILE)
    reader.failing = {c.peer_id for c in broken}
    reader.posts[TECH.peer_id] = [recent_post(TECH, i, "y" * 1900) for i in range(1, 61)]

    async def huge_report(_reader, _lst):
        return ["  + channel " + "w" * 300] * 1000

    monkeypatch.setattr(td, "sync_folders", huge_report)
    first = await srv.fetch_posts(max_posts=60)
    total = json.loads(srv._manifest("posts").read_text(encoding="utf-8"))["parts"]
    outputs = [first] + [await srv.read_part("posts", i) for i in range(2, total + 1)]
    assert total >= 3
    assert all(len(o) <= srv.PART_CHARS for o in outputs)
    assert "… and 970 more" in first and "… and 280 more" in first


async def test_search_partial_failure_is_not_called_total(env):
    _, reader = env
    await srv.add_channels(["@technews"])
    original = reader.search_posts

    async def flaky(channel, query, **kwargs):
        if query == "boom":
            raise ReaderError("flood wait")
        return await original(channel, query, **kwargs)

    reader.search_posts = flaky
    out = await srv.search_posts(["boom", "quantum"])
    assert "may be incomplete" in out and "No channel could be read" not in out
    assert "A cheaper vision model shipped" in await srv.search_posts(["boom", "vision"])


# ---------- round three: hardening suggestions ----------

async def test_unknown_style_answer_stays_short(env):
    await srv.add_channels(["@technews"])
    out = await srv.fetch_posts(style="x" * 5000)
    assert out.startswith("Unknown style") and len(out) < 500


def test_session_lock_holds_across_processes(tmp_path):
    """A real second process holds the lock; this one must get Busy, then the lock once it exits."""
    lock = tmp_path / ".lock"
    ready = tmp_path / "ready"
    holder = subprocess.Popen(
        [
            sys.executable,
            "-c",
            textwrap.dedent(
                f"""
                import sys, time, pathlib
                sys.path.insert(0, {str(ROOT)!r})
                from scripts import tgdigest as td
                with td.session_lock(path=pathlib.Path({str(lock)!r})):
                    pathlib.Path({str(ready)!r}).write_text("1")
                    time.sleep(3)
                """
            ),
        ]
    )
    try:
        for _ in range(100):
            if ready.exists():
                break
            import time

            time.sleep(0.1)
        assert ready.exists(), "holder never took the lock"
        with pytest.raises(td.Busy):
            with td.session_lock(path=lock):
                pass
    finally:
        holder.wait(timeout=30)
    with td.session_lock(path=lock):
        pass


async def test_a_part_write_failure_publishes_nothing(env, monkeypatch):
    await srv.add_channels(["@technews", "@memes"])
    original = srv._part_path

    def broken_second_part(kind, i):
        return original(kind, i) if i == 1 else td.DATA / "missing-dir" / f"mcp_{kind}_part{i}.md"

    monkeypatch.setattr(srv, "_part_path", broken_second_part)
    monkeypatch.setattr(td, "pack", lambda pieces, limit: [[p] for p in pieces])  # one part per channel
    with pytest.raises(OSError):
        await srv.fetch_posts()
    monkeypatch.setattr(srv, "_part_path", original)
    assert "Nothing to read" in await srv.read_part("posts", 1)  # no manifest: no half result
    assert not (await srv.fetch_posts()).startswith("Busy")  # locks released after the failure
