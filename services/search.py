"""
Search: posts in your channels about a topic, and public channels about a topic.

Telegram searches whole words and knows nothing of inflections ("очки" does not find "очков"),
so a query is several terms - word forms, synonyms, English names - and hits are merged.
The bot gets the terms from the model; the Claude Code skill passes its own.
"""
import asyncio
import html
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from bot.texts import t
from database.db import SessionMaker, get_settings, list_channels
from services.llm import LLM, SEARCH_NONE
from services.reader import ChannelInfo, Post, ReaderError
from services.styles import language_name
from utils.text import link_refs, split_message

SEARCH_DAYS = 30
MAX_DAYS = 365
PER_CHANNEL = 20  # hits per channel and term; Telegram returns newest first
ACTIVE_DAYS = 30
SAMPLE_POSTS = 40  # recent posts read to judge a found channel
CHECK_CHANNELS = 25  # found channels worth reading; the rest is usually shops and namesakes
TOP_CHANNELS = 10
SAMPLE_CHARS = 200


def split_terms(text: str) -> list[str]:
    """'Rokid, умные очки; smart glasses' -> three terms, duplicates dropped."""
    return list(dict.fromkeys(term.strip() for term in re.split(r"[,;\n]", text) if term.strip()))


def parse_query(args: str | None, default_days: int = SEARCH_DAYS) -> tuple[str, int]:
    """'/search Rokid, умные очки 14' -> ('Rokid, умные очки', 14). A trailing number is the period in days."""
    words = (args or "").split()
    days = default_days
    if len(words) > 1 and words[-1].isdigit():
        days = min(max(int(words.pop()), 1), MAX_DAYS)
    return " ".join(words), days


_WORD = re.compile(r"[^\W_]+")


def _stem(word: str) -> str:
    """A crude ending cut, enough for Russian and English: очки -> очк, glasses -> glass."""
    if len(word) >= 6:
        return word[:-2]
    return word[:-1] if len(word) >= 4 else word


def topic_matcher(terms: list[str]) -> Callable[[str], bool]:
    """Does a post speak about the topic? Yes when every word of some term starts a word in it,
    whatever the ending: 'умные очки' matches 'умных очков', 'смарт-очки' matches 'смарт очки',
    while 'AI очки' does not match a post about AI agents. Words under 4 letters match whole."""
    groups = []
    for term in terms:
        words = _WORD.findall(term.lower())
        if words:
            groups.append(
                [re.compile(rf"(?<!\w){re.escape(_stem(w))}" + (r"(?!\w)" if len(w) < 4 else ""), re.I) for w in words]
            )
    return lambda text: any(all(p.search(text) for p in group) for group in groups)


# ---------- posts ----------

@dataclass
class Hit:
    channel: ChannelInfo
    posts: list[Post]  # oldest first


async def search_posts(
    reader: Any,
    channels: list[ChannelInfo],
    terms: list[str],
    *,
    since: datetime,
    per_channel: int = PER_CHANNEL,
    concurrency: int = 4,
) -> tuple[list[Hit], list[str]]:
    """Every term in every channel; hits merged per channel, list order kept, channels without hits dropped."""
    gate = asyncio.Semaphore(concurrency)
    errors: list[str] = []

    async def one(info: ChannelInfo) -> Hit | None:
        found: dict[int, Post] = {}
        async with gate:
            try:
                for term in terms:
                    for post in await reader.search_posts(info, term, since=since, limit=per_channel):
                        found.setdefault(post.message_id, post)
            except Exception as exc:  # one broken channel must not kill the search
                errors.append(f"{info.title} ({exc})")
                return None
        if not found:
            return None
        return Hit(info, sorted(found.values(), key=lambda p: p.message_id)[-per_channel:])

    results = await asyncio.gather(*(one(c) for c in channels))
    return [h for h in results if h], errors


# ---------- channels ----------

@dataclass
class FoundChannel:
    channel: ChannelInfo
    subscribers: int | None
    last_post: datetime | None
    posts_month: int  # posts in the last ACTIVE_DAYS
    on_topic: int  # recent text posts that mention a term
    sampled: int  # recent text posts looked at
    sample: str = ""  # start of the latest on-topic post: lets a reader (or the model) tell a shop from a media

    @property
    def score(self) -> float:
        """Share of posts on the topic times activity: a lively media beats a shop that posted once."""
        return self.on_topic / max(self.sampled, 1) * min(self.posts_month, 30)


