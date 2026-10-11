import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from services.reader import ChannelInfo, group_messages, post_link
from services.refs import ChannelRef, RefError, parse_channel_ref
from services.scheduler import next_run_at, run_daily
from tests.fakes import NOW, make_post
from utils.text import link_refs, split_message


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("@Durov", ChannelRef("username", "durov")),
        ("durov", ChannelRef("username", "durov")),
        ("https://t.me/durov", ChannelRef("username", "durov")),
        ("t.me/s/durov", ChannelRef("username", "durov")),
        ("https://t.me/durov/123?single", ChannelRef("username", "durov")),
        ("https://t.me/+AbCdEf123", ChannelRef("invite", "AbCdEf123")),
        ("t.me/joinchat/AbCdEf123", ChannelRef("invite", "AbCdEf123")),
        ("https://t.me/c/1234567890/55", ChannelRef("id", "-1001234567890")),
        ("-1001234567890", ChannelRef("id", "-1001234567890")),
        ("https://t.me/addlist/Xy9_AbC", ChannelRef("folder", "Xy9_AbC")),
    ],
)
def test_parse_channel_ref(raw, expected):
    assert parse_channel_ref(raw) == expected


@pytest.mark.parametrize("raw", ["", "a b", "https://example.com/durov", "@ab", "t.me/"])
def test_parse_channel_ref_rejects_garbage(raw):
    with pytest.raises(RefError):
        parse_channel_ref(raw)


def test_post_links_public_and_private():
    assert post_link(ChannelInfo(-1001, "x", "news"), 7) == "https://t.me/news/7"
    assert post_link(ChannelInfo(-1001234567890, "x", None), 7) == "https://t.me/c/1234567890/7"


def test_group_messages_merges_albums_and_drops_service_messages():
    m = lambda id, grouped=None, action=None: SimpleNamespace(id=id, grouped_id=grouped, action=action)  # noqa: E731
    groups = group_messages([m(5), m(3, grouped=9), m(4, grouped=9), m(2, action="pin"), m(1)])
    assert [[x.id for x in g] for g in groups] == [[1], [3, 4], [5]]


def test_link_refs_escapes_model_text_and_links_only_real_posts():
    channel = ChannelInfo(-1001, "x", "news")
    posts = [make_post(channel, 10, "a"), make_post(channel, 11, "b")]
    out = link_refs("• <b>Price</b> up & more [1][2] [7]\n• Other [2, 1]", posts)
    assert "&lt;b&gt;Price&lt;/b&gt; up &amp; more" in out
    assert '(<a href="https://t.me/news/10">1</a>, <a href="https://t.me/news/11">2</a>)' in out
    assert "[7]" not in out
    assert out.endswith("• Other")  # both posts were already linked above: no repeated citation


def test_split_message_never_orphans_a_channel_title():
    sections = []
    for i in range(12):
        sections.append(f"➡️ <b>Channel {i}</b>\n" + ("word " * 60).strip() + f"\n\nsecond paragraph {i}")
    chunks = split_message("<b>Digest</b>\n\n" + "\n\n".join(sections), limit=900)
    assert all(len(c) <= 900 for c in chunks)
    for chunk in chunks:
        assert not chunk.rstrip().endswith("</b>")  # a title always travels with its text
        assert not chunk.startswith("\n") and not chunk.endswith("\n")
    joined = "\n\n".join(chunks)
    assert all(f"Channel {i}" in joined and f"second paragraph {i}" in joined for i in range(12))


def test_link_refs_collapses_blank_lines():
    channel = ChannelInfo(-1001, "x", "news")
    out = link_refs("\n\nFirst [1]\n\n \n\nSecond\n", [make_post(channel, 10, "a")])
    assert out == 'First (<a href="https://t.me/news/10">1</a>)\n\nSecond'


def test_split_message_respects_limit_and_keeps_lines_whole():
    lines = [f'• item {i} <a href="https://t.me/x/{i}">{i}</a>' for i in range(300)]
    chunks = split_message("\n".join(lines), limit=500)
    assert all(len(c) <= 500 for c in chunks)
    assert "\n".join(chunks).split("\n") == lines
    assert split_message("x" * 1200, limit=500) == ["x" * 500, "x" * 500, "x" * 200]


def test_split_never_cuts_inside_a_tag_or_an_open_element():
    link = '<a href="https://t.me/news/1">1</a>'
    line = "word " * 95 + "end " + link + " " + "<b>a long bold title here</b> tail"
    for limit in range(480, 540, 3):  # cut points that would land inside the link or the bold title
        chunks = split_message(line, limit=limit)
        for chunk in chunks:
            assert len(chunk) <= limit
            assert chunk.count("<a ") == chunk.count("</a>") and chunk.count("<b>") == chunk.count("</b>")
            assert not chunk.endswith("<a") and not chunk.startswith("href")
        assert " ".join(chunks).split() == line.split()  # nothing lost


def test_split_closes_and_reopens_an_element_longer_than_the_limit_and_keeps_entities_whole():
    failures = ", ".join(f"Channel {i} (Request was unsuccessful)" for i in range(120))
    long_italic = f"<i>Could not read: {failures}</i>"
    chunks = split_message(long_italic, limit=1000)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 1000
        assert chunk.startswith("<i>") and chunk.endswith("</i>")  # every part is a whole <i> element
    assert "".join(c[3:-4] for c in chunks).replace(" ", "") == long_italic[3:-4].replace(" ", "")

    entity = split_message("x" * 4094 + "&amp;tail", limit=4096)
    assert entity == ["x" * 4094, "&amp;tail"]

    assert "".join(split_message("<b>x</b>", limit=7)) == "<b>x</b>"  # a limit smaller than the tags: still ends


async def test_scheduler_survives_a_failing_settings_read():
    calls = []

    async def schedule():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("database is locked")
        return "09:00", "UTC"

    async def job():
        raise AssertionError("not due yet")

    task = asyncio.create_task(run_daily(job, schedule, asyncio.Event(), retry_s=0.01))
    await asyncio.sleep(0.1)
    assert len(calls) == 2 and not task.done()  # retried, and still waiting for 09:00
    task.cancel()


def test_next_run_at_today_and_tomorrow_in_local_time():
    # 06:00 UTC = 09:00 Moscow
    assert next_run_at(datetime(2026, 9, 13, 5, 0, tzinfo=timezone.utc), "09:00", "Europe/Moscow") == datetime(
        2026, 9, 13, 6, 0, tzinfo=timezone.utc
    )
    assert next_run_at(NOW, "09:00", "Europe/Moscow") == datetime(2026, 9, 14, 6, 0, tzinfo=timezone.utc)
