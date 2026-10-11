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


def one_line(value: object, limit: int = 300) -> str:
    """An error message fit for one line inside an <i> element: no line breaks, not a page long."""
    text = " ".join(str(value).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def link_refs(summary: str, posts: list[Post]) -> str:
    """Escape model text for HTML and replace [n] citations with links to the posts."""
    escaped = html.escape(summary, quote=False)
    seen: set[int] = set()  # a post already linked is not linked again: "(1) ... (1) ... (1)" is noise

    def replace(match: re.Match) -> str:
        links = []
        for n in dict.fromkeys(int(x) for x in _NUM.findall(match.group(0))):
            if 1 <= n <= len(posts) and n not in seen:
                seen.add(n)
                links.append(f'<a href="{html.escape(posts[n - 1].link)}">{n}</a>')
        return f" ({', '.join(links)})" if links else ""

    linked = _REF_RUN.sub(replace, escaped)
    return re.sub(r"\n[ \t​]*(?:\n[ \t​]*)+", "\n\n", linked).strip()  # at most one blank line


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
