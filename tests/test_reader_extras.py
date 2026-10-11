from datetime import timedelta
from types import SimpleNamespace

import pytest
from telethon.errors import FloodWaitError

from telethon.tl.functions.chatlists import CheckChatlistInviteRequest
from telethon.tl.functions.messages import GetDialogFiltersRequest
from telethon.tl.types import (
    Channel,
    ChatPhotoEmpty,
    InputPeerChannel,
    InputPeerUser,
    MessageEntityBold,
    MessageEntityTextUrl,
    MessageEntityUrl,
)

from scripts.tgdigest import Section, render
from services.reader import ChannelInfo, ReaderError, TelethonReader, hidden_links
from tests.fakes import NOW, make_post

DEVSP = ChannelInfo(-1004, "Data Science", "devsp")


def message(*entities):
    """A Telethon-like message: entities plus the text each one covers."""
    return SimpleNamespace(entities=[e for e, _ in entities], get_entities_text=lambda: list(entities))


def test_hidden_links_kept_with_their_words_self_promo_and_plain_urls_dropped():
    post = message(
        (MessageEntityTextUrl(0, 3, "https://www.goojob.io/"), "тут "),
        (MessageEntityBold(4, 4), "жирный"),
        (MessageEntityUrl(9, 20), "https://visible.example"),  # already in the text
        (MessageEntityTextUrl(30, 8, "https://t.me/devsp"), "Telegram"),
        (MessageEntityTextUrl(40, 3, "https://max.ru/devsp/"), "Max"),
        (MessageEntityTextUrl(44, 5, "https://t.me/devsp/6000"), "пост"),
    )
    album_part = message((MessageEntityTextUrl(0, 3, "https://www.goojob.io/"), "сайт"))  # same url again

    assert hidden_links([post, album_part, SimpleNamespace(entities=None)], DEVSP) == [
        ("тут", "https://www.goojob.io/"),
        ("пост", "https://t.me/devsp/6000"),
    ]


def test_hidden_links_capped_per_post():
    many = message(*[(MessageEntityTextUrl(i, 1, f"https://e.example/{i}"), f"l{i}") for i in range(15)])
    assert len(hidden_links([many], DEVSP)) == 10


def test_render_lists_a_posts_hidden_links():
    post = make_post(DEVSP, 6018, "Разбор детектора")
    post.links = [("Хабр", "https://habr.com/ru/articles/1092636/")]
    text = render(
        [Section(DEVSP, [post])], [], hours=24, now=NOW, total_channels=1, style_key="digest", style_text="Сухо."
    )
    assert "Разбор детектора\nСсылки: «Хабр» https://habr.com/ru/articles/1092636/" in text


class FolderClient:
    """Answers the two requests resolve_folder makes and batched get_entity, like Telethon."""

    def __init__(self, filter_id, peers, entities, invite_chats=()):
        self.filter_id, self.peers, self.entities, self.invite_chats = filter_id, peers, entities, invite_chats

    async def __call__(self, request):
        if isinstance(request, CheckChatlistInviteRequest):
            return SimpleNamespace(filter_id=self.filter_id, chats=list(self.invite_chats), title=None)
        if isinstance(request, GetDialogFiltersRequest):
            folder = SimpleNamespace(id=4, title=SimpleNamespace(text="Промт"),
                                     pinned_peers=self.peers[:1], include_peers=self.peers)
            return SimpleNamespace(filters=[SimpleNamespace(id=1, title="Личные"), folder])
        raise AssertionError(f"unexpected request {request!r}")

    async def get_entity(self, peers):
        return [self.entities[id(p)] for p in peers]


async def test_own_folder_read_instead_of_a_stale_link_channels_only():
    holo, siolo, bot = InputPeerChannel(1019790455, 1), InputPeerChannel(1209999999, 2), InputPeerUser(8040201852, 3)
    chat = InputPeerChannel(1653098338, 4)
    entities = {
        id(holo): SimpleNamespace(broadcast=True, title="Голографика", username="holographica"),
        id(siolo): SimpleNamespace(broadcast=True, title="Сиолошная", username="seeallochnaya"),
        id(chat): SimpleNamespace(broadcast=False, megagroup=True, title="China Fairy Tale Chat"),
        id(bot): SimpleNamespace(first_name="Никита Велс"),
    }
    stale_link_chat = SimpleNamespace(broadcast=True, title="Removed long ago", username="gone", left=False, id=5)
    client = FolderClient(4, [holo, siolo, chat, bot], entities, invite_chats=[stale_link_chat])

    folder = await TelethonReader(client).resolve_folder("slug", own=True)

    assert folder.title == "Промт"
    assert folder.channels == [
        ChannelInfo(-1001019790455, "Голографика", "holographica"),
        ChannelInfo(-1001209999999, "Сиолошная", "seeallochnaya"),
    ]  # the pinned peer is listed once
    assert folder.skipped == ["China Fairy Tale Chat", "Никита Велс"]