async def find_channels(
    reader: Any,
    terms: list[str],
    *,
    now: datetime,
    exclude: set[int] | frozenset[int] = frozenset(),
    top: int = TOP_CHANNELS,
    check: int = CHECK_CHANNELS,
    concurrency: int = 4,
) -> list[FoundChannel]:
    """Public channels whose name matches a term, read a little to keep only live ones that
    actually write about the topic. Channels in `exclude` (already followed) are skipped."""
    candidates: dict[int, tuple[ChannelInfo, int | None]] = {}
    for term in terms:
        try:
            for info, subscribers in await reader.search_channels(term):
                if info.peer_id not in exclude:
                    candidates.setdefault(info.peer_id, (info, subscribers))
        except ReaderError:
            break  # flood wait: go on with what was found
    # Telegram ranks by name match, not quality: read the biggest first
    ordered = sorted(candidates.values(), key=lambda c: c[1] or 0, reverse=True)[:check]
    on_topic = topic_matcher(terms)
    gate = asyncio.Semaphore(concurrency)

    async def judge(info: ChannelInfo, subscribers: int | None) -> FoundChannel | None:
        async with gate:
            try:
                posts = await reader.fetch_posts(
                    info, after_id=0, since=now - timedelta(days=365), limit=SAMPLE_POSTS, with_images=False
                )
            except Exception:
                return None
        texts = [p for p in posts if p.text]
        matching = [p for p in texts if on_topic(p.text)]
        latest = max(matching or texts, key=lambda p: p.date, default=None)
        return FoundChannel(
            info,
            subscribers,
            max((p.date for p in posts), default=None),
            sum(p.date >= now - timedelta(days=ACTIVE_DAYS) for p in posts),
            len(matching),
            len(texts),
            " ".join(latest.text.split())[:SAMPLE_CHARS] if latest else "",
        )

    judged = [f for f in await asyncio.gather(*(judge(*c) for c in ordered)) if f]
    live = [f for f in judged if f.posts_month > 0 and f.on_topic > 0]
    live.sort(key=lambda f: (f.score, f.subscribers or 0), reverse=True)
    return live[:top]


# ---------- the bot's side ----------

class SearchService:
    def __init__(self, sessions: SessionMaker, reader: Any, llm: LLM, *, defaults: dict, concurrency: int = 4):
        self.sessions = sessions
        self.reader = reader
        self.llm = llm
        self.defaults = defaults
        self.concurrency = concurrency

    async def _terms(self, query: str) -> list[str]:
        """Terms typed with commas are used as given; a single phrase is widened by the model."""
        terms = split_terms(query)
        return terms if len(terms) > 1 else await self.llm.search_terms(terms[0])

    async def search(self, query: str, days: int, lang: str, now: datetime | None = None) -> list[str]:
        now = now or datetime.now(timezone.utc)
        async with self.sessions() as db:
            prefs = await get_settings(db, self.defaults)
            channels = await list_channels(db)
        if not channels:
            return [t(lang, "no_channels")]
        self.llm.language = language_name(prefs.language)
        terms = await self._terms(query)
        infos = [ChannelInfo(c.peer_id, c.title, c.username) for c in channels]
        hits, errors = await search_posts(
            self.reader, infos, terms, since=now - timedelta(days=days), concurrency=self.concurrency
        )
        gate = asyncio.Semaphore(self.concurrency)

        async def retell(hit: Hit) -> tuple[Hit, str] | None:
            async with gate:
                try:
                    summary = await self.llm.summarize_search(hit.channel.title, query, hit.posts)
                except Exception as exc:
                    errors.append(f"{hit.channel.title} ({exc})")
                    return None
            # words matched in another sense: the model says so, the channel is not shown
            return None if summary.strip().upper().startswith(SEARCH_NONE) else (hit, summary)

        relevant = [r for r in await asyncio.gather(*(retell(h) for h in hits)) if r]
        shown_terms = html.escape(", ".join(terms), quote=False)
        if not relevant:
            parts = [t(lang, "search_nothing", query=html.escape(query, quote=False), days=days, terms=shown_terms)]
        else:
            sections = []
            for hit, summary in relevant:
                name = html.escape(hit.channel.title, quote=False)
                if hit.channel.username:
                    name = f'<a href="https://t.me/{hit.channel.username}">{name}</a>'
                sections.append(f"➡️ <b>{name}</b>\n{link_refs(summary, hit.posts)}")
            parts = [
                t(
                    lang,
                    "search_title",
                    query=html.escape(query, quote=False),
                    days=days,
                    channels=len(relevant),
                    posts=sum(len(hit.posts) for hit, _ in relevant),
                ),
                t(lang, "search_terms", terms=shown_terms),
                *sections,
            ]
        if errors:
            parts.append(t(lang, "failed_channels", items=html.escape(", ".join(errors), quote=False)))
        return split_message("\n\n".join(parts))

    async def find(self, query: str, lang: str, now: datetime | None = None) -> tuple[str, list[FoundChannel]]:
        now = now or datetime.now(timezone.utc)
        async with self.sessions() as db:
            followed = {c.peer_id for c in await list_channels(db)}
        terms = await self._terms(query)
        found = await find_channels(
            self.reader, terms, now=now, exclude=followed, top=TOP_CHANNELS * 2, concurrency=self.concurrency
        )
        # a word match is not a topic match: «умные очки» also finds optics shops
        keep = await self.llm.pick_channels(query, [(f.channel.title, f.sample) for f in found])
        found = [f for i, f in enumerate(found) if i in keep][:TOP_CHANNELS]
        shown = html.escape(query, quote=False)
        if not found:
            return t(lang, "find_nothing", query=shown, terms=html.escape(", ".join(terms), quote=False)), []
        lines = [t(lang, "find_title", query=shown), ""]
        for i, f in enumerate(found, start=1):
            name = html.escape(f.channel.title, quote=False)
            subscribers = f"{f.subscribers:,}".replace(",", " ") if f.subscribers is not None else "?"
            lines.append(
                f'{i}. <a href="https://t.me/{f.channel.username}">{name}</a>\n'
                + t(
                    lang,
                    "find_stats",
                    subscribers=subscribers,
                    month=f.posts_month,
                    on_topic=f.on_topic,
                    sampled=f.sampled,
                )
            )
        lines += ["", t(lang, "find_hint")]
        return "\n".join(lines), found
