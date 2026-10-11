"""
tgdigest: the Claude Code side of Summarix. Collects posts from a hand-picked channel list
into a Markdown file; Claude writes the digest from that file.

Kept apart from the bot on purpose:
- its own Telegram session (data/tgdigest/claude.session): two processes on one session file
  trip over each other;
- its own channel list (data/tgdigest/channels.json);
- recap only: reads the last N hours and moves no read marks, so the bot's daily digest misses nothing.

    python scripts/tgdigest.py login                    # once, in a terminal: phone, code, 2FA
    python scripts/tgdigest.py add t.me/addlist/slug    # a shared folder, @name, t.me/name, t.me/+invite
    python scripts/tgdigest.py list | remove 3 @name | sync
    python scripts/tgdigest.py fetch [--hours 24] [--style rick] [--images 15] [--no-sync]
                                     # refreshes the folders first, so the list follows Telegram
    python scripts/tgdigest.py search "очки" "очков" "smart glasses" [--days 30]   # posts of the list
    python scripts/tgdigest.py find "умные очки" "smart glasses" [--top 10]        # new live channels
    python scripts/tgdigest.py styles
"""
import argparse
import asyncio
import json
import sqlite3
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.reader import ChannelInfo, Post, ReaderError, TelethonReader  # noqa: E402
from services.refs import RefError, parse_channel_ref  # noqa: E402
from services.search import PER_CHANNEL, SEARCH_DAYS, TOP_CHANNELS, find_channels, search_posts  # noqa: E402
from services.styles import DEFAULT_STYLE, STYLES, style_prompt, style_title  # noqa: E402

DATA = ROOT / "data" / "tgdigest"
SESSION = DATA / "claude"  # Telethon appends .session
LIST_FILE = DATA / "channels.json"
POSTS_FILE = DATA / "posts_latest.md"
SEARCH_FILE = DATA / "search_latest.md"
IMAGES_DIR = DATA / "img"
BOT_DB = ROOT / "data" / "summarix.db"

DEFAULT_HOURS = 24
DEFAULT_MAX_POSTS = 40
DEFAULT_IMAGES = 15
POST_CHARS = 2000
PART_CHARS = 120_000  # what one summarizing agent reads comfortably (Cyrillic is ~2 chars a token)
SHORT_TEXT = 80  # a photo post with less text than this: the picture carries the news
MANUAL = "manual"
DEVICE = "Claude Code tgdigest"  # how the session shows up in Telegram > Devices


# ---------- channel list ----------

@dataclass
class Entry:
    peer_id: int
    title: str
    username: str | None
    source: str = MANUAL  # "manual" or the slug of the folder it came from

    def info(self) -> ChannelInfo:
        return ChannelInfo(self.peer_id, self.title, self.username)


