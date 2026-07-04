<h1 align="center">🤖 AI Telegram Bot Boilerplate</h1>

<p align="center">
  <a href="https://github.com/AndreySukhanov/summarix-ai/actions/workflows/ci.yml"><img src="https://github.com/AndreySukhanov/summarix-ai/actions/workflows/ci.yml/badge.svg" alt="CI"/></a>
  <img src="https://img.shields.io/badge/python-3.13-blue" alt="Python 3.13"/>
  <img src="https://img.shields.io/badge/aiogram-3.x-2CA5E0" alt="aiogram 3"/>
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT"/>
</p>

<p align="center">
  <b>A monetized AI Telegram bot in production in 15 minutes.</b><br/>
  Payments · subscription tiers · usage quotas · referral program · admin funnel · i18n · tests · Docker · CI.<br/>
  You write ONE file — your AI logic. Everything else is already here.
</p>

---

Every AI bot needs the same boring 90%: users, quotas, payments, referrals, rate limiting, admin tools, deployment. This repo is that 90%, production-tested and wired together. The remaining 10% — what your bot actually *does* — is a single file: [`services/ai_service.py`](services/ai_service.py).

## What's inside

| | |
|---|---|
| 💳 **Payments** | Telegram Stars (XTR) — zero payment-provider setup, no webhooks, no PSP account. Invoice → pre-checkout → activation, done. |
| 📊 **Subscription tiers** | FREE / PRO with monthly request quotas. Adding a tier = one enum member + two dict rows. |
| 🎁 **Referral program** | Deep-link invites (`?start=ref_XXX`), bonus requests for both sides, anti-abuse guards (self-referral, double-claim, exhausted codes). |
| 📈 **Admin funnel** | `/stats`: registrations → activation → retention → paying conversion. Plus `/ban`, `/unban`. |
| 🌍 **i18n** | English + Russian out of the box; adding a language = one dict. |
| 🛡 **Middlewares** | DB-backed ban check (cached), per-user rate limiting. |
| 🗄 **Async SQLAlchemy 2.0** | asyncpg for the bot, sync stack for Celery. SQLite for dev, Postgres for prod — same code. |
| ⏰ **Celery beat** | Subscription expiry and monthly quota reset, scheduled. |
| 🧪 **Tests** | pytest on in-memory async SQLite — no external services needed, runs in CI. |
| 🐳 **Docker** | `docker-compose up` = postgres + redis + bot + worker + beat. |
| 🪂 **Graceful degradation** | No Redis? FSM falls back to memory. No Postgres? SQLite. The bot starts anyway. |

## Quick start

**1. Get 3 keys** — bot token from [@BotFather](https://t.me/BotFather), an [OpenAI API key](https://platform.openai.com/api-keys), your Telegram ID from [@userinfobot](https://t.me/userinfobot).

**2. Run:**

```bash
git clone https://github.com/AndreySukhanov/summarix-ai.git
cd summarix-ai
cp .env.example .env        # paste your 3 keys
docker-compose up -d
```

That's it — message your bot.

**Without Docker** (uses SQLite, no Redis needed):

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # paste your 3 keys
python run_bot.py
```

## Make it yours

**Step 1 — replace the AI logic.** Open [`services/ai_service.py`](services/ai_service.py) and swap the demo chat assistant for whatever your product does: RAG over documents, image generation, transcription, an agent loop. The contract is one async function: text in → text out. Quotas, payments and everything else don't care what happens inside.

**Step 2 — set your prices.** [`config/constants.py`](config/constants.py): tier quotas, Stars prices, referral bonuses. One place.

**Step 3 — reword the texts.** [`utils/i18n.py`](utils/i18n.py): all user-facing strings in one dict.

Ship it.

## Architecture

```
telegram ──▶ aiogram 3 (polling)
              │  middlewares: ban check · rate limit
              │  routers: admin → start → subscription → referral → ai (catch-all, last)
              ▼
       async SQLAlchemy 2.0 ──▶ PostgreSQL (prod) / SQLite (dev)
              │
              ├──▶ OpenAI API          (services/ai_service.py — YOUR CODE HERE)
              └──▶ Redis ──▶ Celery beat: expire subs · reset monthly quotas
```

```
bot/
  main.py            entry point: storage fallback, middleware + router registration
  handlers/          one file per feature: start, ai, subscription, referral, admin
  middlewares.py     ban check + rate limit
  keyboards.py       inline keyboards
services/
  ai_service.py      ★ THE SLOT — replace with your AI feature
  subscription_service.py    users, quotas, upgrades
  referral_service.py        codes, bonuses, guards
database/
  models.py          User, Subscription, Payment, ReferralCode, Referral
  connection.py      dual sync/async session stacks
tasks/               Celery app + scheduled maintenance
config/              pydantic settings (.env) + business constants
utils/               logger, i18n
tests/               unit tests, in-memory async SQLite
```

## Design notes worth knowing

- **Telegram Stars over Stripe/PSP** — for digital goods Telegram *requires* Stars anyway, and they need no setup at all. Crypto or fiat gateways can be added later as separate handlers.
- **Quota charged after generation, not before** — a failed OpenAI call never burns the user's request.
- **`expire_on_commit=False`** on async sessions — handlers read ORM attributes after commit; the trade-off is that lazy loading doesn't work, use `selectinload()`.
- **Referral bonuses live in `Subscription.bonus_requests`** and extend the monthly quota additively — no separate ledger to reconcile.
- **The AI router is registered last** — it catches all plain text, so commands and callbacks must win first.

## Tests

```bash
pytest        # no DB, no Redis, no network — runs anywhere
```

## License

[MIT](LICENSE). Built from a production bot ([Summarix](https://github.com/AndreySukhanov/summarix_ai)). If this saved you a week of plumbing — a ⭐ says thanks.
