import sqlite3
from datetime import timedelta

import pytest

from scripts.tgdigest import ChannelList, Section, fetch_all, folder_from_bot_db, pack, render, sync_folders
from services.reader import ChannelInfo, Post, post_link
from tests.fakes import NOW, FakeReader, make_post

TECH = ChannelInfo(-1001, "Tech News", "technews")
PRIV = ChannelInfo(-1002, "Private notes", None)
MEMES = ChannelInfo(-1003, "Memes", "memes")


class PhotoReader(FakeReader):
    """FakeReader that keeps photo marks on posts and serves photo downloads."""

    def __init__(self, posts):
        super().__init__(posts)
        self.downloads: list[tuple[int, int]] = []

    async def fetch_posts(self, channel, *, after_id, since, limit, with_images):
        self.calls.append({"peer_id": channel.peer_id, "after_id": after_id, "since": since})
        if channel.peer_id in self.failing:
            raise RuntimeError("channel is private now")
        return [p for p in self.posts.get(channel.peer_id, []) if p.date >= since][:limit]

    async def download_photo(self, channel, message_id):
        self.downloads.append((channel.peer_id, message_id))
        return b"\xff\xd8jpeg"


def photo_post(channel, message_id, text="", hours_ago=1):
    return Post(message_id, NOW - timedelta(hours=hours_ago), text, post_link(channel, message_id),
                photo_message_id=message_id)


# ---------- channel list ----------

def test_folder_sync_adds_then_drops_channels_gone_from_folder_and_keeps_manual():
    lst = ChannelList()
    lst.add(PRIV)
    added, gone = lst.sync_folder("slug", "Промт", [TECH, MEMES])
    assert added == ["Tech News", "Memes"] and gone == []

    added, gone = lst.sync_folder("slug", "Промт", [TECH])
    assert added == [] and gone == ["Memes"]
    assert [c.title for c in lst.channels] == ["Private notes", "Tech News"]


def test_channel_removed_by_hand_stays_out_on_sync_until_added_back():
    lst = ChannelList()
    lst.sync_folder("slug", "Промт", [TECH, MEMES])
    lst.remove(lst.find("@memes"))
    lst.sync_folder("slug", "Промт", [TECH, MEMES])
    assert [c.title for c in lst.channels] == ["Tech News"]

    assert lst.add(MEMES)  # by hand: the exclusion is lifted
    assert [c.title for c in lst.channels] == ["Tech News", "Memes"]


def test_find_by_number_username_and_title_piece():
    lst = ChannelList()
    for c in (TECH, PRIV, MEMES):
        lst.add(c)
    assert lst.find("2").title == "Private notes"
    assert lst.find("@TechNews").title == "Tech News"
    assert lst.find("privat").title == "Private notes"
    with pytest.raises(KeyError):
        lst.find("9")
    with pytest.raises(KeyError):
        lst.find("e")  # matches several titles


def test_list_survives_save_and_load(tmp_path):
    path = tmp_path / "channels.json"
    lst = ChannelList()
    lst.sync_folder("slug", "Промт", [TECH, MEMES])
    lst.remove(lst.find("memes"))
    lst.save(path)

    loaded = ChannelList.load(path)
    assert loaded == lst
    assert ChannelList.load(tmp_path / "missing.json") == ChannelList()


def test_folder_channels_from_the_bot_database(tmp_path):
    db = tmp_path / "bot.db"
    con = sqlite3.connect(db)
    con.executescript(
        """
        CREATE TABLE channels (id INTEGER PRIMARY KEY, peer_id INTEGER, title TEXT, username TEXT);
        CREATE TABLE groups (id INTEGER PRIMARY KEY, kind TEXT, title TEXT, folder_slug TEXT);
        CREATE TABLE group_channels (group_id INTEGER, channel_id INTEGER);
        INSERT INTO channels VALUES (1, -1001, 'Tech News', 'technews'), (2, -1002, 'Private notes', NULL);
        INSERT INTO groups VALUES (1, 'manual', '', NULL), (2, 'folder', 'Промт', 'slug');
        INSERT INTO group_channels VALUES (1, 2), (2, 1);
        """
    )
    con.commit()
    con.close()

    assert folder_from_bot_db("slug", db) == ("Промт", [TECH])
    assert folder_from_bot_db("other", db) is None
    assert folder_from_bot_db("slug", tmp_path / "missing.db") is None


# ---------- fetching ----------

