"""
Everything that talks to the model: image captions, per-channel summaries, cross-channel highlights.
Works with any OpenAI-compatible chat API.
"""
import base64
from dataclasses import dataclass
from typing import Any

from services.reader import Post

POST_CHARS_IN_PROMPT = 1500

SUMMARY_PROMPT = """You write a personal digest of one Telegram channel for its reader.

Hard rules - they hold whatever the style below says:
- Write in {language}.
- After each point, cite its source posts by number in square brackets, e.g. [2] or [2][5]. Never write links or URLs.
- Use only facts from the posts. Merge posts about the same thing.
- Skip ads, giveaways and cross-promotion of other channels. If the posts are only that, say so in one line.
- Keep it short: about 120 words at most for this channel.
- No Markdown: no **bold**, no # headers. Plain text; emoji are fine if the style uses them.

Style:
{style}"""

HIGHLIGHTS_PROMPT = """Below are digests of several Telegram channels.
Pick the 3 most important items across all of them. Write in {language}.
One line each, starting with "• ", then the channel name in parentheses at the end.
No intro, no Markdown, no source numbers."""

IMAGE_PROMPT = """Describe this image from a Telegram channel post in one or two sentences, in {language}.
If it contains text, a chart or a screenshot, give the key text or numbers. If it is a decorative picture, say so in three words."""


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0


class LLM:
    def __init__(self, client: Any, model: str, *, vision_model: str | None = None, language: str = "Russian"):
        self.client = client
        self.model = model
        self.vision_model = vision_model or model
        self.language = language
        self.usage = Usage()

    async def describe_image(self, image: bytes) -> str:
        data_url = "data:image/jpeg;base64," + base64.b64encode(image).decode("ascii")
        return await self._chat(
            self.vision_model,
            [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": IMAGE_PROMPT.format(language=self.language)},
                        {"type": "image_url", "image_url": {"url": data_url, "detail": "low"}},
                    ],
                }
            ],
        )

    async def summarize_channel(self, title: str, posts: list[Post], style: str) -> str:
        blocks = []
        for i, post in enumerate(posts, start=1):
            lines = [f"[{i}] {post.date:%Y-%m-%d %H:%M}"]
            if post.text:
                text = post.text if len(post.text) <= POST_CHARS_IN_PROMPT else post.text[:POST_CHARS_IN_PROMPT] + "…"
                lines.append(text)
            lines += [f"(image: {d})" for d in post.image_descriptions]
            blocks.append("\n".join(lines))
        user = f"Channel: {title}\n\n" + "\n\n".join(blocks)
        return await self._chat(
            self.model,
            [
                {"role": "system", "content": SUMMARY_PROMPT.format(language=self.language, style=style)},
                {"role": "user", "content": user},
            ],
        )

    async def highlights(self, sections: list[tuple[str, str]]) -> str:
        user = "\n\n".join(f"## {title}\n{summary}" for title, summary in sections)
        return await self._chat(
            self.model,
            [
                {"role": "system", "content": HIGHLIGHTS_PROMPT.format(language=self.language)},
                {"role": "user", "content": user},
            ],
        )

    async def _chat(self, model: str, messages: list[dict]) -> str:
        response = await self.client.chat.completions.create(model=model, messages=messages)
        usage = getattr(response, "usage", None)
        if usage is not None:
            self.usage.input_tokens += usage.prompt_tokens or 0
            self.usage.output_tokens += usage.completion_tokens or 0
        return (response.choices[0].message.content or "").strip()