@dataclass
class ChannelList:
    channels: list[Entry] = field(default_factory=list)
    folders: dict[str, str] = field(default_factory=dict)  # slug -> folder title
    excluded: list[int] = field(default_factory=list)  # removed by hand: a folder sync keeps them out

    @classmethod
    def load(cls, path: Path = LIST_FILE) -> "ChannelList":
        if not path.exists():
            return cls()
        raw = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            [Entry(**c) for c in raw.get("channels", [])],
            raw.get("folders", {}),
            raw.get("excluded", []),
        )

    def save(self, path: Path = LIST_FILE) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "folders": self.folders,
            "excluded": self.excluded,
            "channels": [asdict(c) for c in self.channels],
        }
        # write aside, then swap: an interrupted save must not leave a broken list behind
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)

    def add(self, info: ChannelInfo, source: str = MANUAL) -> bool:
        if source == MANUAL and info.peer_id in self.excluded:
            self.excluded.remove(info.peer_id)  # added back by hand
        if info.peer_id in self.excluded or any(c.peer_id == info.peer_id for c in self.channels):
            return False
        self.channels.append(Entry(info.peer_id, info.title, info.username, source))
        return True

    def find(self, key: str) -> Entry:
        """By number in `list` (1-based), @username or a piece of the title."""
        key = key.strip()
        if key.isdigit():
            index = int(key) - 1
            if 0 <= index < len(self.channels):
                return self.channels[index]
            raise KeyError(f"нет канала с номером {key}")
        name = key.lstrip("@").lower()
        by_name = [c for c in self.channels if (c.username or "").lower() == name]
        if by_name:
            return by_name[0]
        by_title = [c for c in self.channels if name in c.title.lower()]
        if len(by_title) == 1:
            return by_title[0]
        if not by_title:
            raise KeyError(f"не нашёл канал «{key}»")
        raise KeyError(f"«{key}» подходит к нескольким: " + ", ".join(c.title for c in by_title))

    def remove(self, entry: Entry) -> None:
        self.channels.remove(entry)
        if entry.source != MANUAL and entry.peer_id not in self.excluded:
            self.excluded.append(entry.peer_id)

    def sync_folder(self, slug: str, title: str, infos: list[ChannelInfo]) -> tuple[list[str], list[str]]:
        """Bring the channels that came from this folder in line with it; manual ones stay."""
        self.folders[slug] = title
        present = {i.peer_id: i for i in infos}
        for c in self.channels:
            if c.peer_id in present:
                c.title, c.username = present[c.peer_id].title, present[c.peer_id].username  # renamed channels
                if c.source == MANUAL:
                    c.source = slug  # added by hand, then put into the folder: the folder owns it now
        gone = [c for c in self.channels if c.source == slug and c.peer_id not in present]
        for c in gone:
            self.channels.remove(c)
        added = [i.title for i in infos if self.add(i, slug)]
        return added, [c.title for c in gone]


async def sync_folders(reader: Any, lst: ChannelList) -> list[str]:
    """Bring every folder of the list up to date. Returns report lines, empty when nothing
    changed; a folder that cannot be read is reported and the saved channels stay."""
    report = []
    for slug in list(lst.folders):
        name = lst.folders[slug]
        try:
            folder = await reader.resolve_folder(slug, own=True)
        except Exception as exc:  # a network hiccup must not cost the digest
            report.append(f"папка «{name}» не обновилась, беру сохранённый список: {exc}")
            continue
        added, gone = lst.sync_folder(slug, folder.title or name, folder.channels)
        if added or gone:
            report.append(f"папка «{lst.folders[slug]}»: +{len(added)} -{len(gone)}")
            report += [f"  + {title}" for title in added] + [f"  - {title}" for title in gone]
    return report


def folder_from_bot_db(slug: str, db: Path = BOT_DB) -> tuple[str, list[ChannelInfo]] | None:
    """The bot already stores the channels of folders it was given; usable before `login`."""
    if not db.exists():
        return None
    con = sqlite3.connect(db.as_uri() + "?mode=ro", uri=True)
    try:
        group = con.execute("SELECT id, title FROM groups WHERE folder_slug = ?", (slug,)).fetchone()
        if not group:
            return None
        rows = con.execute(
            "SELECT c.peer_id, c.title, c.username FROM channels c "
            "JOIN group_channels gc ON gc.channel_id = c.id WHERE gc.group_id = ? ORDER BY c.id",
            (group[0],),
        ).fetchall()
    finally:
        con.close()
    return group[1], [ChannelInfo(*row) for row in rows]


# ---------- fetching ----------

@dataclass
class Section:
    channel: ChannelInfo
    posts: list[Post]
    images: dict[int, Path] = field(default_factory=dict)  # post message_id -> saved photo


