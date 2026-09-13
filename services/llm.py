"""
Everything that talks to the model: image captions, per-channel summaries, cross-channel highlights.
Works with any OpenAI-compatible chat API.
"""
import base64
import re
from dataclasses import dataclass
from typing import Any

from services.reader import Post

POST_CHARS_IN_PROMPT = 1500

# Layout copied from the original Summarix bot, where styles worked: a short role in the system
# message, then in the user message the posts, the task, the format - and the style LAST, right
# before the model starts writing. With the style in the system prompt ahead of 30 posts and a
# "cite every sentence" rule, every voice faded into a neutral news summary.
SUMMARY_SYSTEM = (
    "You are a sharp content curator with a strong voice. You turn Telegram channel posts into short, "
    "vivid retellings: nothing important is lost, nothing boring remains. Stay fully in character "
    "for the requested style from the first word to the last."
)

SUMMARY_TASK = """

Retell these posts so the reader saves most of the reading time but misses nothing important. Be concise, never dry: the style below matters as much as the facts.

Format:
- Write in {language}. Plain text, no Markdown; emoji and line breaks are fine.
- At most {words} words, one or two short paragraphs. With many posts, keep only what matters most.
- Facts only from the posts - the style changes how you tell them, never what happened. Skip ads and cross-promotion.
- After a key fact, put the source post number in square brackets, e.g. [2]. Only after key facts, not after every sentence. Never write links.
- This retelling is one of many channels the reader sees back to back in one digest. Every channel must sound fresh: use at most one or two signature devices of the style here, no stock opening or closing line, no joke you would reuse for another channel.
- Start with the retelling itself: no disclaimers, no remarks about the style or the voice.
- Add 2-4 emoji that fit the content and the style, each next to the fact it illustrates (🤖 AI, 💰 money, 🔒 security, 🎮 games, 📉 decline...). Pick them for this channel's topics; do not reuse one generic set everywhere.
- No sound effects or burps.

STYLE - stay in character:
{style}"""

HIGHLIGHTS_TASK = """

From the channel digests above, pick the 3 most important items across all channels.
Format: exactly 3 lines in {language}, each starts with "• " and one emoji that fits its topic, at most 40 words, ends with the channel name in parentheses. No intro, no Markdown, no source numbers, no repeated jokes.

STYLE - stay in character:
{style}"""

WORDS_PLAIN = 120  # the default "digest" style is a list
WORDS_STYLED = 130  # room for the tone; 180 produced 3-4 paragraphs per channel in practice

# Models sometimes still prepend a refusal-style note about imitating a voice; the retelling follows it.
_DISCLAIMER = re.compile(
    r"\A\s*(?:не могу|я не могу|i can(?:no|')t|i am unable|je ne peux|no puedo)[^\n]*(?:\n\s*)+", re.I
)


def strip_disclaimer(text: str) -> str:
    stripped = _DISCLAIMER.sub("", text, count=1)
    return stripped if stripped.strip() else text


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
        user = (
            f"Posts from the Telegram channel \"{title}\" ({len(posts)}):\n\n"
            + "\n\n".join(blocks)
            + SUMMARY_TASK.format(language=self.language, style=style, words=words)
        )
        text = await self._chat(
            self.model,
            [
                {"role": "system", "content": SUMMARY_SYSTEM},
                {"role": "user", "content": user},
            ],
        )
        return strip_disclaimer(text)

    async def highlights(self, sections: list[tuple[str, str]], style: str) -> str:
        user = "\n\n".join(f"## {title}\n{summary}" for title, summary in sections)
        return await self._chat(
            self.model,
            [
                {"role": "system", "content": SUMMARY_SYSTEM},
                {"role": "user", "content": user + HIGHLIGHTS_TASK.format(language=self.language, style=style)},
            ],
        )

    async def _chat(self, model: str, messages: list[dict]) -> str:
        response = await self.client.chat.completions.create(model=model, messages=messages)
        usage = getattr(response, "usage", None)
        if usage is not None:
            self.usage.input_tokens += usage.prompt_tokens or 0
            self.usage.output_tokens += usage.completion_tokens or 0
        return (response.choices[0].message.content or "").strip()
