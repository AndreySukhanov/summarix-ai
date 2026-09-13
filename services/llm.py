"""
Everything that talks to the model: image captions, per-channel summaries, cross-channel highlights.
Works with any OpenAI-compatible chat API.
"""
import base64
from dataclasses import dataclass
from typing import Any

from services.reader import Post

POST_CHARS_IN_PROMPT = 1500

# The voice goes first and is framed as the reader's choice: placed after a block of "hard rules"
# it read as an afterthought and every style collapsed into the same neutral summary.
SUMMARY_PROMPT = """You retell what one Telegram channel posted, for a reader who chose a specific voice for their digest.

THE VOICE - the reader picked it on purpose. Commit to it in every sentence; do not drift back into a neutral news summary:
{style}

Keep, whatever the voice:
- Write in {language}.
- Facts come only from the posts: the voice changes how you tell them, never what happened. Merge posts about the same thing.
- Cite source posts by number in square brackets at the end of the sentence they support, e.g. [2] or [2][5]. Never write links.
- Skip ads, giveaways and cross-promotion. If that is all there is, say so in one line - in the voice.
- A voice is attitude, not a set of catchphrases: use any signature phrase of the voice at most once, and vary the jokes.
- Hard limit: {words} words for this channel, in one or two short paragraphs. With many posts, keep only what matters most.
- No Markdown (no **, no #)."""

HIGHLIGHTS_PROMPT = """Below are digests of several Telegram channels. Pick the 3 most important items across all of them.

Write in {language}, in this voice:
{style}

Format regardless of the voice: exactly 3 lines, each starts with "• " and ends with the channel name in parentheses.
Each line at most 40 words. Do not repeat the same catchphrase across lines. No intro, no Markdown, no source numbers."""

WORDS_PLAIN = 120  # the default "digest" style is a list
WORDS_STYLED = 180  # voices need room for their tone

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

    async def summarize_channel(self, title: str, posts: list[Post], style: str, words: int = WORDS_PLAIN) -> str:
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
                {"role": "system", "content": SUMMARY_PROMPT.format(language=self.language, style=style, words=words)},
                {"role": "user", "content": user},
            ],
        )

    async def highlights(self, sections: list[tuple[str, str]], style: str) -> str:
        user = "\n\n".join(f"## {title}\n{summary}" for title, summary in sections)
        return await self._chat(
            self.model,
            [
                {"role": "system", "content": HIGHLIGHTS_PROMPT.format(language=self.language, style=style)},
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