async def fetch_all(
    reader: Any,
    channels: list[ChannelInfo],
    *,
    since: datetime,
    max_posts: int = DEFAULT_MAX_POSTS,
    image_budget: int = DEFAULT_IMAGES,
    images_dir: Path = IMAGES_DIR,
    concurrency: int = 4,
) -> tuple[list[Section], list[str]]:
    """Recap of every channel since `since`, list order kept. Photos only for posts where the
    picture is the news (little or no text), capped per run."""
    gate = asyncio.Semaphore(concurrency)
    budget = {"images": image_budget}
    errors: list[str] = []

    async def one(info: ChannelInfo) -> Section | None:
        async with gate:
            try:
                posts = await reader.fetch_posts(info, after_id=0, since=since, limit=max_posts, with_images=False)
            except Exception as exc:  # one broken channel must not kill the run
                errors.append(f"{info.title} ({exc})")
                return None
            if not posts:
                return None
            section = Section(info, posts)
            for post in posts:
                if post.photo_message_id is None or len(post.text) >= SHORT_TEXT or budget["images"] <= 0:
                    continue
                budget["images"] -= 1  # reserve before awaiting: other channels run concurrently
                try:
                    data = await reader.download_photo(info, post.photo_message_id)
                except Exception:
                    data = None  # a missing picture is not worth failing the channel
                if data:
                    images_dir.mkdir(parents=True, exist_ok=True)
                    path = images_dir / f"{abs(info.peer_id)}_{post.message_id}.jpg"
                    path.write_bytes(data)
                    section.images[post.message_id] = path
            return section

    results = await asyncio.gather(*(one(c) for c in channels))
    return [s for s in results if s], errors


def render_blocks(
    sections: list[Section],
    errors: list[str],
    *,
    hours: int,
    now: datetime,
    total_channels: int,
    style_key: str,
    style_text: str,
) -> tuple[str, list[str]]:
    """The header and one block per channel; numbering is global so parts can be merged back."""
    posts = sum(len(s.posts) for s in sections)
    header = [
        f"# tgdigest · посты за {hours} ч до {now.astimezone():%d.%m.%Y %H:%M}",
        f"Каналов в списке: {total_channels}; с постами: {len(sections)}; постов: {posts}",
        f"Стиль: {style_key}",
        f"STYLE: {style_text}",
        "",
    ]
    if errors:
        header += ["Не прочитались: " + "; ".join(errors), ""]
    return "\n".join(header), channel_blocks(sections)


def search_blocks(
    sections: list[Section], errors: list[str], *, terms: list[str], days: int, now: datetime, total_channels: int
) -> tuple[str, list[str]]:
    posts = sum(len(s.posts) for s in sections)
    header = [
        f"# tgdigest · поиск за {days} дн. до {now.astimezone():%d.%m.%Y %H:%M}",
        "Слова поиска: " + ", ".join(f"«{term}»" for term in terms),
        f"Каналов в списке: {total_channels}; с находками: {len(sections)}; постов: {posts}",
        "",
    ]
    if errors:
        header += ["Не прочитались: " + "; ".join(errors), ""]
    return "\n".join(header), channel_blocks(sections)


def channel_blocks(sections: list[Section]) -> list[str]:
    blocks = []
    for ci, s in enumerate(sections, start=1):
        channel = s.channel
        handle = f" · https://t.me/{channel.username}" if channel.username else ""
        lines = [f"## {ci}. {channel.title}{handle}", ""]
        for pi, post in enumerate(s.posts, start=1):
            lines.append(f"### [{pi}] {post.date.astimezone():%d.%m %H:%M} · {post.link}")
            text = post.text if len(post.text) <= POST_CHARS else post.text[:POST_CHARS] + "…"
            if text:
                lines.append(text)
            if post.links:
                lines.append("Ссылки: " + "; ".join(f"«{anchor}» {url}" for anchor, url in post.links))
            if post.message_id in s.images:
                lines.append(f"(картинка: {s.images[post.message_id]})")
            elif not text:
                lines.append("(пост из одной картинки, не скачана)")
            lines.append("")
        blocks.append("\n".join(lines))
    return blocks


def render(sections: list[Section], errors: list[str], **kwargs) -> str:
    header, blocks = render_blocks(sections, errors, **kwargs)
    return "\n".join([header, *blocks])


