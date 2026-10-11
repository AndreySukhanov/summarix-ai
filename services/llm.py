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
- Write in {language} only. The style description may quote slang in another language: never paste it as is, use natural {language} slang with the same attitude. Plain text, no Markdown; line breaks are fine.
- At most {words} words, one or two short paragraphs. With many posts, keep only what matters most.
- Facts only from the posts - the style changes how you tell them, never what happened. Skip ads and cross-promotion.
- After a key fact, put the source post number in square brackets, e.g. [2]. Only after key facts, not after every sentence. Never write links.
- This retelling is one of many channels the reader sees back to back in one digest. Every channel must sound fresh: use at most one or two signature devices of the style here, no stock opening or closing line, no joke you would reuse for another channel.
- Opening move for this channel: {opening}.
- Start with the retelling itself: no disclaimers, no remarks about the style or the voice.
- Add 2-4 emoji, each next to the fact it illustrates, chosen by the specific topic (💰 money, 🔒 security, 🎮 games, 📉 decline, 🎬 video...). At most one of them may be a mood emoji the style likes (💀 💅 🤡 🔥 ✨ and similar), and only where it lands; skip the generic 🤖 unless the post is literally about robots.
- No sound effects or burps.

STYLE - stay in character:
{style}"""

HIGHLIGHTS_TASK = """

From the channel digests above, pick the 3 most important items across all channels.
Format: exactly 3 lines in {language}, each starts with "• " and one emoji that fits its topic, at most 40 words, ends with the channel name in parentheses. No intro, no Markdown, no source numbers, no repeated jokes.

STYLE - stay in character:
{style}"""

# Channels are summarized in separate calls that cannot see each other, so "don't repeat yourself"
# alone does not stop every channel opening with the same trick. Rotating the opening makes the
# variety mechanical.
OPENINGS = [
    "a short verdict on the situation in five words or fewer",
    "a pointed question to the reader",
    "the single most surprising fact, stated flat",
    "a comparison with something from everyday life",
    "the consequence first, then what caused it",
    "a mini-story: who did what, and what came of it",
    "a number or date from the posts that says it all",
    "mock agreement with the channel that one detail then undermines",
]

WORDS_PLAIN = 120  # the default "digest" style is a list
WORDS_STYLED = 130  # room for the tone; 180 produced 3-4 paragraphs per channel in practice

# Models sometimes still prepend a refusal-style note about imitating a voice; the retelling follows it.
_DISCLAIMER = re.compile(
    r"\A\s*(?:не могу|я не могу|i can(?:no|')t|i am unable|je ne peux|no puedo)[^\n]*(?:\n\s*)+", re.I
)


_LIST_MARK = re.compile(r"^\s*(?:\d+[.)]|[-•*])\s*")  # "1. ", "- ", "• " the model may still add


def strip_disclaimer(text: str) -> str:
    stripped = _DISCLAIMER.sub("", text, count=1)
    return stripped if stripped.strip() else text


SEARCH_SYSTEM = "You are a precise research assistant. You report what Telegram channels wrote about a topic."

SEARCH_TASK = """

These posts matched the search «{query}». Tell the reader what this channel wrote about it.

Format:
- Write in {language} only. Plain text, no Markdown.
- 1 to 4 points, each starts with "• " and is one or two sentences, most important first. At most {words} words in total.
- Facts only from the posts. A post that touches the topic only in passing gets a short mention at most. Skip ads and cross-promotion.
- After a key fact, put the source post number in square brackets, e.g. [2]. Never write links.
- Search matches words, not meaning: a word can match in another sense («очки» are also points in a game). If no post is really about «{query}», answer with the single word NONE."""

SEARCH_NONE = "NONE"

# Telegram search matches whole words: "очки" does not find "очков", "AR-очки" or "smart glasses".
SEARCH_TERMS_TASK = """Telegram search matches whole words and knows nothing of word forms or synonyms.
For the request below, give up to 5 search terms that together find what it is about.
A phrase finds only posts that have every word of it, so the list MUST include the single most telling word of the request on its own (the thing itself, not an adjective). Then other word forms, close synonyms, the English or brand name if there is one. One to three words each.
Example for «электромобили Tesla»: электромобиль, электромобилей, Tesla, EV
Answer with the terms only, one per line, no numbering, no explanations.

