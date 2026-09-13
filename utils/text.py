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

    def replace(match: re.Match) -> str:
        links = []
        for n in dict.fromkeys(int(x) for x in _NUM.findall(match.group(0))):
            if 1 <= n <= len(posts):
                links.append(f'<a href="{html.escape(posts[n - 1].link)}">{n}</a>')
        return f" ({', '.join(links)})" if links else ""

    return _REF_RUN.sub(replace, escaped)


def split_message(text: str, limit: int = TELEGRAM_LIMIT) -> list[str]:
    """Split on blank lines, then lines, then spaces. Links live inside single lines, so tags stay whole."""
    chunks: list[str] = []
    current = ""
    for piece in _pieces(text, limit):
        candidate = f"{current}\n{piece}" if current else piece
        if len(candidate) <= limit:
            current = candidate
        else:
            if current:
                chunks.append(current)
            current = piece
    if current:
        chunks.append(current)
    return chunks


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