def pack(blocks: list[str], limit: int = PART_CHARS) -> list[list[str]]:
    """Channel blocks into parts of about `limit` characters; a channel is never split."""
    parts: list[list[str]] = []
    current: list[str] = []
    size = 0
    for block in blocks:
        if current and size + len(block) > limit:
            parts.append(current)
            current, size = [], 0
        current.append(block)
        size += len(block)
    if current:
        parts.append(current)
    return parts


# ---------- Telegram session ----------

def account_settings():
    from config.settings import TelegramAccountSettings

    return TelegramAccountSettings(_env_file=ROOT / ".env")


def make_client():
    from telethon import TelegramClient

    s = account_settings()
    return TelegramClient(str(SESSION), s.tg_api_id, s.tg_api_hash, device_model=DEVICE, receive_updates=False)


async def connect():
    """An authorized client, or None when `login` has not been run yet."""
    if not SESSION.with_suffix(".session").exists():
        return None
    client = make_client()
    await client.connect()
    if not await client.is_user_authorized():
        await client.disconnect()
        return None
    return client


NO_SESSION = (
    "Нет сессии tgdigest. Один раз в отдельном окне терминала:\n"
    f'  "{ROOT / ".venv" / "Scripts" / "python.exe"}" "{Path(__file__).resolve()}" login'
)


# ---------- commands ----------

async def cmd_login(_args) -> None:
    from scripts.login import ask_phone

    DATA.mkdir(parents=True, exist_ok=True)
    client = make_client()
    await client.start(phone=ask_phone)
    me = await client.get_me()
    if me.bot:
        await client.log_out()
        sys.exit("Это бот, он не читает каналы. Запусти снова и введи номер телефона.")
    print(f"Вошёл как {me.first_name} (id {me.id}). Сессия: {SESSION}.session")
    print("Файл сессии = полный доступ к аккаунту: никому не передавать и не коммитить.")
    await client.disconnect()


def cmd_list(_args) -> None:
    lst = ChannelList.load()
    if not lst.channels:
        print("Список пуст. Добавь: add @канал или add https://t.me/addlist/...")
        return
    for i, c in enumerate(lst.channels, start=1):
        handle = f" @{c.username}" if c.username else ""
        source = "" if c.source == MANUAL else f"  [папка {lst.folders.get(c.source, c.source)}]"
        print(f"{i:>3}. {c.title}{handle}{source}")
    if lst.excluded:
        print(f"Убрано из папок вручную: {len(lst.excluded)}")


async def cmd_add(args) -> None:
    lst = ChannelList.load()
    client = await connect()
    reader = TelethonReader(client) if client else None
    try:
        for raw in args.refs:
            try:
                ref = parse_channel_ref(raw)
            except RefError as exc:
                print(f"пропуск {raw}: {exc}")
                continue
            if ref.kind == "folder":
                if reader:
                    try:
                        folder = await reader.resolve_folder(ref.value, own=True)
                    except ReaderError as exc:
                        print(f"папка {raw}: {exc}")
                        continue
                    title, infos = folder.title, folder.channels
                    if folder.skipped:
                        print("Пропущены (не каналы или закрытые без вступления): " + ", ".join(folder.skipped))
                else:
                    found = folder_from_bot_db(ref.value)
                    if not found:
                        print(NO_SESSION)
                        continue
                    title, infos = found
                    print("Сессии ещё нет: каналы папки взяты из базы бота. После login сделай sync.")
                added, gone = lst.sync_folder(ref.value, title, infos)
                print(f"Папка «{title}»: добавлено {len(added)}, убрано {len(gone)}, в списке {len(lst.channels)}")
            elif not reader:
                print(f"{raw}: нужна сессия.\n{NO_SESSION}")
            else:
                try:
                    info = await reader.resolve(ref)
                except ReaderError as exc:
                    print(f"{raw}: {exc}")
                    continue
                print(("добавлен: " if lst.add(info) else "уже в списке: ") + info.title)
    finally:
        lst.save()
        if client:
            await client.disconnect()


