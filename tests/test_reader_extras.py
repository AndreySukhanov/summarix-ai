from types import SimpleNamespace

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
from services.reader import ChannelInfo, TelethonReader, hidden_links
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
