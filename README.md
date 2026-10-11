# Summarix

<p>
  <a href="https://github.com/AndreySukhanov/summarix-ai/actions/workflows/ci.yml"><img src="https://github.com/AndreySukhanov/summarix-ai/actions/workflows/ci.yml/badge.svg" alt="CI"/></a>
  <img src="https://img.shields.io/badge/python-3.13-blue" alt="Python 3.13"/>
  <img src="https://img.shields.io/badge/aiogram-3.x-2CA5E0" alt="aiogram 3"/>
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT"/>
</p>

**A personal Telegram bot that reads the channels you follow and sends you one short digest a day.**

Self-hosted, single user. It reads channels through your own Telegram account, so private channels work too, summarizes them with any OpenAI-compatible model - images included - and links every point back to the original post.

## What you get

An illustrative digest (channels and news are made up):

```
Digest · 13.09.2026
Channels with news: 3 · posts: 27

Highlights
• OpenAI shipped a cheaper vision model (AI Weekly)
• Central bank kept the key rate at 16% (Markets)
• ...

AI Weekly
• A new small vision model is priced 4x below the previous one; benchmarks in the post show it on par for OCR (1, 4)
• Two posts about an agent framework release - mostly a changelog (2, 3)

Markets
• ...
```

Numbers in brackets are links to the posts. The model only cites post numbers; the bot turns them into links, so a made-up URL cannot appear.

## How it works

```
every day at DIGEST_TIME                      /digest, /digest 48
          │                                          │
          ▼                                          ▼
   for each channel: new posts since the last delivered digest
          │   Telethon, your account (private channels, albums)
          ▼
   images ──▶ vision model: one-line caption   (capped per run)
          ▼
   posts + captions ──▶ model: 2-6 bullets citing [post numbers]
          ▼
   2+ channels ──▶ model: top 3 highlights
          ▼
   HTML message(s) to you ──▶ only then posts are marked read
```

- **Nothing is lost on failure.** Read marks move after the digest is delivered. A crash, an API error or a failed send means the same posts come next time.
- **One broken channel does not break the digest.** It is listed at the bottom as "could not read".
- **Ads and cross-promotion are skipped** by the summary prompt.

## Setup

You need four things:

| What | Where |
|---|---|
| `BOT_TOKEN` | [@BotFather](https://t.me/BotFather) → `/newbot`. The chat with this bot is where digests arrive. |
| `OWNER_ID` | [@userinfobot](https://t.me/userinfobot). Everyone else is ignored. |
| `TG_API_ID`, `TG_API_HASH` | [my.telegram.org](https://my.telegram.org) → API development tools. Lets the bot read channels as you. |
| `LLM_API_KEY`, `LLM_MODEL` | OpenAI, OpenRouter, DeepSeek, Qwen or any OpenAI-compatible API. The model must accept images, or set `DESCRIBE_IMAGES=false`. |

```bash
git clone https://github.com/AndreySukhanov/summarix-ai.git
cd summarix-ai
cp .env.example .env            # fill in the keys

# once: log in to your Telegram account (phone, code, 2FA password)
docker compose run --rm bot python -m scripts.login

docker compose up -d
```

Without Docker: `pip install -r requirements.txt`, then `python -m scripts.login` and `python run_bot.py`.

Then open your bot, press Start, and add channels.

## Commands

| Command | What it does |
|---|---|
| `/add @channel https://t.me/other t.me/+invite` | Add one or several channels. Forwarding any post from a channel works too. |
| `/channels` | Numbered list |
| `/remove 2` or `/remove @channel` | Remove |
| `/digest` | Digest of unread posts right now (marks them read) |
| `/digest 48` | Recap of the last 48 hours, marks nothing |
| `/search smart glasses 14` | What your channels wrote about a topic in the last 14 days (30 by default). The model widens the query with word forms and synonyms - Telegram search matches words only - and drops hits where a word matched in another sense |
| `/find smart glasses` | New public channels on a topic: only live ones that actually write about it, with subscribers, posts a month and share of posts on the topic; ➕ adds one |
| `/status` | Model, next scheduled digest, last run with post/image/token counts |

## Configuration

All optional, in `.env`:

| Variable | Default | |
|---|---|---|
| `DIGEST_TIME` / `TIMEZONE` | `09:00` / `Europe/Moscow` | When the daily digest arrives |
| `DIGEST_LANGUAGE` | `Russian` | Language of the summaries, whatever the channels are in |
| `UI_LANGUAGE` | `ru` | `ru` or `en` for bot messages |
| `LLM_BASE_URL` | OpenAI | e.g. `https://openrouter.ai/api/v1` |
| `VISION_MODEL` | `LLM_MODEL` | A separate, cheaper model for image captions |
| `DESCRIBE_IMAGES` | `true` | Caption photos, including posts that are only a picture or a chart |
| `MAX_IMAGES_PER_RUN` | `20` | Cost cap: images beyond this are skipped |
| `LOOKBACK_HOURS` | `24` | How far back the first digest of a newly added channel looks |
| `MAX_POSTS_PER_CHANNEL` | `60` | Upper bound per channel per digest |

## Cost

Per digest: one call per image (sent at low detail), one call per channel with news, one call for highlights. Twenty channels with a few posts each and the image cap at 20 means about 40 calls a day; on a small model that is usually a few cents a day - `/status` shows the real token count.

## Privacy and security

- **The session file (`data/owner.session`) is full access to your Telegram account.** It stays on your machine, is git- and docker-ignored, and should never be shared or committed.
- The bot answers only `OWNER_ID`; every other update is dropped before any handler runs.
- The account is used read-only: it never posts, joins or leaves anything. Channels behind an invite link must be joined by you first.
- Post texts and images are sent to the model provider you configure. Pick one whose data policy you accept, or point `LLM_BASE_URL` at a local model.
- Storage is a local SQLite file with channel names and read marks only; post contents are not stored.

## Project layout

```
bot/
  main.py          wiring: settings, SQLite, Telethon, model, bot, scheduler
  handlers.py      commands + owner-only middleware
  texts.py         ru / en interface strings
services/
  reader.py        Telethon: resolve channels, fetch posts, albums, photos
  llm.py           prompts: image captions, channel summary, highlights
  digest.py        build a digest, mark read after delivery
  scheduler.py     daily run in your timezone, no Celery or Redis
  refs.py          parse @name, t.me links, invite links
database/          two tables: channels, digest runs
scripts/login.py   one-time account login
utils/text.py      citations → links, safe HTML, splitting at 4096 chars
tests/             offline: fake Telegram reader and fake model
```

## Tests

```bash
pip install -r requirements.txt
pytest
```

28 tests, no network: link parsing, album grouping, citation linking and HTML escaping, message splitting, schedule in local time, read marks only after commit, recap windows, image cost cap, broken channels, owner-only access.

## License

[MIT](LICENSE)