def cmd_remove(args) -> None:
    lst = ChannelList.load()
    entries = []
    for key in args.keys:  # resolve all first: numbers shift after each removal
        try:
            entries.append(lst.find(key))
        except KeyError as exc:
            print(exc.args[0])
    for entry in entries:
        if entry in lst.channels:  # skips a channel named twice
            lst.remove(entry)
            print(f"убран: {entry.title}")
    lst.save()


async def cmd_sync(_args) -> None:
    lst = ChannelList.load()
    if not lst.folders:
        print("В списке нет папок, синхронизировать нечего.")
        return
    client = await connect()
    if not client:
        sys.exit(NO_SESSION)
    try:
        report = await sync_folders(TelethonReader(client), lst)
    finally:
        lst.save()
        await client.disconnect()
    print("\n".join(report) or "Папки без изменений.")


async def open_list(no_sync: bool) -> tuple[ChannelList, Any]:
    """The channel list, brought in line with its folders, and a connected client."""
    lst = ChannelList.load()
    client = await connect()
    if not client:
        sys.exit(NO_SESSION)
    if lst.folders and not no_sync:  # the folder in Telegram is where the list is kept
        try:
            report = await sync_folders(TelethonReader(client), lst)
        finally:
            lst.save()
        for line in report:
            print(line)
    if not lst.channels:
        await client.disconnect()
        sys.exit("Список каналов пуст: сначала add.")
    return lst, client


def write_output(path: Path, header: str, blocks: list[str]) -> str:
    """The whole file plus <name>_partK.md files when it is too big for one reader; prints the paths."""
    text = "\n".join([header, *blocks])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    stem = path.stem.replace("_latest", "")
    for old in path.parent.glob(f"{stem}_part*.md"):
        old.unlink()
    print(f"файл: {path}")
    parts = pack(blocks)
    if len(parts) > 1:
        for i, part in enumerate(parts, start=1):
            part_path = path.parent / f"{stem}_part{i}.md"
            part_path.write_text("\n".join([header, f"Часть {i} из {len(parts)}", "", *part]), encoding="utf-8")
            print(f"часть {i}: {part_path}")
    return text


async def cmd_search(args) -> None:
    terms = list(dict.fromkeys(term.strip() for term in args.terms if term.strip()))
    lst, client = await open_list(args.no_sync)
    now = datetime.now(timezone.utc)
    try:
        hits, errors = await search_posts(
            TelethonReader(client),
            [c.info() for c in lst.channels],
            terms,
            since=now - timedelta(days=args.days),
            per_channel=args.per_channel,
        )
    finally:
        await client.disconnect()
    sections = [Section(h.channel, h.posts) for h in hits]
    header, blocks = search_blocks(
        sections, errors, terms=terms, days=args.days, now=now, total_channels=len(lst.channels)
    )
    text = write_output(SEARCH_FILE, header, blocks)
    posts = sum(len(s.posts) for s in sections)
    print(f"каналов с находками: {len(sections)} из {len(lst.channels)}; постов: {posts}; символов: {len(text)}")
    if errors:
        print("не прочитались: " + "; ".join(errors))


async def cmd_find(args) -> None:
    terms = list(dict.fromkeys(term.strip() for term in args.terms if term.strip()))
    lst = ChannelList.load()
    client = await connect()
    if not client:
        sys.exit(NO_SESSION)
    now = datetime.now(timezone.utc)
    try:
        found = await find_channels(
            TelethonReader(client), terms, now=now, exclude={c.peer_id for c in lst.channels}, top=args.top
        )
    finally:
        await client.disconnect()
    if not found:
        print("Живых каналов по этим словам не нашлось (каналы из списка не показываются).")
        return
    for i, f in enumerate(found, start=1):
        subscribers = f.subscribers if f.subscribers is not None else "?"
        last = f.last_post.astimezone().strftime("%d.%m.%y") if f.last_post else "-"
        print(
            f"{i:>2}. {f.channel.title} · https://t.me/{f.channel.username}\n"
            f"    подписчиков: {subscribers} · постов за месяц: {f.posts_month} · "
            f"по теме {f.on_topic} из {f.sampled} последних · последний пост {last}\n"
            f"    пример: {f.sample}"
        )


