"""
Parse whatever the user pastes to point at a channel:
@name, name, t.me/name, https://t.me/s/name, t.me/name/123, t.me/+invite, t.me/joinchat/invite.
"""
import re
from dataclasses import dataclass
from typing import Literal

_USERNAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]{3,31}$")
_LINK = re.compile(r"^(?:https?://)?(?:www\.)?(?:t\.me|telegram\.me)/(.+)$", re.I)


@dataclass(frozen=True)
class ChannelRef:
    kind: Literal["username", "invite", "id"]
    value: str


class RefError(ValueError):
    pass


def parse_channel_ref(raw: str) -> ChannelRef:
    text = raw.strip().rstrip("/")
    if not text:
        raise RefError("empty reference")

    if re.fullmatch(r"-?\d+", text):
        return ChannelRef("id", text)

    link = _LINK.match(text)
    if link:
        path = link.group(1).split("?", 1)[0]
        parts = [p for p in path.split("/") if p]
        if not parts:
            raise RefError(f"not a channel link: {raw}")
        if parts[0].startswith("+"):
            return ChannelRef("invite", parts[0][1:])
        if parts[0] == "joinchat" and len(parts) > 1:
            return ChannelRef("invite", parts[1])
        if parts[0] in ("s", "c") and len(parts) > 1:
            if parts[0] == "c":
                return ChannelRef("id", f"-100{parts[1]}")
            parts = parts[1:]
        text = parts[0]

    username = text.lstrip("@")
    if not _USERNAME.match(username):
        raise RefError(f"not a channel username or link: {raw}")
    return ChannelRef("username", username.lower())
