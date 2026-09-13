"""
Building a digest: read new posts per channel -> caption images -> summarize -> compose.

Read marks move only after the digest was delivered (`commit`), so a crash or a failed
send never swallows posts.
"""
import asyncio
import html
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from bot.texts import t
from database.db import SessionMaker, get_channel, get_settings, list_channels
from database.models import DigestRun
from services.llm import LLM, WORDS_PLAIN, WORDS_STYLED, Usage
from services.reader import ChannelInfo, Post, Reader
from services.styles import DEFAULT_STYLE, language_name, style_prompt
from utils.text import link_refs, split_message

logger = logging.getLogger(__name__)


@dataclass
class DigestResult:
    messages: list[str]
    posts: int = 0
    channels_with_news: int = 0
    images: int = 0
    errors: list[str] = field(default_factory=list)
    read_marks: dict[int, int] = field(default_factory=dict)  # peer_id -> newest message id seen


@dataclass
class _Section:
    channel: ChannelInfo
    posts: list[Post]
    summary: str


class DigestService:
    def __init__(
        self,
        sessions: SessionMaker,
        reader: Reader,
        llm: LLM,
        *,
        lookback_hours: int = 24,
        max_posts_per_channel: int = 60,
        describe_images: bool = True,
        max_images_per_run: int = 20,
        ui_language: str = "ru",
        defaults: dict | None = None,
        concurrency: int = 6,
    ):
        self.concurrency = concurrency
        self.sessions = sessions
        self.reader = reader
        self.llm = llm
        self.lookback = timedelta(hours=lookback_hours)
        self.max_posts = max_posts_per_channel
        self.describe_images = describe_images
        self.max_images = max_images_per_run
        self.lang = ui_language
        # seed for the settings row; after that /settings is the source of truth
        self.defaults = defaults or {
            "style": DEFAULT_STYLE,
            "language": "ru",
            "ui_language": ui_language,
            "digest_time": "09:00",
            "timezone": "Europe/Moscow",
        }
        self.tz = ZoneInfo(self.defaults["timezone"])
        self.lock = asyncio.Lock()

    async def build(self, *, window_hours: int | None = None, now: datetime | None = None) -> DigestResult:
        """window_hours=None: unread posts (to be marked read). A number: a recap that marks nothing."""
        now = now or datetime.now(timezone.utc)
        self.llm.usage = Usage()  # per-run token count for the run log
        async with self.sessions() as db:
            channels = await list_channels(db)
            prefs = await get_settings(db, self.defaults)
        self.tz = ZoneInfo(prefs.timezone)
        self.lang = prefs.ui_language or self.lang
        self.llm.language = language_name(prefs.language)
        style = style_prompt(prefs.style, prefs.language, prefs.custom_prompt)
        plain = prefs.style == DEFAULT_STYLE and not prefs.custom_prompt
        words = WORDS_PLAIN if plain else WORDS_STYLED
        if not channels:
            return DigestResult(messages=[t(self.lang, "no_channels")])

        budget = {"images": self.max_images if self.describe_images else 0}
        result = DigestResult(messages=[])
        recap = window_hours is not None
        since = now - (timedelta(hours=window_hours) if recap else self.lookback)
        gate = asyncio.Semaphore(self.concurrency)

        async def process(index: int, channel) -> _Section | None:
            info = ChannelInfo(channel.peer_id, channel.title, channel.username)
            async with gate:
                try:
                    posts = await self.reader.fetch_posts(
                        info,
                        after_id=0 if recap else channel.last_message_id,
                        since=since,
                        limit=self.max_posts,
                        with_images=budget["images"] > 0,
                    )
                    if not posts:
                        return None
                    for post in posts:
                        for image in post.images:
                            if budget["images"] <= 0:
                                break
                            budget["images"] -= 1  # reserve before awaiting: other channels run concurrently
                            result.images += 1
                            post.image_descriptions.append(await self.llm.describe_image(image))
                        post.images.clear()
                    summary = await self.llm.summarize_channel(
                        channel.title, posts, style, words, None if plain else index
                    )
                except Exception as exc:  # one broken channel must not kill the whole digest
                    logger.warning("channel %s failed: %s", channel.title, exc)
                    result.errors.append(f"{channel.title} ({exc})")
                    return None
            return _Section(info, posts, summary)

        # gather keeps the channel order of the list, whatever finishes first
        sections = [s for s in await asyncio.gather(*(process(i, c) for i, c in enumerate(channels))) if s]
        for s in sections:
            result.posts += len(s.posts)
            if not recap:
                result.read_marks[s.channel.peer_id] = max(p.message_id for p in s.posts)

        result.channels_with_news = len(sections)
        highlights = ""
        if len(sections) >= 2:
            try:
                highlights = await self.llm.highlights([(s.channel.title, s.summary) for s in sections], style)
            except Exception as exc:
                logger.warning("highlights failed: %s", exc)

        result.messages = split_message(self._compose(sections, highlights, result, window_hours, now))
        return result

    async def commit(self, result: DigestResult, trigger: str) -> None:
        async with self.sessions() as db:
            for peer_id, message_id in result.read_marks.items():
                channel = await get_channel(db, peer_id)
                if channel and message_id > channel.last_message_id:
                    channel.last_message_id = message_id
            db.add(
                DigestRun(
                    trigger=trigger,
                    channels=result.channels_with_news,
                    posts=result.posts,
                    images=result.images,
                    input_tokens=self.llm.usage.input_tokens,
                    output_tokens=self.llm.usage.output_tokens,
                    errors="; ".join(result.errors) or None,
                )
            )
            await db.commit()

    def _compose(
        self, sections: list[_Section], highlights: str, result: DigestResult, window_hours: int | None, now: datetime
    ) -> str:
        date = now.astimezone(self.tz).strftime("%d.%m.%Y")
        title = (
            t(self.lang, "digest_window_title", hours=window_hours, date=date)
            if window_hours is not None
            else t(self.lang, "digest_title", date=date)
        )
        parts = [title]
        if not sections:
            parts.append(t(self.lang, "nothing_new"))
        else:
            parts.append(t(self.lang, "digest_stats", channels=len(sections), posts=result.posts))
            if highlights:
                parts += ["", t(self.lang, "highlights"), html.escape(highlights, quote=False)]
            for s in sections:
                name = html.escape(s.channel.title, quote=False)
                if s.channel.username:
                    name = f'<a href="https://t.me/{s.channel.username}">{name}</a>'
                parts += ["", f"➡️ <b>{name}</b>", link_refs(s.summary, s.posts)]
        if result.errors:
            parts += ["", t(self.lang, "failed_channels", items=html.escape(", ".join(result.errors), quote=False))]
        return "\n".join(parts)