async def test_recap_reads_window_marks_nothing_keeps_order_and_reports_broken_channel(tmp_path):
    reader = PhotoReader({
        TECH.peer_id: [make_post(TECH, 5, "old", hours_ago=30), make_post(TECH, 6, "fresh news")],
        MEMES.peer_id: [make_post(MEMES, 9, "a meme")],
    })
    reader.failing.add(PRIV.peer_id)
    since = NOW - timedelta(hours=24)

    sections, errors = await fetch_all(reader, [MEMES, PRIV, TECH], since=since, images_dir=tmp_path)

    assert [s.channel.title for s in sections] == ["Memes", "Tech News"]
    assert [p.text for p in sections[1].posts] == ["fresh news"]
    assert all(call["after_id"] == 0 and call["since"] == since for call in reader.calls)
    assert errors == ["Private notes (channel is private now)"]


async def test_photos_only_where_the_picture_is_the_news_and_capped(tmp_path):
    reader = PhotoReader({
        TECH.peer_id: [
            photo_post(TECH, 1, ""),
            photo_post(TECH, 2, "A long caption that already tells the whole story in detail, the picture adds little"),
            photo_post(TECH, 3, "chart"),
            photo_post(TECH, 4, ""),
        ],
    })
    sections, _ = await fetch_all(
        reader, [TECH], since=NOW - timedelta(hours=24), image_budget=2, images_dir=tmp_path
    )

    assert reader.downloads == [(TECH.peer_id, 1), (TECH.peer_id, 3)]
    assert sorted(sections[0].images) == [1, 3]
    assert (tmp_path / "1001_1.jpg").read_bytes() == b"\xff\xd8jpeg"


def test_render_numbers_posts_links_them_and_lists_failures(tmp_path):
    long_text = "x" * 2500
    sections = [
        Section(TECH, [make_post(TECH, 6, "fresh news"), photo_post(TECH, 7, "")], {7: tmp_path / "1001_7.jpg"}),
        Section(PRIV, [make_post(PRIV, 3, long_text), photo_post(PRIV, 4, "")]),
    ]
    text = render(
        sections, ["Memes (gone)"], hours=24, now=NOW, total_channels=3, style_key="digest", style_text="Сухо."
    )

    assert "Каналов в списке: 3; с постами: 2; постов: 4" in text
    assert "## 1. Tech News · https://t.me/technews" in text
    assert "https://t.me/technews/6" in text and "### [2]" in text
    assert f"(картинка: {tmp_path / '1001_7.jpg'})" in text
    assert "## 2. Private notes\n" in text and "https://t.me/c/2/3" in text
    assert "x" * 2000 + "…" in text and "x" * 2001 not in text
    assert "(пост из одной картинки, не скачана)" in text
    assert "Не прочитались: Memes (gone)" in text
    assert "STYLE: Сухо." in text


def test_pack_keeps_channels_whole_and_starts_a_new_part_past_the_limit():
    blocks = ["a" * 60, "b" * 50, "c" * 30, "d" * 200]
    assert pack(blocks, limit=100) == [["a" * 60], ["b" * 50, "c" * 30], ["d" * 200]]
    assert pack(blocks, limit=1000) == [blocks]
    assert pack([], limit=100) == []


async def test_sync_folders_reports_changes_only_and_survives_an_unreadable_folder():
    lst = ChannelList()
    lst.sync_folder("slug", "Промт", [TECH, PRIV])
    reader = FakeReader(known={"technews": TECH, "memes": MEMES})  # the folder now: Tech News + Memes

    report = await sync_folders(reader, lst)
    assert report == ["папка «Test folder»: +1 -1", "  + Memes", "  - Private notes"]
    assert await sync_folders(reader, lst) == []  # nothing changed the second time

    class Broken(FakeReader):
        async def resolve_folder(self, slug, *, own=False):
            raise ConnectionError("network is down")

    before = [c.title for c in lst.channels]
    report = await sync_folders(Broken(), lst)
    assert report == ["папка «Test folder» не обновилась, беру сохранённый список: network is down"]
    assert [c.title for c in lst.channels] == before


def test_manual_channel_later_put_into_the_folder_follows_the_folder():
    lst = ChannelList()
    lst.sync_folder("slug", "Промт", [TECH])
    lst.add(MEMES)  # by hand first
    lst.sync_folder("slug", "Промт", [TECH, MEMES])  # then added to the folder in Telegram
    assert [c.source for c in lst.channels] == ["slug", "slug"]

    lst.sync_folder("slug", "Промт", [TECH])  # removed from the folder: gone from the digest too
    assert [c.title for c in lst.channels] == ["Tech News"]
