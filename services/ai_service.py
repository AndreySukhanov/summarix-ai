"""
═══════════════════════════════════════════════════════════════════
  THIS IS THE SLOT — replace this file with your product's AI logic.
═══════════════════════════════════════════════════════════════════

The demo implementation is a plain chat assistant. Everything around it
(quotas, payments, referrals, admin, i18n, Docker, CI) already works and
doesn't care what you put here: a RAG pipeline, an image generator,
a document analyzer, an agent — anything that takes user input and
returns text.
"""
from openai import AsyncOpenAI

from config.settings import settings
from utils.logger import get_logger

logger = get_logger("services.ai")

SYSTEM_PROMPT = (
    "You are a helpful, concise assistant inside a Telegram bot. "
    "Answer in the same language the user writes in."
)

_client = AsyncOpenAI(api_key=settings.openai_api_key)


async def generate_reply(user_message: str) -> str:
    response = await _client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        max_tokens=1000,
        temperature=0.7,
    )
    return response.choices[0].message.content
