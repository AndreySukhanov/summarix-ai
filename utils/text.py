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


def _pieces(text: str, limit: int) -> list[str]:
    out: list[str] = []
    for line in text.split("\n"):
        while len(line) > limit:
            cut = line.rfind(" ", 0, limit)
            cut = cut if cut > 0 else limit
            out.append(line[:cut])
            line = line[cut:].lstrip()
        out.append(line)
    return out
