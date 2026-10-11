"""Offline stand-ins: no Telegram, no model API, no money."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from services.llm import LLM
from services.reader import ChannelInfo, Folder, Post, ReaderError, post_link
from services.refs import ChannelRef

NOW = datetime(2026, 9, 13, 6, 0, tzinfo=timezone.utc)


def make_post(channel: ChannelInfo, message_id: int, text: str, hours_ago: float = 1, images: int = 0) -> Post:
    return Post(
        message_id=message_id,
        date=NOW - timedelta(hours=hours_ago),
        text=text,
        link=post_link(channel, message_id),
        images=[b"\xff\xd8fake-jpeg"] * images,
    )


class FakeReader:
    """Serves a fixed set of posts per channel and honours after_id / since like Telethon would."""

    def __init__(self, posts: dict[int, list[Post]] | None = None, known: dict[str, ChannelInfo] | None = None):
        self.posts = posts or {}
        self.known = known or {}
        self.failing: set[int] = set()
        self.calls: list[dict] = []
        self.directory: list[tuple[ChannelInfo, int | None]] = []  # what a channel search can find

    async def resolve(self, ref: ChannelRef) -> ChannelInfo:
        if ref.value in self.known:
            return self.known[ref.value]
        raise ReaderError("not found")

    async def resolve_folder(self, slug: str, *, own: bool = False) -> Folder:
        return Folder("Test folder", list(self.known.values()), ["Closed club"])

    async def fetch_posts(self, channel, *, after_id, since, limit, with_images):
        self.calls.append({"peer_id": channel.peer_id, "after_id": after_id, "since": since, "with_images": with_images})
        if channel.peer_id in self.failing:
            raise ReaderError("channel is private now")
        selected = [p for p in self.posts.get(channel.peer_id, []) if p.message_id > after_id and p.date >= since]
        out = []
        for p in selected[:limit]:
            out.append(Post(p.message_id, p.date, p.text, p.link, list(p.images) if with_images else []))
        return out

    async def search_posts(self, channel, query, *, since, limit):
        """Like Telegram: plain substring match, newest first."""
        self.calls.append({"peer_id": channel.peer_id, "query": query, "since": since})
        if channel.peer_id in self.failing:
            raise ReaderError("channel is private now")
        hits = [p for p in self.posts.get(channel.peer_id, []) if query.lower() in p.text.lower() and p.date >= since]
        return sorted(hits, key=lambda p: p.message_id, reverse=True)[:limit]

    async def search_channels(self, query, limit=20):
        return [(info, subs) for info, subs in self.directory if query.lower() in info.title.lower()][:limit]


class _Completions:
    def __init__(self, replies):
        self.replies = replies
        self.requests: list[dict] = []

    async def create(self, **kwargs):
        self.requests.append(kwargs)
        content = self.replies(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
            usage=SimpleNamespace(prompt_tokens=100, completion_tokens=20),
        )


class FakeClient:
    def __init__(self, replies=None):
        self.chat = SimpleNamespace(completions=_Completions(replies or default_reply))

    @property
    def requests(self) -> list[dict]:
        return self.chat.completions.requests


def default_reply(kwargs) -> str:
    messages = kwargs["messages"]
    content = messages[-1]["content"]
    if isinstance(content, list):
        return "A chart with revenue up 20%"
    if "most important items" in content:
        return "• Big news (Tech)"
    return "• Summary of the posts [1][2]"


def fake_llm(replies=None) -> tuple[LLM, FakeClient]:
    client = FakeClient(replies)
    return LLM(client, "test-model", language="English"), client