async def cmd_fetch(args) -> None:
    lst, client = await open_list(args.no_sync)
    for old in IMAGES_DIR.glob("*.jpg") if IMAGES_DIR.exists() else []:
        old.unlink()
    now = datetime.now(timezone.utc)
    try:
        sections, errors = await fetch_all(
            TelethonReader(client),
            [c.info() for c in lst.channels],
            since=now - timedelta(hours=args.hours),
            max_posts=args.max_posts,
            image_budget=args.images,
        )
    finally:
        await client.disconnect()
    header, blocks = render_blocks(
        sections,
        errors,
        hours=args.hours,
        now=now,
        total_channels=len(lst.channels),
        style_key="свой" if args.style_text else args.style,
        style_text=args.style_text or style_prompt(args.style, "ru"),
    )
    text = write_output(POSTS_FILE, header, blocks)
    posts = sum(len(s.posts) for s in sections)
    images = sum(len(s.images) for s in sections)
    print(
        f"каналов с постами: {len(sections)} из {len(lst.channels)}; "
        f"постов: {posts}; картинок: {images}; символов: {len(text)}"
    )
    if errors:
        print("не прочитались: " + "; ".join(errors))


def cmd_styles(_args) -> None:
    for key in STYLES:
        print(f"{key:<16} {style_title(key, 'ru')}")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        prog="tgdigest", description="Posts from your channel list for a Claude Code digest"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("login", help="one-time login of your account into a separate session")
    sub.add_parser("list", help="the channel list")
    add = sub.add_parser("add", help="add channels: @name, t.me links, t.me/+invite, t.me/addlist/folder")
    add.add_argument("refs", nargs="+")
    remove = sub.add_parser("remove", help="remove by number, @username or part of the title")
    remove.add_argument("keys", nargs="+")
    sub.add_parser("sync", help="re-read the folders in the list: new channels in, gone ones out")
    fetch = sub.add_parser("fetch", help="collect posts of the last N hours into a Markdown file")
    fetch.add_argument("--hours", type=int, default=DEFAULT_HOURS)
    fetch.add_argument("--max-posts", type=int, default=DEFAULT_MAX_POSTS, help="per channel")
    fetch.add_argument("--images", type=int, default=DEFAULT_IMAGES, help="photo cap per run, 0 = none")
    fetch.add_argument("--style", choices=list(STYLES), default=DEFAULT_STYLE)
    fetch.add_argument("--style-text", help="your own style description instead of a preset")
    fetch.add_argument("--no-sync", action="store_true", help="skip refreshing the folders first")
    sub.add_parser("styles", help="available styles")
    search = sub.add_parser("search", help="posts of the list matching any of the terms, into a Markdown file")
    search.add_argument("terms", nargs="+", help="word forms and synonyms: Telegram matches whole words only")
    search.add_argument("--days", type=int, default=SEARCH_DAYS)
    search.add_argument("--per-channel", type=int, default=PER_CHANNEL, help="hits per channel and term")
    search.add_argument("--no-sync", action="store_true", help="skip refreshing the folders first")
    find = sub.add_parser("find", help="live public channels about a topic that are not in the list yet")
    find.add_argument("terms", nargs="+")
    find.add_argument("--top", type=int, default=TOP_CHANNELS)

    args = parser.parse_args()
    handlers = {
        "login": cmd_login,
        "list": cmd_list,
        "add": cmd_add,
        "remove": cmd_remove,
        "sync": cmd_sync,
        "fetch": cmd_fetch,
        "styles": cmd_styles,
        "search": cmd_search,
        "find": cmd_find,
    }
    result = handlers[args.command](args)
    if asyncio.iscoroutine(result):
        asyncio.run(result)


if __name__ == "__main__":
    main()