async def test_folder_not_in_the_account_falls_back_to_the_link():
    link_chat = Channel(
        id=1001, title="Tech News", photo=ChatPhotoEmpty(), date=None, broadcast=True, username="technews", left=True
    )
    client = FolderClient(None, [], {}, invite_chats=[link_chat])
    folder = await TelethonReader(client).resolve_folder("slug", own=True)
    assert [c.title for c in folder.channels] == ["Tech News"]


class HistoryClient:
    """iter_messages like Telethon: newest first, or oldest first after min_id with reverse=True."""

    def __init__(self, messages, flood_first=0):
        self.messages = sorted(messages, key=lambda m: m.id)
        self.flood_left = flood_first
        self.calls = []

    async def get_input_entity(self, peer):
        return InputPeerChannel(1001, 1)

    async def iter_messages(self, entity, limit=None, min_id=0, reverse=False, offset_id=0, **kwargs):
        self.calls.append({"limit": limit, "min_id": min_id, "reverse": reverse})
        if self.flood_left:
            self.flood_left -= 1
            raise FloodWaitError(request=None, capture=0)
        picked = [m for m in self.messages if m.id > min_id and (not offset_id or m.id < offset_id)]
        picked = picked if reverse else picked[::-1]
        for message in picked[:limit]:
            yield message


def msg(id, text="", grouped=None, hours_ago=1.0):
    return SimpleNamespace(
        id=id, message=text, grouped_id=grouped, action=None, photo=None, entities=None,
        date=NOW - timedelta(hours=hours_ago),
    )


CHANNEL = ChannelInfo(-1001001, "Tech", "tech")


async def test_unread_is_read_oldest_first_and_an_album_cut_by_the_limit_is_read_to_its_end():
    client = HistoryClient([msg(1, "a"), msg(2, "b"), msg(3, "c"), msg(4, "album", grouped=9), msg(5, grouped=9),
                            msg(6, grouped=9), msg(7, "later")])
    reader = TelethonReader(client)

    posts = await reader.fetch_posts(CHANNEL, after_id=1, since=None, limit=4, with_images=False)
    assert client.calls[0] == {"limit": 4, "min_id": 1, "reverse": True}
    assert [(p.message_id, p.read_up_to) for p in posts] == [(2, 2), (3, 3), (4, 6)]  # 6 read past the limit
    assert posts.scanned_up_to == 6

    posts = await reader.fetch_posts(CHANNEL, after_id=6, since=None, limit=4, with_images=False)
    assert [p.message_id for p in posts] == [7]


async def test_an_album_bigger_than_the_limit_still_arrives_as_one_post_with_its_caption():
    client = HistoryClient([msg(2, "caption", grouped=5), msg(3, grouped=5), msg(4, grouped=5), msg(5, grouped=5),
                            msg(6, "next")])
    posts = await TelethonReader(client).fetch_posts(CHANNEL, after_id=1, since=None, limit=2)
    assert [(p.message_id, p.text, p.read_up_to) for p in posts] == [(2, "caption", 5)]


async def test_first_read_reaches_back_for_the_beginning_of_an_album_cut_by_the_limit():
    client = HistoryClient([msg(1, "caption", grouped=7), msg(2, grouped=7), msg(3, grouped=7), msg(4, "x"),
                            msg(5, "y")])
    posts = await TelethonReader(client).fetch_posts(CHANNEL, after_id=0, since=None, limit=3)
    assert [(p.message_id, p.text, p.read_up_to) for p in posts] == [(1, "caption", 3), (4, "x", 4), (5, "y", 5)]


async def test_since_is_ignored_for_unread_and_stickers_still_move_the_scan():
    sticker = msg(2)  # no text, no photo: read, but not a post
    client = HistoryClient([sticker, msg(3, "old post", hours_ago=100), msg(4, "fresh")])
    posts = await TelethonReader(client).fetch_posts(CHANNEL, after_id=1, since=NOW, limit=2)
    assert [p.message_id for p in posts] == [3] and posts.scanned_up_to == 3


async def test_first_read_is_newest_first_back_to_since_and_a_short_flood_wait_is_retried():
    channel = ChannelInfo(-1001001, "Tech", "tech")
    client = HistoryClient([msg(1, "old", hours_ago=30), msg(2, "fresh"), msg(3, "fresher")], flood_first=1)
    posts = await TelethonReader(client).fetch_posts(
        channel, after_id=0, since=NOW - timedelta(hours=24), limit=10, with_images=False
    )
    assert [p.message_id for p in posts] == [2, 3]
    assert len(client.calls) == 2 and client.calls[-1]["reverse"] is False


async def test_a_flood_wait_that_keeps_coming_becomes_a_reader_error():
    client = HistoryClient([msg(1, "a")], flood_first=10)
    with pytest.raises(ReaderError):
        await TelethonReader(client).fetch_posts(ChannelInfo(-1001001, "T", "t"), after_id=0, since=None, limit=5)
    assert len(client.calls) == 3  # first try + 2 retries
