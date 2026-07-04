<p align="center">
  <img src="docs/banner.png" alt="Summarix AI — production-ready boilerplate for monetized AI Telegram bots" width="100%"/>
</p>

<p align="center">
  <a href="https://github.com/AndreySukhanov/summarix-ai/actions/workflows/ci.yml"><img src="https://github.com/AndreySukhanov/summarix-ai/actions/workflows/ci.yml/badge.svg" alt="CI"/></a>
  <img src="https://img.shields.io/badge/python-3.13-blue" alt="Python 3.13"/>
  <img src="https://img.shields.io/badge/aiogram-3.x-2CA5E0" alt="aiogram 3"/>
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT"/>
</p>

<p align="center">
  <b>Idea → paying users, without writing the plumbing.</b><br/>
  You bring one function: <code>text in → text out</code>. This repo brings everything else.
</p>

---

## The problem this solves

Every monetized AI bot is 10% unique idea and 90% identical plumbing:

```
users · quotas · payments · subscription tiers · referrals · rate limiting
ban system · admin analytics · i18n · scheduled jobs · deployment · tests
```

People burn weeks on that 90% before they can even test whether anyone wants the 10%. This repo is the 90%, extracted from [Summarix](https://github.com/AndreySukhanov/summarix-bot) — a real bot running in production — and reduced to a clean, replaceable core.

Your entire product lives in **one file**: [`services/ai_service.py`](services/ai_service.py). The demo ships a GPT-4o-mini chat assistant; swap the function body for RAG, image analysis, transcription, an agent loop — quotas, payments and everything else won't notice.

## Features

| | What you get | Why it matters |
|---|---|---|
| 💳 | **Telegram Stars payments** | Zero setup: no Stripe account, no webhooks, no PSP contract. Invoice → pre-checkout → tier activated. |
| 📊 | **Subscription tiers + quotas** | FREE / PRO with monthly request limits. New tier = one enum member + two dict rows in [`config/constants.py`](config/constants.py). |
| 🎁 | **Referral program** | Deep-link invites (`?start=ref_XXX`), bonus requests for both sides, guards against self-referral and double-claiming. |
| 📈 | **Admin funnel** | `/stats`: registrations → activation → 7-day retention → paying conversion. Plus `/ban` and `/unban`. |
| 🌍 | **i18n** | English and Russian included; a new language is one dict in [`utils/i18n.py`](utils/i18n.py). |
| 🛡 | **Abuse protection** | DB-backed ban middleware (cached), per-user rate limiting. |
| 🗄 | **Async SQLAlchemy 2.0** | SQLite for development, PostgreSQL for production — same code, one env var. |
| ⏰ | **Celery beat** | Subscription expiry and monthly quota resets run themselves. |
| 🧪 | **Tests + CI** | pytest on in-memory SQLite (no services needed), GitHub Actions included. |
| 🐳 | **Docker Compose** | `docker-compose up` = postgres + redis + bot + worker + beat. |
| 🪂 | **Graceful degradation** | No Redis → in-memory FSM. No Postgres → SQLite. The bot starts anyway. |

## Quick start — 15 minutes to a live bot

You need exactly **3 keys**:

| Key | Where to get it |
|---|---|
| `BOT_TOKEN` | [@BotFather](https://t.me/BotFather) → `/newbot` |
| `OPENAI_API_KEY` | [platform.openai.com](https://platform.openai.com/api-keys) |
| `ADMIN_ID` | [@userinfobot](https://t.me/userinfobot) → your numeric ID |

### With Docker

```bash
git clone https://github.com/AndreySukhanov/summarix-ai.git
cd summarix-ai
cp .env.example .env   # paste your 3 keys
docker-compose up -d
```

### Without Docker (SQLite, no Redis needed)

```bash
git clone https://github.com/AndreySukhanov/summarix-ai.git
cd summarix-ai
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env   # paste your 3 keys
python run_bot.py
```

Message your bot. It answers, counts quota, sells PRO for Stars, and tracks your funnel in `/stats`. That's the whole loop.

## Make it yours — 3 steps

**1. Replace the AI logic** — [`services/ai_service.py`](services/ai_service.py)

```python
async def generate_reply(user_message: str) -> str:
    # your product goes here: RAG, vision, agents, anything.
    ...
```

**2. Set your prices** — [`config/constants.py`](config/constants.py): quotas, Stars prices, referral bonuses. One file.

**3. Reword the texts** — [`utils/i18n.py`](utils/i18n.py): every user-facing string, en + ru.

Ship it. Everything else — payments, limits, referrals, admin, deploy — already works.

## How it's wired

```
telegram ──▶ aiogram 3 (polling)
              │  middlewares: ban check · rate limit
              │  routers: admin → start → subscription → referral → ai (catch-all, last)
              ▼
       async SQLAlchemy 2.0 ──▶ PostgreSQL (prod) / SQLite (dev)
              │
              ├──▶ OpenAI API      ← services/ai_service.py — YOUR CODE HERE
              └──▶ Redis ──▶ Celery beat: expire subscriptions · reset quotas
```

```
bot/
  main.py                  entry point: storage fallback, middleware/router registration
  handlers/
    start.py               registration + referral deep-links
    ai.py                  quota check → AI call → reply (charges quota only on success)
    subscription.py        status, Stars invoice, pre-checkout, activation
    referral.py            /invite: personal link, stats, share button
    admin.py               /stats funnel, /ban, /unban
  middlewares.py           ban check + rate limit
  keyboards.py             inline keyboards
services/
  ai_service.py            ★ THE SLOT — your product
  subscription_service.py  users, quotas, upgrades
  referral_service.py      codes, bonuses, anti-abuse guards
database/
  models.py                User, Subscription, Payment, ReferralCode, Referral
  connection.py            dual sync/async session stacks
tasks/                     Celery app + scheduled maintenance
config/                    settings (.env) + business constants
utils/                     logger, i18n
tests/                     11 tests, in-memory async SQLite
```

## Design decisions (and why)

- **Telegram Stars, not Stripe.** For digital goods inside Telegram, Stars are mandatory per platform rules anyway — and they require literally zero setup. Fiat/crypto gateways can be added later as extra handlers.
- **Quota is charged after generation, not before.** A failed API call never burns a user's request.
- **Referral bonuses extend the monthly quota additively** (`Subscription.bonus_requests`) — no separate ledger, nothing to reconcile.
- **The AI router registers last.** It's a catch-all for text; commands and callbacks must match first.
- **`expire_on_commit=False`** on async sessions so handlers can read attributes after commit. Trade-off: lazy loading is off — use `selectinload()` for relationships.
- **SQLite in dev is a feature.** Clone → run, no infrastructure. The same code hits Postgres in production via one env var.

## FAQ

**Can I use Claude / Gemini / a local model instead of OpenAI?**
Yes — `ai_service.py` is the only file that knows OpenAI exists. Swap the client, keep the signature.

**Polling or webhooks?**
Polling, deliberately: it works behind NAT, needs no domain or SSL, and survives restarts. At the scale where webhooks matter you'll know how to add them.

**Where do I add my own tables?**
`database/models.py`, then either recreate the dev DB or wire up Alembic — `init_db()` covers you until the schema starts evolving.

**How do I check it works?**
`pytest` — 11 tests, no DB, no Redis, no network. CI runs the same on every push.

## License

[MIT](LICENSE) — build a business on it, no strings. If it saved you a week of plumbing, a ⭐ says thanks.

<p align="center"><sub>Extracted from <a href="https://github.com/AndreySukhanov/summarix-bot">Summarix</a>, a production Telegram bot for AI channel digests.</sub></p>
