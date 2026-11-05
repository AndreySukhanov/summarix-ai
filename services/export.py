"""
Every delivered digest with news as a Markdown file in a folder of your choice (DIGEST_EXPORT_DIR):
an Obsidian vault, a synced notes folder, a plain archive. The links to the posts stay links.
"No new posts" replies are not archived.
"""
import html
import re
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote

_MD_SPECIAL = re.compile(r"([\\`*_\[\]])")


def _md_text(text: str) -> str:
    """Plain text safe in Markdown: its own <, > and & stay literal, its *, _, [ ] and ` stay characters."""
    return _MD_SPECIAL.sub(r"\\\1", html.escape(text, quote=False))


def _md_code(text: str) -> str:
    """Inline code as written: a fence one backtick longer than any run inside, padded when the
    code itself starts or ends with a backtick."""
    longest = max((len(run) for run in re.findall(r"`+", text)), default=0)
    fence = "`" * (longest + 1)
    pad = " " if text.startswith("`") or text.endswith("`") else ""
    return f"{fence}{pad}{text}{pad}{fence}"


def _md_url(url: str) -> str:
    """A link target that cannot close the link early: spaces and parentheses percent-encoded."""
    return quote(url, safe=":/?#@!$&'*+,;=%~-._")


class _ToMarkdown(HTMLParser):
    """The digest's Telegram HTML -> Markdown: <a>, <b>, <i>, <code>; any other tag keeps only its text."""

    WRAP = {"b": "**", "strong": "**", "i": "_", "em": "_"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.links: list[tuple[str, int]] = []  # (href, where the link text starts in out)
        self.code: list[str] | None = None  # inside <code>: the text as is, no escaping

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.links.append((dict(attrs).get("href") or "", len(self.out)))
        elif tag == "code":
            self.code = []
        elif tag in self.WRAP:
            self.out.append(self.WRAP[tag])

    def handle_endtag(self, tag):
        if tag == "a" and self.links:
            href, start = self.links.pop()
            label = "".join(self.out[start:])
            del self.out[start:]
            self.out.append(f"[{label}]({_md_url(href)})" if href else label)
        elif tag == "code" and self.code is not None:
            self.out.append(_md_code("".join(self.code)))
            self.code = None
        elif tag in self.WRAP:
            self.out.append(self.WRAP[tag])

    def handle_data(self, data):
        if self.code is not None:
            self.code.append(data)
        else:
            self.out.append(_md_text(data))

    def close(self):
        super().close()
        if self.code is not None:  # an unclosed <code> keeps its text
            self.out.append(_md_code("".join(self.code)))
            self.code = None


def html_to_markdown(text: str) -> str:
    parser = _ToMarkdown()
    parser.feed(text)
    parser.close()
    return "".join(parser.out)


def _slug(title: str) -> str:
    words = re.findall(r"\w+", title)
    return "-".join(words)[:60]


def export_digest(directory: Path, messages: list[str], when: datetime, group: str | None = None) -> Path:
    """Writes the digest to `<directory>/<YYYY-MM-DD_HHMM>[_<group>].md` and returns the path.
    An existing file is never overwritten: a second digest in the same minute gets "-2"."""
    directory.mkdir(parents=True, exist_ok=True)
    stem = f"{when:%Y-%m-%d_%H%M}" + (f"_{_slug(group)}" if group and _slug(group) else "")
    path = directory / f"{stem}.md"
    n = 2
    while path.exists():
        path = directory / f"{stem}-{n}.md"
        n += 1
    body = "\n\n".join(html_to_markdown(m).strip() for m in messages if m.strip())
    path.write_text(body + "\n", encoding="utf-8")
    return path
