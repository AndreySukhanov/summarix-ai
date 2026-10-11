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
from database.db import SessionMaker, get_channel, get_group, get_settings, group_channels, list_channels
from database.models import DigestRun, Group
from services.llm import LLM, WORDS_PLAIN, WORDS_STYLED, Usage
from services.reader import ChannelInfo, Post, Reader
from services.styles import DEFAULT_STYLE, language_name, style_prompt
from utils.text import link_refs, one_line, split_message

logger = logging.getLogger(__name__)


def group_display_title(group: Group, lang: str) -> str:
    return t(lang, "group_manual") if group.kind == "manual" else f"📁 {group.title}"


@dataclass
class DigestResult:
    messages: list[str]
    posts: int = 0
    channels_with_news: int = 0
    images: int = 0
    errors: list[str] = field(default_factory=list)
    read_marks: dict[int, int] = field(default_factory=dict)  # peer_id -> newest message id seen
    group_id: int | None = None
    usage: Usage = field(default_factory=Usage)  # tokens of this build, logged on commit


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

    def new_budget(self) -> dict:
        """Image captions allowed in one run; shared by every group of the run."""
        return {"images": self.max_images if self.describe_images else 0}

    async def build(
        self,
        *,
        window_hours: int | None = None,
        now: datetime | None = None,
        group_id: int | None = None,
        budget: dict | None = None,
    ) -> DigestResult:
        """window_hours=None: unread posts (to be marked read). A number: a recap that marks nothing.
        group_id: only that group's channels, with the group name under the title; None: every channel.
        budget: image captions left for the run (see new_budget); a fresh one when not given."""
        now = now or datetime.now(timezone.utc)
        self.llm.usage = Usage()  # per-build token count, kept in the result for the run log
        async with self.sessions() as db:
            prefs = await get_settings(db, self.defaults)
            group = await get_group(db, group_id) if group_id is not None else None
            channels = await group_channels(db, group_id) if group_id is not None else await list_channels(db)
        self.tz = ZoneInfo(prefs.timezone)
        self.lang = prefs.ui_language or self.lang
        group_title = group_display_title(group, self.lang) if group else None
        self.llm.language = language_name(prefs.language)
        style = style_prompt(prefs.style, prefs.language, prefs.custom_prompt)
        plain = prefs.style == DEFAULT_STYLE and not prefs.custom_prompt
        words = WORDS_PLAIN if plain else WORDS_STYLED
        if not channels:
            return DigestResult(messages=[t(self.lang, "no_channels")], group_id=group_id)

        budget = budget if budget is not None else self.new_budget()
        result = DigestResult(messages=[], group_id=group_id, usage=self.llm.usage)
        recap = window_hours is not None
        gate = asyncio.Semaphore(self.concurrency)
        scanned: dict[int, int] = {}  # peer_id -> last message read, posts or not

        async def process(index: int, channel) -> _Section | None:
            info = ChannelInfo(channel.peer_id, channel.title, channel.username)
            unread_after = 0 if recap else channel.last_message_id
            if recap:
                since = now - timedelta(hours=window_hours)
            else:  # the lookback only bounds a channel's first read; after that nothing unread is skipped
                since = now - self.lookback if not unread_after else None
            async with gate:
                try:
                    posts = await self.reader.fetch_posts(
                        info, after_id=unread_after, since=since, limit=self.max_posts, with_images=False
                    )
                    scanned[info.peer_id] = getattr(posts, "scanned_up_to", 0)
                    if not posts:
                        return None
                    for post in posts:
                        if post.photo_message_id is None or budget["images"] <= 0:
                            continue
                        budget["images"] -= 1  # reserve before awaiting: other channels run concurrently
                        try:
                            image = await self.reader.download_photo(info, post.photo_message_id)
                            if image:
                                post.image_descriptions.append(await self.llm.describe_image(image))
                                result.images += 1
                        except Exception as exc:
                            if not post.text:  # the picture IS the post: retelling nothing would lose it
                                raise
                            logger.warning("image of %s failed: %s", post.link, exc)  # the text carries it
                    summary = await self.llm.summarize_channel(
                        channel.title, posts, style, words, None if plain else index
                    )
                    if not summary.strip():  # an empty answer must not mark the posts read
                        raise ValueError("the model returned an empty retelling")
                except Exception as exc:  # one broken channel must not kill the whole digest
                    logger.warning("channel %s failed: %s", channel.title, exc)
                    result.errors.append(f"{channel.title} ({one_line(exc)})")
                    scanned.pop(info.peer_id, None)  # nothing of a failed channel counts as read
                    return None
            return _Section(info, posts, summary)

        # gather keeps the channel order of the list, whatever finishes first
        sections = [s for s in await asyncio.gather(*(process(i, c) for i, c in enumerate(channels))) if s]
        for s in sections:
            result.posts += len(s.posts)
            if not recap:
                result.read_marks[s.channel.peer_id] = max(p.read_up_to for p in s.posts)
        if not recap:  # channels that only had stickers or polls move on too (failed ones are not in `scanned`)
            for peer_id, last in scanned.items():
                if last > result.read_marks.get(peer_id, 0):
                    result.read_marks[peer_id] = last

        result.channels_with_news = len(sections)
        highlights = ""
        if len(sections) >= 2:
            try:
                highlights = await self.llm.highlights([(s.channel.title, s.summary) for s in sections], style)
            except Exception as exc:
                logger.warning("highlights failed: %s", exc)

        result.messages = split_message(self._compose(sections, highlights, result, window_hours, now, group_title))
        return result

    async def commit(self, result: DigestResult, trigger: str, log: bool = True) -> None:
        """Move the read marks; log=False for a digest that was not sent (only stickers moved marks)."""
        async with self.sessions() as db:
            for peer_id, message_id in result.read_marks.items():
                channel = await get_channel(db, peer_id)
                if channel and message_id > channel.last_message_id:
                    channel.last_message_id = message_id
            if not log:
                await db.commit()
                return
            db.add(
                DigestRun(
                    trigger=trigger,
                    channels=result.channels_with_news,
                    posts=result.posts,
                    images=result.images,
                    input_tokens=result.usage.input_tokens,
                    output_tokens=result.usage.output_tokens,
                    errors="; ".join(result.errors) or None,
                )
            )
            await db.commit()

    def _compose(
        self,
        sections: list[_Section],
        highlights: str,
        result: DigestResult,
        window_hours: int | None,
        now: datetime,
        group_title: str | None = None,
    ) -> str:
        date = now.astimezone(self.tz).strftime("%d.%m.%Y")
        title = (
            t(self.lang, "digest_window_title", hours=window_hours, date=date)
            if window_hours is not None
            else t(self.lang, "digest_title", date=date)
        )
        parts = [title]
        if group_title:
            parts.append(html.escape(group_title, quote=False))
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