Request: {query}"""

PICK_CHANNELS_TASK = """The reader wants Telegram channels about: {query}

These channels were found by a word in their name; each comes with the start of a recent post.
Keep the channels that are really about this topic: its news, reviews, products, development, industry.
Drop channels about a different thing that merely shares a word with the request, and spam.

{channels}

Answer with the numbers of the channels to keep, comma-separated, or "none". Nothing else."""

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

    @staticmethod
    def _posts_block(title: str, posts: list[Post]) -> str:
        blocks = []
        for i, post in enumerate(posts, start=1):
            lines = [f"[{i}] {post.date:%Y-%m-%d %H:%M}"]
            if post.text:
                text = post.text if len(post.text) <= POST_CHARS_IN_PROMPT else post.text[:POST_CHARS_IN_PROMPT] + "…"
                lines.append(text)
            lines += [f"(image: {d})" for d in post.image_descriptions]
            blocks.append("\n".join(lines))
        return f"Posts from the Telegram channel \"{title}\" ({len(posts)}):\n\n" + "\n\n".join(blocks)

    async def summarize_channel(
        self, title: str, posts: list[Post], style: str, words: int = WORDS_PLAIN, index: int | None = None
    ) -> str:
        user = (
            self._posts_block(title, posts)
            + SUMMARY_TASK.format(
                language=self.language,
                style=style,
                words=words,
                opening="straight to the first point" if index is None else OPENINGS[index % len(OPENINGS)],
            )
        )
        text = await self._chat(
            self.model,
            [
                {"role": "system", "content": SUMMARY_SYSTEM},
                {"role": "user", "content": user},
            ],
        )
        return strip_disclaimer(text)

    async def summarize_search(
        self, title: str, query: str, posts: list[Post], words: int = WORDS_PLAIN, language: str | None = None
    ) -> str:
        """`language` per call: two searches running at once may want different languages."""
        user = self._posts_block(title, posts) + SEARCH_TASK.format(
            query=query, language=language or self.language, words=words
        )
        text = await self._chat(
            self.model,
            [
                {"role": "system", "content": SEARCH_SYSTEM},
                {"role": "user", "content": user},
            ],
        )
        return strip_disclaimer(text)

    async def search_terms(self, query: str) -> list[str]:
        """The query plus its word forms and synonyms, for Telegram's word-only search.
        The query alone if the model fails: a search should not die on an extra nicety."""
        try:
            text = await self._chat(self.model, [{"role": "user", "content": SEARCH_TERMS_TASK.format(query=query)}])
        except Exception:
            return [query]
        terms = [_LIST_MARK.sub("", line).strip(" \t\"'«»") for line in text.splitlines()]
        return list(dict.fromkeys([query, *(term for term in terms if term and len(term) <= 40)]))[:6]

    async def pick_channels(self, query: str, channels: list[tuple[str, str]]) -> set[int]:
        """Indexes of (title, sample) pairs that are really about `query`. Every index if the model
        fails: an unfiltered list beats an empty answer."""
        if not channels:
            return set()
        listing = "\n".join(f"{i}. {title} - {sample}" for i, (title, sample) in enumerate(channels, start=1))
        try:
            text = await self._chat(
                self.model,
                [{"role": "user", "content": PICK_CHANNELS_TASK.format(query=query, channels=listing)}],
            )
        except Exception:
            return set(range(len(channels)))
        return {int(n) - 1 for n in re.findall(r"\d+", text) if 1 <= int(n) <= len(channels)}

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
