"""Offline stand-ins: no Telegram, no model API, no money."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from services.llm import LLM
from services.reader import ChannelInfo, Folder, Post, ReaderError, post_link
from services.refs import ChannelRef

NOW = datetime(2026, 9, 13, 6, 0, tzinfo=timezone.utc)


def make_post(
    channel: ChannelInfo, message_id: int, text: str, hours_ago: float = 1, images: int = 0, album: int = 1
) -> Post:
    """album > 1: the post is an album of that many messages, ids message_id .. message_id + album - 1."""
    return Post(
        message_id=message_id,
        date=NOW - timedelta(hours=hours_ago),
        text=text,
        link=post_link(channel, message_id),
        images=[b"\xff\xd8fake-jpeg"] * images,
        photo_message_id=message_id if images else None,
        last_id=message_id + album - 1 if album > 1 else None,
    )


class FakeReader:
    """Serves a fixed set of posts per channel in Telegram's order: unread (after_id > 0) oldest
    first from the mark, a first read or recap newest first back to `since`."""

    def __init__(self, posts: dict[int, list[Post]] | None = None, known: dict[str, ChannelInfo] | None = None):
        self.posts = posts or {}
        self.known = known or {}
        self.failing: set[int] = set()
        self.calls: list[dict] = []
        self.directory: list[tuple[ChannelInfo, int | None]] = []  # what a channel search can find
        self.downloads: list[tuple[int, int]] = []

    async def resolve(self, ref: ChannelRef) -> ChannelInfo:
        if ref.value in self.known:
            return self.known[ref.value]
        raise ReaderError("not found")

    async def resolve_folder(self, slug: str, *, own: bool = False) -> Folder:
        return Folder("Test folder", list(self.known.values()), ["Closed club"])

    async def fetch_posts(self, channel, *, after_id, since, limit, with_images=False):
        self.calls.append(
            {"peer_id": channel.peer_id, "after_id": after_id, "since": since, "with_images": with_images}
        )
        if channel.peer_id in self.failing:
            raise ReaderError("channel is private now")
        posts = sorted(self.posts.get(channel.peer_id, []), key=lambda p: p.message_id)
        fresh = [p for p in posts if since is None or p.date >= since]
        if after_id:
            selected = [p for p in fresh if p.message_id > after_id][:limit]
        else:
            selected = fresh[-limit:]
        return [replace(p, images=list(p.images) if with_images else [], image_descriptions=[]) for p in selected]

    async def download_photo(self, channel, message_id):
        self.downloads.append((channel.peer_id, message_id))
        post = next((p for p in self.posts.get(channel.peer_id, []) if p.photo_message_id == message_id), None)
        return post.images[0] if post and post.images else None

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
