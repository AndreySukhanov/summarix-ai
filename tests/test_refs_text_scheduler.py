from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from services.reader import ChannelInfo, group_messages, post_link
from services.refs import ChannelRef, RefError, parse_channel_ref
from services.scheduler import next_run_at
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
    assert out.endswith('Other (<a href="https://t.me/news/11">2</a>, <a href="https://t.me/news/10">1</a>)')


def test_split_message_respects_limit_and_keeps_lines_whole():
    lines = [f'• item {i} <a href="https://t.me/x/{i}">{i}</a>' for i in range(300)]
    chunks = split_message("\n".join(lines), limit=500)
    assert all(len(c) <= 500 for c in chunks)
    assert "\n".join(chunks).split("\n") == lines
    assert split_message("x" * 1200, limit=500) == ["x" * 500, "x" * 500, "x" * 200]


def test_next_run_at_today_and_tomorrow_in_local_time():
    # 06:00 UTC = 09:00 Moscow
    assert next_run_at(datetime(2026, 9, 13, 5, 0, tzinfo=timezone.utc), "09:00", "Europe/Moscow") == datetime(
        2026, 9, 13, 6, 0, tzinfo=timezone.utc
    )
    assert next_run_at(NOW, "09:00", "Europe/Moscow") == datetime(2026, 9, 14, 6, 0, tzinfo=timezone.utc)
