"""
Turning model output into safe Telegram HTML, and splitting long digests.

The model never writes URLs: it cites post numbers like [2][5], and we swap them for real
links here. A link the model made up is impossible by construction.
"""
import html
import re

from services.reader import Post

TELEGRAM_LIMIT = 4096

_REF_RUN = re.compile(r"(?:\s*\[\s*\d+(?:\s*,\s*\d+)*\s*\])+")
_NUM = re.compile(r"\d+")
MAX_REF_DIGITS = 6  # no issue has a million posts; a 5000-digit "number" must not reach int()


def _numbers(run: str) -> list[int]:
    """The post numbers of one citation run, in order; absurdly long digit strings are ignored."""
    return [int(x) for x in _NUM.findall(run) if len(x) <= MAX_REF_DIGITS]


def one_line(value: object, limit: int = 300) -> str:
    """An error message fit for one line inside an <i> element: no line breaks, not a page long."""
    text = " ".join(str(value).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def link_refs(summary: str, posts: list[Post], labels: list[str] | None = None) -> str:
    """Escape model text for HTML and replace [n] citations with links to the posts.
    labels[n-1], when given, is the link's text instead of the number (the channel name in a
    digest by topic, where one point can cite several channels)."""
    escaped = html.escape(summary, quote=False)
    seen: set[int] = set()  # a post already linked is not linked again: "(1) ... (1) ... (1)" is noise

    def replace(match: re.Match) -> str:
        links = []
        used: dict[str, int] = {}  # two posts of one channel in one point: "Tech, Tech 2"
        for n in dict.fromkeys(_numbers(match.group(0))):
            if 1 <= n <= len(posts) and n not in seen:
                seen.add(n)
                if labels:
                    label = labels[n - 1]
                    used[label] = used.get(label, 0) + 1
                    text = html.escape(label if used[label] == 1 else f"{label} {used[label]}", quote=False)
                else:
                    text = str(n)
                links.append(f'<a href="{html.escape(posts[n - 1].link)}">{text}</a>')
        return f" ({', '.join(links)})" if links else ""

    linked = _REF_RUN.sub(replace, escaped)
    return re.sub(r"\n[ \t​]*(?:\n[ \t​]*)+", "\n\n", linked).strip()  # at most one blank line


def renumber_refs(summary: str, offset: int, count: int) -> str:
    """A channel's [k] citations (1..count) as numbers across the whole issue: [offset + k].
    A number outside 1..count was never a post of this channel and is dropped."""

    def replace(match: re.Match) -> str:
        run = match.group(0)
        valid = [n for n in _numbers(run) if 1 <= n <= count]
        if not valid:
            return ""
        lead = run[: len(run) - len(run.lstrip())]  # the run swallows the space before it: keep it
        return lead + "".join(f"[{offset + n}]" for n in dict.fromkeys(valid))

    return _REF_RUN.sub(replace, summary)


def cited_numbers(text: str) -> set[int]:
    """Every post number the text cites in [n] form."""
    return {n for run in _REF_RUN.findall(text) for n in _numbers(run)}


def strip_refs(text: str) -> str:
    """The text without its [n] citations (a heading is no place for a link)."""
    return _REF_RUN.sub("", text).strip()


def parse_words(raw: str | None) -> list[str]:
    """Filter words as typed: comma- or line-separated, trimmed, case kept for display, no repeats."""
    words = [w.strip() for w in re.split(r"[,\n]", raw or "")]
    return list(dict.fromkeys(w for w in words if w))[:50]


def mute_pattern(words: list[str]) -> re.Pattern | None:
    """Matches a post that has any of the words at the start of a word, any case: «крипт»
    mutes «криптовалюта» and «Крипта», but not «скрипт»."""
    if not words:
        return None
    return re.compile(r"(?<!\w)(?:" + "|".join(re.escape(w) for w in words) + ")", re.I)


def split_message(text: str, limit: int = TELEGRAM_LIMIT) -> list[str]:
    """Split into Telegram-sized messages at the widest possible seam.

    Blocks separated by a blank line are kept whole when they fit, so a channel title never
    ends one message while its text starts the next. Only a block longer than the limit is
    cut by lines, then by spaces. Links live inside single lines, so tags stay whole.
    """
    chunks: list[str] = []
    current = ""

    def push(piece: str, sep: str) -> None:
        nonlocal current
        candidate = f"{current}{sep}{piece}" if current else piece
        if len(candidate) <= limit:
            current = candidate
            return
        if current:
            chunks.append(current)
        current = piece

    for block in text.split("\n\n"):
        if len(block) <= limit:
            push(block, "\n\n")
            continue
        for line in _pieces(block, limit):
            push(line, "\n")
    if current:
        chunks.append(current)
    return [c.strip("\n") for c in chunks if c.strip()]


_TAG = re.compile(r"<(/?)([a-zA-Z]+)[^>]*>")


def _cut_point(line: str, limit: int) -> int:
    """The last space before the limit, stepped back out of a tag ('<a' | 'href=…') or an entity
    ('&am' | 'p;') it would land in."""
    cut = line.rfind(" ", 0, limit)
    cut = cut if cut > 0 else limit
    for opener, closer in (("<", ">"), ("&", ";")):
        head = line[:cut]
        pos = head.rfind(opener)
        if 0 < pos and pos > head.rfind(closer):
            cut = pos
    return cut


def _open_elements(head: str) -> list[tuple[str, int, str]]:
    """Elements opened in `head` and not closed there: (name, start, opening tag)."""
    stack: list[tuple[str, int, str]] = []
    for match in _TAG.finditer(head):
        name = match.group(2).lower()
        if match.group(1):
            if stack and stack[-1][0] == name:
                stack.pop()
        else:
            stack.append((name, match.start(), match.group(0)))
    return stack


def _split_line(line: str, limit: int) -> tuple[str, str]:
    """An over-long line -> a head of at most `limit` chars and the rest, both valid HTML for Telegram.
    A short element the cut would split (a link, a bold title) moves whole into the rest; an element
    longer than that (a long <i> list) is closed at the cut and opened again in the rest."""
    margin = 0
    while True:
        cut = _cut_point(line, limit - margin)
        stack = _open_elements(line[:cut])
        if stack and stack[0][1] > 0:
            start = stack[0][1]
            return line[:start].rstrip(), line[start:].lstrip()
        closers = "".join(f"</{name}>" for name, _, _ in reversed(stack))
        if cut + len(closers) <= limit or margin:
            reopen = "".join(tag for _, _, tag in stack)
            head, rest = line[:cut].rstrip() + closers, reopen + line[cut:].lstrip()
            if len(rest) >= len(line):  # a limit too small for the tags themselves: cut plainly, but move on
                return line[:limit], line[limit:]
            return head, rest
        margin = len(closers)


def _pieces(text: str, limit: int) -> list[str]:
    out: list[str] = []
    for line in text.split("\n"):
        while len(line) > limit:
            piece, line = _split_line(line, limit)
            out.append(piece)
        out.append(line)
    return out
